"""Stage: calibration measurement

    python metrics/code/run_metrics.py            

For every model x data part x cohort it reports:
  ECE with 10 fixed-width bins (+ 5 and 15 bins, + 10 quantile bins as a binning check), MCE, signed gap,
  Brier, log loss, AUROC, prevalence, mean prediction, checkpoints, families,
  and family-bootstrap 95% intervals for ECE, gap, Brier, log loss and AUROC (primary cohort).

  parts    dev_search, dev_assess, dev (both halves), test
  cohorts  primary (confirmed examiner, the main analysis) and all (secondary, with the fallback)

Also:
  reliability_bins.csv    the binned reliability diagram for 5/10/15 bins (mean prediction, observed rate,
                          count, Wilson 95% interval) 
  learned_curves.json     EBM learned curve, family cross-fitted (vml/learned.py), per model and part
  by_year.csv             the same measures per reply year (dev + test): shows the drift over time
  confirmed_share.csv     update rule: a block whose confirmed share is below 80% is descriptive only

Outputs: VML_OUT/metrics/
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from vml import params  # noqa: E402
from vml.bootstrap import FamilyBootstrap, interval, metric_draws  # noqa: E402
from vml.common import log, need, write_json, write_manifest  # noqa: E402
from vml.learned import crossfit_curve  # noqa: E402
from vml.metrics import reliability_table, summary  # noqa: E402
from vml.paths import stage_dir  # noqa: E402

STAGE = "metrics"
CI_METRICS = ("ece", "gap", "brier", "log_loss", "auroc")


def parts_of(df):
    yield "dev_search", df[df.part == "dev_search"]
    yield "dev_assess", df[df.part == "dev_assess"]
    yield "dev", df[df.block == "dev"]
    yield "test", df[df.block == "test"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true", help="B=200 bootstrap, skip learned curves (debugging)")
    a = ap.parse_args()
    B = 200 if a.fast else params.BOOT_B
    out = stage_dir(STAGE)
    pred_csv = need(stage_dir("models") / "predictions.csv", "models/code/train_models.py")
    df = pd.read_csv(pred_csv, dtype={"family_root": str})

    rows, rel, curves, years = [], [], {}, []
    for cohort, cd in (("primary", df[df.primary == 1]), ("all", df)):
        for part, d in parts_of(cd):
            if d.empty:
                continue
            bs = FamilyBootstrap(d.family_root, B=B, seed=params.SEED)
            for m in params.ALL_MODELS:
                p, y = d[m].to_numpy(), d.y.to_numpy()
                s = {"cohort": cohort, "part": part, "model": m, **summary(p, y, d.family_root)}
                for k in CI_METRICS:
                    if m == "base" and k == "auroc":
                        s[f"{k}_lo"] = s[f"{k}_hi"] = np.nan
                        continue
                    s[f"{k}_lo"], s[f"{k}_hi"] = interval(metric_draws(bs, k, p, y))
                rows.append(s)
                if cohort == "primary":
                    for nb in (5, params.N_BINS, 15):
                        for r in reliability_table(p, y, nb):
                            rel.append({"part": part, "model": m, "n_bins": nb, **r})
                    if not a.fast and part in ("dev", "test", "dev_search", "dev_assess") and m != "base":
                        c = crossfit_curve(p, y, d.family_root.to_numpy())
                        if c:
                            curves.setdefault(part, {})[m] = c
            log(STAGE, f"{cohort} {part}: {len(d)} rows done")
    tab = pd.DataFrame(rows)
    tab.to_csv(out / "metrics_overall.csv", index=False)
    pd.DataFrame(rel).to_csv(out / "reliability_bins.csv", index=False)
    write_json(out / "learned_curves.json", curves)

    # by reply year (primary), with intervals for gap and ECE
    for yr, d in df[df.primary == 1].groupby("reply_year"):
        if len(d) < 30:
            continue
        bs = FamilyBootstrap(d.family_root, B=B, seed=params.SEED)
        for m in params.ALL_MODELS:
            p, y = d[m].to_numpy(), d.y.to_numpy()
            s = {"year": int(yr), "model": m, **summary(p, y, d.family_root)}
            for k in ("ece", "gap"):
                s[f"{k}_lo"], s[f"{k}_hi"] = interval(metric_draws(bs, k, p, y))
            years.append(s)
    pd.DataFrame(years).to_csv(out / "by_year.csv", index=False)

    feat = pd.read_csv(stage_dir("features") / "features.csv", usecols=["block", "primary"])
    cs = feat.groupby("block").primary.agg(["mean", "size"]).rename(columns={"mean": "confirmed_share",
                                                                             "size": "checkpoints"})
    cs["supports_conclusions"] = cs.confirmed_share >= params.CONFIRMED_SHARE_MIN
    cs.to_csv(out / "confirmed_share.csv")

    write_manifest(STAGE, {"predictions": pred_csv}, ["metrics_overall.csv", "reliability_bins.csv",
                                                      "learned_curves.json", "by_year.csv", "confirmed_share.csv"],
                   {"bootstrap_B": B})
    show = tab[(tab.cohort == "primary") & tab.part.isin(["dev", "test"])][
        ["part", "model", "ece", "ece_lo", "ece_hi", "gap", "brier", "log_loss", "auroc"]]
    log(STAGE, "\n" + show.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
