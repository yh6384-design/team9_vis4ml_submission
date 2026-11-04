"""Build the modelling cohort: temporal blocks with a family purge.

    python cohort/code/build_cohort.py
    python cohort/code/build_cohort.py --target episode_table/output/episodes_target.csv --out cohort/output

Input: the prediction set from episode_table (one row per episode whose next letter is an allowance,
a non-final or a final rejection; target y_allowance).

Steps
1. Keep checkpoints whose prior examiner letter is a non-final rejection, a final rejection or an
   advisory action.
2. Assign each checkpoint to a block by its reply date:
       train  2008-01-01 to 2013-12-31
       dev    2014-01-01 to 2014-12-31
       test   2015-01-01 to 2017-12-31
3. Drop checkpoints whose next letter was mailed after the end of their block, so no label comes
   from a later period.
4. Family purge: each patent family belongs to the block of its earliest checkpoint; its checkpoints
   in later blocks are dropped, so no family appears in two blocks.
5. Flag identity_verified = 1 when the letter being answered was signed by the examiner whose
   history forms the profile (prior_signed is true).

Output: cohort.csv (one row per checkpoint) and cohort_counts.json (row counts after each step).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PRIOR_TYPES = ("nonfinal_rejection", "final_rejection", "advisory_action")
BLOCKS = [("train", "2008-01-01", "2013-12-31"),
          ("dev", "2014-01-01", "2014-12-31"),
          ("test", "2015-01-01", "2017-12-31")]
ORDER = {name: i for i, (name, _, _) in enumerate(BLOCKS)}
KEEP = ["episode_id", "examiner_id", "app_id", "family_root", "art_unit_today", "block",
        "reply_date", "reply_codes", "prior_type", "prior_date", "next_type", "next_date", "y_allowance",
        "identity_verified", "signature_basis"]


def block_of(date: str) -> str | None:
    for name, lo, hi in BLOCKS:
        if lo <= date <= hi:
            return name
    return None


def build(target_csv: Path) -> tuple[pd.DataFrame, dict]:
    e = pd.read_csv(target_csv, dtype=str)
    counts = {"prediction_set": len(e)}

    e = e[e["prior_type"].isin(PRIOR_TYPES)].copy()
    counts["after_prior_type_filter"] = len(e)

    e["block"] = e["reply_date"].map(block_of)
    counts["outside_all_blocks"] = int(e["block"].isna().sum())
    e = e[e["block"].notna()]

    block_end = {name: hi for name, _, hi in BLOCKS}
    late = e["next_date"] > e["block"].map(block_end)
    counts["dropped_label_after_block_end"] = e[late].groupby("block").size().to_dict()
    e = e[~late]

    first_block = e.groupby("family_root")["block"].agg(lambda s: min(s, key=ORDER.get))
    crossing = e["block"] != e["family_root"].map(first_block)
    counts["dropped_family_in_earlier_block"] = e[crossing].groupby("block").size().to_dict()
    e = e[~crossing].copy()

    e["y_allowance"] = e["y_allowance"].astype(int)
    e["identity_verified"] = (e["prior_signed"].str.lower() == "true").astype(int)
    out = e[KEEP].sort_values(["reply_date", "episode_id"]).reset_index(drop=True)

    counts["cohort"] = len(out)
    counts["by_block"] = (out.groupby("block")
                          .agg(checkpoints=("y_allowance", "size"), families=("family_root", "nunique"),
                               applications=("app_id", "nunique"), allowance_rate=("y_allowance", "mean"),
                               identity_verified=("identity_verified", "sum"))
                          .round(4).reindex([b for b, _, _ in BLOCKS]).to_dict("index"))
    return out, counts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default=str(ROOT / "episode_table" / "output" / "episodes_target.csv"))
    ap.add_argument("--out", default=str(ROOT / "cohort" / "output"))
    a = ap.parse_args()
    out_dir = Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    cohort, counts = build(Path(a.target))
    cohort.to_csv(out_dir / "cohort.csv", index=False)
    (out_dir / "cohort_counts.json").write_text(json.dumps(counts, indent=1, default=int) + "\n")
    print(json.dumps(counts, indent=1, default=int))


if __name__ == "__main__":
    main()
