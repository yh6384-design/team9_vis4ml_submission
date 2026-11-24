"""Figures for the paper and slides, drawn from the stage outputs.

    python figures/code/make_figures.py

Every figure is drawn from the CSV/JSON outputs, never from numbers typed by hand. Colors match the interface
(colorblind-safe Okabe-Ito family; profile off = light, on = dark). Diverging quantities use a scale centered at 0.

  fig_reliability_overall.png   reliability diagram (10 bins, Wilson 95% CI) + learned curve + histogram, 2014 and 2015–17
  fig_by_year.png               gap (predicted allowance − real allowance) per reply year with 95% CI: the drift
  fig_e2_forest.png             Experiment 2: on − off (ECE, Brier score, AUROC) with paired 95% CI, by group
  fig_frozen_replication.png    flagged groups ⚑1–⚑5: group gap − full population gap in 2014 part A, part B, 2015–17
  fig_e3_recovery.png           Experiment 3: share of known gaps found, by group size and size of gap; groups passing by luck
Outputs: VML_OUT/figures/
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from vml import params  # noqa: E402
from vml.common import log, read_json, write_manifest  # noqa: E402
from vml.paths import stage_dir  # noqa: E402

STAGE = "figures"
COL = {"base": "#999999", "lr_off": "#56B4E9", "lr_on": "#0072B2", "gbt_off": "#F0A35E", "gbt_on": "#D55E00"}
LAB = params.MODEL_LABEL
plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False})


def yerr(est, lo, hi):
    """Error-bar lengths, never negative. Rounding (a rate of exactly 0 or 1) or a bootstrap interval that does not
    contain the point estimate (ECE is biased upward in resamples) can give tiny negative values, which newer
    matplotlib refuses."""
    est, lo, hi = (np.asarray(v, float) for v in (est, lo, hi))
    return [np.clip(est - lo, 0, None), np.clip(hi - est, 0, None)]


def fig_reliability(out):
    rel = pd.read_csv(stage_dir("metrics") / "reliability_bins.csv")
    curves = read_json(stage_dir("metrics") / "learned_curves.json")
    pred = pd.read_csv(stage_dir("models") / "predictions.csv")
    fig, axes = plt.subplots(2, 4, figsize=(13, 6.2), gridspec_kw={"height_ratios": [3, 1]}, sharex=True)
    for j, (part, pair) in enumerate([("dev", ("lr_off", "lr_on")), ("dev", ("gbt_off", "gbt_on")),
                                      ("test", ("lr_off", "lr_on")), ("test", ("gbt_off", "gbt_on"))]):
        ax, axh = axes[0, j], axes[1, j]
        ax.plot([0, 1], [0, 1], "--", color="gray", lw=1)
        d = pred[(pred.block == part) & (pred.primary == 1)]
        for m in pair:
            t = rel[(rel.part == part) & (rel.model == m) & (rel.n_bins == params.N_BINS)]
            ax.errorbar(t.mean_p, t.observed, yerr=yerr(t.observed, t.ci_lo, t.ci_hi), fmt="o", ms=4,
                        color=COL[m], label=LAB[m], capsize=0, lw=1)
            c = curves.get(part, {}).get(m)
            if c:
                x = np.array(c["x"]); lo, hi = d[m].min(), d[m].max(); k = (x >= lo) & (x <= hi)
                ax.plot(x[k], np.array(c["y"])[k], color=COL[m], lw=1.4)
                ax.fill_between(x[k], np.array(c["lo"])[k], np.array(c["hi"])[k], color=COL[m], alpha=0.12, lw=0)
            axh.hist(d[m], bins=np.linspace(0, 1, 41), histtype="stepfilled", alpha=0.25, color=COL[m])
            axh.hist(d[m], bins=np.linspace(0, 1, 41), histtype="step", color=COL[m])
        ax.set(title=f"{'2014' if part == 'dev' else '2015–2017 (final test)'}", xlim=(0, 1), ylim=(0, 1),
               ylabel="Real allowance" if j == 0 else None)
        ax.legend(fontsize=7, loc="upper left")
        axh.set(xlabel="Predicted allowance", ylabel="Cases" if j == 0 else None)
    fig.tight_layout()
    fig.savefig(out / "fig_reliability_overall.png", dpi=180)
    plt.close(fig)


def fig_by_year(out):
    by = pd.read_csv(stage_dir("metrics") / "by_year.csv")
    fig, ax = plt.subplots(figsize=(6.5, 3.4))
    ax.axhline(0, color="gray", lw=1)
    for i, m in enumerate(params.ALL_MODELS):
        t = by[by.model == m]
        off = (i - 2) * 0.08
        ax.errorbar(t.year + off, t.gap, yerr=yerr(t.gap, t.gap_lo, t.gap_hi), fmt="o-", ms=3, lw=1,
                    color=COL[m], label=LAB[m])
    years = sorted(by.year.unique())
    ax.set_xticks(years, [str(int(y)) for y in years])
    shown = ", ".join(str(int(y)) for y in years)
    ax.set(xlabel=f"Reply year ({shown}; years with too few cases are left out)", ylabel="Gap = predicted − real allowance",
           title="Gap by year (above 0: predicted allowance too high)")
    ax.legend(fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(out / "fig_by_year.png", dpi=180)
    plt.close(fig)


def fig_e2(out):
    e2 = pd.read_csv(stage_dir("e2") / "e2_paired.csv")
    e2 = e2[(e2.cohort == "primary") & e2.group_type.isin(["all", "round", "history_tier", "frozen_slice"])]
    groups = e2.drop_duplicates(["group_type", "group"])[["group_type", "group", "support_ok"]].reset_index(drop=True)
    fig, axes = plt.subplots(1, 3, figsize=(13, 0.32 * len(groups) + 1.6), sharey=True)
    for ax, k, t in zip(axes, ("ece", "brier", "auroc"), ("Δ ECE (lower = better)", "Δ Brier score (lower = better)",
                                                          "Δ AUROC (higher = better)")):
        ax.axvline(0, color="gray", lw=1)
        for pi, (off, on) in enumerate(params.PAIRS):
            g = e2[e2.pair == f"{off}->{on}"].set_index(["group_type", "group"])
            for i, r in groups.iterrows():
                if (r.group_type, r.group) not in g.index:
                    continue
                row = g.loc[(r.group_type, r.group)]
                yv = i + (pi - 0.5) * 0.3
                c = COL[on] if r.support_ok else "#bbbbbb"
                ax.plot([row[f"delta_{k}_lo"], row[f"delta_{k}_hi"]], [yv, yv], color=c, lw=1.5)
                ax.plot(row[f"delta_{k}"], yv, "o", color=c, ms=4, label=("LR" if pi == 0 else "Trees") if i == 0 else None)
        ax.set(title=t)
    axes[0].set_yticks(range(len(groups)))
    gname = {"all": "full population", "round": "round", "history_tier": "examiner history", "frozen_slice": "flagged group"}
    axes[0].set_yticklabels([f"{gname.get(r.group_type, r.group_type)}: {r.group}" if r.group_type != "all"
                             else "full population" for _, r in groups.iterrows()], fontsize=7)
    axes[0].invert_yaxis()
    axes[0].legend(fontsize=7)
    fig.suptitle("Experiment 2: profile on − off, 2015–2017, same cases, paired 95% CI (1,000 family re-draws; gray = < 100 families)",
                 fontsize=9)
    fig.tight_layout()
    fig.savefig(out / "fig_e2_forest.png", dpi=180)
    plt.close(fig)


def fig_frozen(out):
    fa = pd.read_csv(stage_dir("slices") / "frozen_assessment.csv")
    labels = fa.drop_duplicates("rule_id").label.tolist()
    fig, axes = plt.subplots(1, len(params.LEARNED_MODELS), figsize=(13, 0.5 * len(labels) + 1.8), sharey=True)
    parts = [("dev_search", "o", "2014 part A (finds)"), ("dev_assess", "s", "2014 part B (re-checks)"), ("test", "D", "2015–2017 (final test)")]
    for ax, m in zip(axes, params.LEARNED_MODELS):
        ax.axvline(0, color="gray", lw=1)
        for k, (part, mk, nm) in enumerate(parts):
            t = fa[fa.part == part].set_index("label").reindex(labels)
            yv = np.arange(len(labels)) + (k - 1) * 0.22
            ax.errorbar(t[f"gapdiff_{m}"], yv, xerr=yerr(t[f"gapdiff_{m}"], t[f"gapdiff_lo_{m}"], t[f"gapdiff_hi_{m}"]),
                        fmt=mk, ms=4, lw=1, color=["#444444", "#888888", COL[m]][k], label=nm)
        ax.set(title=LAB[m], xlabel="group gap − full population gap")
    axes[0].set_yticks(range(len(labels)))
    axes[0].set_yticklabels([f"⚑{i + 1} {l}" for i, l in enumerate(labels)], fontsize=7)
    axes[0].invert_yaxis()
    h, l = axes[0].get_legend_handles_labels()
    fig.legend(h, l, fontsize=7, loc="lower center", ncol=3, frameon=False)
    fig.suptitle("Flagged groups ⚑1–⚑5 (fixed rule on 2014 part A), re-checked on 2014 part B and 2015–2017; bars = 95% CI", fontsize=9)
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    fig.savefig(out / "fig_frozen_replication.png", dpi=180)
    plt.close(fig)


def fig_e3(out):
    s = read_json(stage_dir("e3") / "e3_summary.json")
    rec = pd.DataFrame(s["recovery"])
    rec = rec[rec.measure == "hit_overlap"]
    piv = rec.pivot(index="size", columns="delta", values="rate").reindex(["small", "medium", "large"])
    nulls = pd.read_csv(stage_dir("e3") / "e3_null.csv")
    fig, (a, b) = plt.subplots(1, 2, figsize=(11, 3.6), gridspec_kw={"width_ratios": [1.3, 1]})
    im = a.imshow(piv.values, cmap="Blues", vmin=0, vmax=1, aspect="auto")
    for i in range(piv.shape[0]):
        for j in range(piv.shape[1]):
            v = piv.values[i, j]
            a.text(j, i, f"{v:.2f}", ha="center", va="center", color="white" if v > 0.6 else "black")
    a.set_xticks(range(piv.shape[1]), [f"±{d}" for d in piv.columns])
    a.set_yticks(range(piv.shape[0]), piv.index)
    a.set(xlabel="Known gap added (log-odds; 0.25 / 0.5 / 1.0 ≈ 6 / 12 / 23 points at 50%)", ylabel="Group size",
          title="Share of runs where a flagged group shares ≥ 50% of its cases\nwith the group given the known gap")
    fig.colorbar(im, ax=a, fraction=0.04)
    b.hist(nulls.n_eligible, bins=np.arange(-0.5, nulls.n_eligible.max() + 1.5), color="#999999")
    b.set(xlabel="Groups passing the tests by luck in one run", ylabel="Runs",
          title=f"Runs with no real gap: {(nulls.n_eligible == 0).mean():.0%} have no group passing, "
                f"{(nulls.n_eligible > 0).mean():.0%} at least one\n"
                f"mean {nulls.n_eligible.mean():.1f} passing per run; at most 5 flagged, mean {nulls.n_eligible.clip(upper=5).mean():.1f}")
    b.title.set_fontsize(7.5)
    b.yaxis.get_major_locator().set_params(integer=True)
    fig.tight_layout()
    fig.savefig(out / "fig_e3_recovery.png", dpi=180)
    plt.close(fig)


def main():
    out = stage_dir(STAGE)
    made = []
    for f in (fig_reliability, fig_by_year, fig_e2, fig_frozen, fig_e3):
        try:
            f(out)
            made.append(f.__name__)
        except FileNotFoundError as e:
            log(STAGE, f"skipped {f.__name__}: missing {e.filename} (run that stage first)")
    write_manifest(STAGE, {}, made)
    log(STAGE, f"made {made}, saved to {out}")


if __name__ == "__main__":
    main()
