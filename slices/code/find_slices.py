"""Stage: the flagging procedure -> flagged groups ⚑1-⚑5.

    python slices/code/find_slices.py

The five flagged groups are chosen by a fixed rule on 2014 part A only. The rule is deterministic (fixed seed, fixed
parameters), so the same data always gives the same five: there is no manual "freeze" step. Later data (2014 part B,
2015-2017) is only used to re-check them. The dashboard filters work on every case feature without the five.
(File names frozen_top5.json / frozen_assessment.csv are kept so other stages did not change; "frozen" = fixed by
this rule.)

Data: cases with a confirmed examiner ("primary").
  part A    = dev_search    (2014 part A: finds the groups)
  part B    = dev_assess    (2014 part B: re-checks them)
  test      = 2015-2017     (final test; Experiment 2 reuses the five there)

Steps (details and a worked example in vml/slicing.py):
  1. groups = all 1- and 2-condition rules over params.SLICE_ATTRS (tech center, art unit, examiner history, round,
     RCE, letter answered, grounds incl. double patenting; NOT examiner group), plus small-tree leaves (one per model)
  2. size: >= 100 distinct families in part A AND in part B
  3. two tests on part A, per model: group gap - full population gap (gap = predicted allowance - real allowance);
     |difference| >= 0.05 AND its 95% CI (500 family re-draws) excludes 0; at least one of the four models
  4. rank the groups that pass by their largest ECE among the four models; a group with exactly the same part A cases
     as a better-ranked group is not ranked (column duplicate_of); the first five = ⚑1-⚑5
  5. re-check the five on part B and 2015-2017 with the same comparison (+ ECE with 95% CI, learned curves)

Exploratory: no formal error-rate control after the search. Experiment 3 measures how often this procedure flags
groups when every true gap is 0.

Outputs (VML_OUT/slices/): candidates.csv, frozen_top5.json, frozen_assessment.csv, slice_curves.json, _run.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from vml import params  # noqa: E402
from vml.bootstrap import FamilyBootstrap, interval, metric_draws  # noqa: E402
from vml.common import log, need, read_json, write_json, write_manifest  # noqa: E402
from vml.learned import crossfit_curve  # noqa: E402
from vml.metrics import summary  # noqa: E402
from vml.paths import stage_dir  # noqa: E402
from vml.slicing import RuleStats, preds_from_record, rule_mask, search, vocab_from_tiers_file  # noqa: E402

STAGE = "slices"


def vocab_from_tiers():
    return vocab_from_tiers_file(stage_dir("profiles") / "tiers.json")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--refreeze", action="store_true", help="no longer needed (kept so old commands still work)")
    ap.add_argument("--no-curves", action="store_true")
    a = ap.parse_args()
    out = stage_dir(STAGE)
    pred_csv = need(stage_dir("models") / "predictions.csv", "models/code/train_models.py")
    df = pd.read_csv(pred_csv, dtype={"family_root": str, "art_unit": str, "tc": str})
    df = df[df.primary == 1].reset_index(drop=True)
    vocab = vocab_from_tiers()
    if params.DEV_SPLIT == "halves":
        s_df, a_df = df[df.part == "dev_search"].reset_index(drop=True), df[df.part == "dev_assess"].reset_index(drop=True)
    else:
        s_df, a_df = df[df.block == "dev"].reset_index(drop=True), None
    t_df = df[df.block == "test"].reset_index(drop=True)
    models = list(params.LEARNED_MODELS)

    tab, rules = search(s_df, a_df, models, vocab=vocab)
    tab.to_csv(out / "candidates.csv", index=False)
    n_el = int(tab.eligible.sum())
    n_dup = int(tab.duplicate_of.notna().sum())
    log(STAGE, f"{len(tab)} candidates; support ok {int(tab.support_ok.sum())}; pass tests "
               f"{int(tab.passes_tests.sum())}; eligible {n_el} ({n_el - n_dup} with different cases; "
               f"{n_dup} same cases as a better-ranked group, not ranked)")
    if n_el < params.SLICE_TOP_K:
        log(STAGE, f"WARNING: only {n_el} eligible slices (< {params.SLICE_TOP_K}).")

    frozen_path = out / "frozen_top5.json"
    top = tab[tab.top_k]
    record = {                     # no time stamp inside: the same data must give a byte-identical file
        "rule": "top %d eligible slices by largest search-half ECE over the learned models (deterministic)"
                % params.SLICE_TOP_K,
        "candidates_sha1": hashlib.sha1((out / "candidates.csv").read_bytes()).hexdigest(),
        "rule_ids": top.rule_id.tolist(),
        "slices": [{**json.loads(r.to_json()), "preds": json.loads(r.preds), "columns": json.loads(r.columns)}
                   for _, r in top[["rule_id", "label", "preds", "columns", "source", "search_n_families",
                                    "assess_n_families", "search_ece_max", "search_ece_max_model"]].iterrows()],
        "params": {"min_families": params.SLICE_MIN_FAMILIES, "effect_min": params.SLICE_EFFECT_MIN,
                   "boot_B": params.SLICE_BOOT_B, "dev_split": params.DEV_SPLIT},
    }
    if frozen_path.exists():
        old = read_json(frozen_path)
        if old.get("rule_ids") != record["rule_ids"]:
            log(STAGE, "NOTE: the top five changed since the last run (data or parameters changed): "
                       + " | ".join(old.get("rule_ids", [])) + "  ->  " + " | ".join(record["rule_ids"]))
    write_json(frozen_path, record)
    log(STAGE, f"top {len(record['rule_ids'])} labels: " + " | ".join(s["label"] for s in record["slices"]))

    # ---- re-check of the five labels on search / assess / test (same statistics + ECE intervals)
    frozen = [preds_from_record(s) for s in record["slices"]]          # the five label rules
    rows, curves = [], {}
    for part, d in (("dev_search", s_df), ("dev_assess", a_df), ("test", t_df)):
        if d is None or d.empty:
            continue
        st = RuleStats(d, models, B=params.SLICE_BOOT_B, seed=params.SEED).table(frozen)
        bs = FamilyBootstrap(d.family_root, B=params.SLICE_BOOT_B, seed=params.SEED)
        for j, (srec, pr) in enumerate(zip(record["slices"], frozen)):
            m = rule_mask(d, pr)
            row = {"part": part, "rule_id": srec["rule_id"], "label": srec["label"], **st.iloc[j].to_dict()}
            row["support_ok"] = row["n_families"] >= params.SLICE_MIN_FAMILIES
            for mc in models:
                lo, hi = interval(metric_draws(bs, "ece", d[mc].to_numpy(), d.y.to_numpy(), mask=m))
                row[f"ece_lo_{mc}"], row[f"ece_hi_{mc}"] = lo, hi
                s = summary(d.loc[m, mc], d.loc[m, "y"], d.loc[m, "family_root"])
                row[f"brier_{mc}"], row[f"auroc_{mc}"] = s["brier"], s["auroc"]
                if not a.no_curves and m.sum() >= 50:
                    c = crossfit_curve(d.loc[m, mc].to_numpy(), d.loc[m, "y"].to_numpy(),
                                       d.loc[m, "family_root"].to_numpy())
                    if c:
                        curves.setdefault(part, {}).setdefault(srec["rule_id"], {})[mc] = c
            rows.append(row)
    fa = pd.DataFrame(rows)
    fa.to_csv(out / "frozen_assessment.csv", index=False)
    if not a.no_curves:            # keep the previous curves file when curves were skipped
        write_json(out / "slice_curves.json", curves)
    write_manifest(STAGE, {"predictions": pred_csv}, ["candidates.csv", "frozen_top5.json",
                                                      "frozen_assessment.csv", "slice_curves.json"],
                   {"eligible": n_el, "eligible_distinct": n_el - n_dup, "frozen": record["rule_ids"]})
    cols = ["part", "label", "n_families"] + [f"gap_{m}" for m in models] + ["ece_max"]
    log(STAGE, "\n" + fa[cols].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
