"""Stage: features. One row per checkpoint with every input the models and slices use.

    python features/code/build_features.py

Inputs
  VML_OUT/cohort/cohort.csv          from cohort/code/build_cohort.py (run_all.sh writes it there)
  episode_table/output/episodes.csv  committed (all 8,364 episodes: used for the round number and document ids)
  the raw corpus (VML_CORPUS)        profile_index.csv (filing date) and apps/<app>/text/ (rejection grounds)

What is added (and why)
  part          train / dev_search / dev_assess / test. Dev families are split at random (seeded) into two
                disjoint halves: slices are searched on one and checked on the other (proposal, section 4).
  primary       1 if the examiner identity is confirmed (identity_verified); the main analysis uses these rows.
  round_n       1 = reply to the first office action of this application, 2 = the next one, ...
  round_c       round_n capped at 3 ("3" means round 3 or later)
  rce           1 if the reply was a request for continued examination
  tc            technology center = first two digits of the art unit + "00" (e.g. art unit 2873 -> TC 2800)
  filing_year, elapsed_years   from the application's filing date to the reply (checkpoint) date
  g101 g102 g103 g112 g_dp     rejection grounds in the latest rejection letter (non-final or final) mailed on or
                before the prior letter, read from its text: "Claims 1-5 are rejected under 35 U.S.C. 103 ..."
  ground_text_ok 1 if that letter's text exists (otherwise the ground flags are 0 and this flag says why)

Outputs (VML_OUT/features/)
  features.csv, features_summary.json, ground_spotcheck.csv (20 random letters with the matched sentences,
  for a by-hand check that goes into the data card), _run.json
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from vml import params  # noqa: E402
from vml.common import log, need, write_json, write_manifest  # noqa: E402
from vml.paths import EPISODES, corpus_dir, stage_dir  # noqa: E402

STAGE = "features"

# "Claims 1-5 are rejected under (pre-AIA) 35 U.S.C. (§) 103(a) ..." and the section headings
# "Claim Rejections - 35 USC § 102". Line breaks and odd spacing are allowed between the words.
RX_REJ = re.compile(r"rejected\s+under\s+(?:pre[-\s]?AIA\s+)?35\s*U\.?\s*S\.?\s*C\.?\s*(?:§+\s*)?(101|102|103|112)",
                    re.I)
RX_HEAD = re.compile(r"Claim\s+Rejections?\s*[-–—]\s*35\s*U\.?\s*S\.?\s*C\.?\s*(?:§+\s*)?(101|102|103|112)", re.I)
RX_DP = re.compile(r"double\s+patenting", re.I)


def tc_of(au: str) -> str:
    au = str(au)
    return au[:2] + "00" if au[:2].isdigit() else "other"


def letter_texts(corpus: Path, app: str):
    """(date, code, path) for every non-final / final rejection text of one application."""
    d = corpus / "apps" / str(app) / "text"
    out = []
    if d.is_dir():
        for f in d.iterdir():
            n = f.name
            if n.endswith(".txt") and not n.endswith(".substantive.txt") and re.match(r"\d{4}-\d{2}-\d{2}_CT(NF|FR)_", n):
                out.append((n[:10], n[11:15], f))
    return sorted(out)


def grounds(text: str):
    found = {m.group(1) for m in RX_REJ.finditer(text)} | {m.group(1) for m in RX_HEAD.finditer(text)}
    sents = [text[max(0, m.start() - 60): m.end() + 20].replace("\n", " ") for m in RX_REJ.finditer(text)][:3]
    return {f"g{k}": int(k in found) for k in ("101", "102", "103", "112")} | {"g_dp": int(bool(RX_DP.search(text)))}, sents


def main():
    out = stage_dir(STAGE)
    cohort_csv = need(stage_dir("cohort") / "cohort.csv", "cohort/code/build_cohort.py --out $VML_OUT/cohort")
    c = pd.read_csv(cohort_csv, dtype=str)
    e = pd.read_csv(EPISODES, dtype=str)
    corpus = corpus_dir(required=False)
    if corpus is None:
        log(STAGE, "WARNING: raw corpus not found -> filing_year, elapsed_years and ground flags will be empty")

    # ---- round number from all episodes of the application
    e = e.sort_values(["app_id", "reply_date"])
    e["round_n"] = e.groupby("app_id").cumcount() + 1
    keep = ["episode_id", "round_n", "is_first_reply", "prior_doc_ids", "reply_doc_ids", "next_doc_ids",
            "reply_text_paths", "next_text_paths", "next_days", "prior_signed"]
    df = c.merge(e[keep], on="episode_id", how="left", validate="one_to_one")
    df["y"] = df["y_allowance"].astype(int)
    df["primary"] = df["identity_verified"].astype(int)
    df["round_n"] = df["round_n"].astype(int)
    df["round_c"] = df["round_n"].clip(upper=params.ROUND_CAP)
    df["rce"] = df["reply_codes"].fillna("").str.contains("RCEX").astype(int)
    df["art_unit"] = df["art_unit_today"].astype(str)
    df["tc"] = df["art_unit"].map(tc_of)
    df["reply_year"] = df["reply_date"].str[:4].astype(int)

    # ---- filing date and grounds from the raw corpus
    df["filing_date"] = np.nan
    for g in ("g101", "g102", "g103", "g112", "g_dp"):
        df[g] = 0
    df["ground_text_ok"] = 0
    df["ground_doc"] = ""
    spot = []
    if corpus is not None:
        idx = pd.read_csv(corpus / "profile_index.csv", dtype=str)[["app_id", "filing_date"]].drop_duplicates("app_id")
        df = df.drop(columns="filing_date").merge(idx, on="app_id", how="left")
        cache = {}
        for i, r in df.iterrows():
            app = r["app_id"]
            if app not in cache:
                cache[app] = letter_texts(corpus, app)
            cands = [t for t in cache[app] if t[0] <= r["prior_date"]]
            if not cands:
                continue
            day, code, path = cands[-1]
            flags, sents = grounds(path.read_text(errors="ignore"))
            for k, v in flags.items():
                df.at[i, k] = v
            df.at[i, "ground_text_ok"] = 1
            df.at[i, "ground_doc"] = f"apps/{app}/text/{path.name}"
            spot.append({"episode_id": r["episode_id"], "letter": f"apps/{app}/text/{path.name}", **flags,
                         "matched_sentences": " | ".join(sents)})
    fd = pd.to_datetime(df["filing_date"], errors="coerce")
    rd = pd.to_datetime(df["reply_date"])
    df["filing_year"] = fd.dt.year
    df["elapsed_years"] = (rd - fd).dt.days / 365.25

    # ---- dev halves by family (seeded), the rest by block
    dev_fams = np.array(sorted(df.loc[df.block == "dev", "family_root"].unique()))
    rng = np.random.default_rng(params.SEED)
    rng.shuffle(dev_fams)
    cut = int(round(len(dev_fams) * params.DEV_SEARCH_FRACTION))
    search_fams = set(dev_fams[:cut])
    df["part"] = df["block"]
    if params.DEV_SPLIT == "halves":
        is_dev = df.block == "dev"
        df.loc[is_dev, "part"] = np.where(df.loc[is_dev, "family_root"].isin(search_fams), "dev_search", "dev_assess")

    cols = ["episode_id", "examiner_id", "app_id", "family_root", "block", "part", "primary", "y",
            "reply_date", "reply_year", "prior_type", "prior_date", "next_type", "next_date", "signature_basis",
            "art_unit", "tc", "round_n", "round_c", "rce", "filing_date", "filing_year", "elapsed_years",
            "g101", "g102", "g103", "g112", "g_dp", "ground_text_ok", "ground_doc",
            "prior_doc_ids", "reply_doc_ids", "next_doc_ids", "reply_text_paths", "next_text_paths"]
    df = df[cols].sort_values(["reply_date", "episode_id"]).reset_index(drop=True)
    df.to_csv(out / "features.csv", index=False)

    # ---- summary: counts, confirmed share rule (update, Response 1), ground rates
    summ = {"rows": len(df), "corpus_used": corpus is not None}
    blocks = {}
    for b, g in df.groupby("block"):
        share = g["primary"].mean()
        blocks[b] = {"checkpoints": len(g), "families": g.family_root.nunique(), "allowance_rate": g.y.mean(),
                     "confirmed_share": share, "supports_conclusions": bool(share >= params.CONFIRMED_SHARE_MIN)}
    summ["blocks"] = blocks
    summ["parts"] = {p: {"checkpoints": len(g), "families": g.family_root.nunique(), "primary": int(g.primary.sum())}
                     for p, g in df.groupby("part")}
    summ["ground_text_ok_share"] = float(df.ground_text_ok.mean())
    summ["ground_rates_when_text_ok"] = df.loc[df.ground_text_ok == 1, ["g101", "g102", "g103", "g112", "g_dp"]
                                               ].mean().round(3).to_dict()
    summ["round_c_counts"] = df.round_c.value_counts().sort_index().to_dict()
    summ["filing_date_missing"] = int(df.filing_date.isna().sum())
    write_json(out / "features_summary.json", summ)
    if spot:
        pd.DataFrame(spot).sample(n=min(20, len(spot)), random_state=params.SEED).to_csv(out / "ground_spotcheck.csv",
                                                                                         index=False)
    write_manifest(STAGE, {"cohort": cohort_csv, "episodes": EPISODES,
                           "profile_index": (corpus / "profile_index.csv") if corpus else "missing"},
                   ["features.csv", "features_summary.json", "ground_spotcheck.csv"])
    log(STAGE, f"{len(df)} checkpoints -> {out/'features.csv'}")
    for b, v in blocks.items():
        log(STAGE, f"  {b}: {v['checkpoints']} rows, confirmed share {v['confirmed_share']:.3f}"
                   f" -> {'OK' if v['supports_conclusions'] else 'DESCRIPTIVE ONLY'}")


if __name__ == "__main__":
    main()
