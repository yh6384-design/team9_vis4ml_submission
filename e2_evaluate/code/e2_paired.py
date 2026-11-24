"""Experiment 2: profile off vs on, on the same 2015-2017 cases.

    python e2_evaluate/code/e2_paired.py

For each pair (LR off/on, trees off/on): difference = on - off for ECE, Brier score, log loss, AUROC and gap,
with a paired 95% CI (the same family re-draws score both models).
Groups: full population, round, examiner history tier, the five flagged groups, and tech centers with >= 100 families.
Main result: confirmed examiners; all cases is a secondary check.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from vml import params  # noqa: E402
from vml.bootstrap import FamilyBootstrap, interval, metric_draws  # noqa: E402
from vml.common import log, need, read_json, write_manifest  # noqa: E402
from vml.metrics import summary  # noqa: E402
from vml.paths import stage_dir  # noqa: E402
from vml.slicing import preds_from_record, rule_mask  # noqa: E402

STAGE = "e2"
METRICS = ("ece", "brier", "log_loss", "auroc", "gap")
TITLE = {"all": "Full population", "round": "Round", "history_tier": "Examiner history",
         "frozen_slice": "Flagged groups", "tc": "Tech center"}
PAIR_NAME = {"lr_off->lr_on": "LR", "gbt_off->gbt_on": "Trees"}


def groups(d, frozen, tier_labels):
    yield "all", "all", np.ones(len(d), bool)
    for r in sorted(d.round_c.unique()):
        yield "round", {1: "1", 2: "2", 3: "3+"}[int(r)], (d.round_c == r).to_numpy()
    for t in sorted(d.hist_tier.unique()):
        yield "history_tier", tier_labels[int(t)], (d.hist_tier == t).to_numpy()
    for s in frozen:
        yield "frozen_slice", s["label"], rule_mask(d, preds_from_record(s))
    for tc, g in d.groupby("tc"):
        if g.family_root.nunique() >= params.SLICE_MIN_FAMILIES:
            yield "tc", tc, (d.tc == tc).to_numpy()


def main():
    out = stage_dir(STAGE)
    pred_csv = need(stage_dir("models") / "predictions.csv", "models/code/train_models.py")
    frozen = read_json(need(stage_dir("slices") / "frozen_top5.json", "slices/code/find_slices.py"))["slices"]
    tiers = read_json(stage_dir("profiles") / "tiers.json")["labels"]
    df = pd.read_csv(pred_csv, dtype={"family_root": str, "art_unit": str, "tc": str})
    rows = []
    for cohort, d in (("primary", df[(df.block == "test") & (df.primary == 1)]),
                      ("all", df[df.block == "test"])):
        d = d.reset_index(drop=True)
        bs = FamilyBootstrap(d.family_root, B=params.BOOT_B, seed=params.SEED)
        y = d.y.to_numpy()
        for gtype, gname, m in groups(d, frozen, tiers):
            if m.sum() == 0:
                continue
            for off, on in params.PAIRS:
                po, pn = d[off].to_numpy(), d[on].to_numpy()
                so = summary(po[m], y[m], d.family_root[m])
                sn = summary(pn[m], y[m], d.family_root[m])
                row = {"cohort": cohort, "group_type": gtype, "group": gname, "pair": f"{off}->{on}",
                       "n": so["n"], "n_families": so["n_families"], "prevalence": so["prevalence"],
                       "support_ok": so["n_families"] >= params.SLICE_MIN_FAMILIES,
                       "single_class": so["single_class"]}
                for k in METRICS:
                    row[f"{k}_off"], row[f"{k}_on"] = so[k], sn[k]
                    row[f"delta_{k}"] = sn[k] - so[k]
                    if k == "auroc" and so["single_class"]:
                        row[f"delta_{k}_lo"] = row[f"delta_{k}_hi"] = np.nan
                        continue
                    a = metric_draws(bs, k, po, y, mask=m)
                    b = metric_draws(bs, k, pn, y, mask=m)
                    row[f"delta_{k}_lo"], row[f"delta_{k}_hi"] = interval(b - a)
                rows.append(row)
        log(STAGE, f"{cohort}: {len(d)} test checkpoints done")
    tab = pd.DataFrame(rows)
    tab.to_csv(out / "e2_paired.csv", index=False)

    # worst flagged group per model
    fs = tab[(tab.group_type == "frozen_slice") & (tab.cohort == "primary")]
    worst = []
    for off, on in params.PAIRS:
        g = fs[fs.pair == f"{off}->{on}"]
        for side, mdl in (("off", off), ("on", on)):
            if len(g):
                r = g.loc[g[f"ece_{side}"].idxmax()]
                worst.append({"model": mdl, "worst_slice": r.group, "ece": r[f"ece_{side}"], "n_families": r.n_families})
    pd.DataFrame(worst).to_csv(out / "e2_worst_slice.csv", index=False)

    # short readable summary
    lines = ["# Experiment 2 summary: profile off vs on, 2015–2017, primary cohort", "",
             "Δ = profile on − profile off; negative ECE / Brier score / log loss = better; positive AUROC = better.",
             "95% CI: paired family bootstrap (1,000 re-draws). Groups with < 100 families are descriptive only. prev = real allowance.", ""]
    p = tab[tab.cohort == "primary"]
    for gtype in ("all", "round", "history_tier", "frozen_slice", "tc"):
        g = p[p.group_type == gtype]
        if g.empty:
            continue
        lines.append(f"## {TITLE.get(gtype, gtype)}")
        lines.append("| group | model | families | prev | ΔECE [95%] | ΔBrier [95%] | ΔAUROC [95%] |")
        lines.append("|---|---|---|---|---|---|---|")
        for _, r in g.iterrows():
            def f(k):
                return f"{r[f'delta_{k}']:+.3f} [{r[f'delta_{k}_lo']:+.3f}, {r[f'delta_{k}_hi']:+.3f}]"
            flag = "" if r.support_ok else " (low support)"
            lines.append(f"| {r.group}{flag} | {PAIR_NAME.get(r.pair, r.pair)} | {r.n_families} | {r.prevalence:.2f} | {f('ece')} | "
                         f"{f('brier')} | {f('auroc')} |")
        lines.append("")
    (out / "e2_summary.md").write_text("\n".join(lines))
    write_manifest(STAGE, {"predictions": pred_csv, "frozen": stage_dir("slices") / "frozen_top5.json"},
                   ["e2_paired.csv", "e2_worst_slice.csv", "e2_summary.md"])
    log(STAGE, "\n".join(lines[:16]))


if __name__ == "__main__":
    main()
