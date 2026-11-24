"""Experiment 1: reproduce Calibrate (Xenopoulos et al., IEEE VIS 2022 / TVCG 2023).

    python e1_reproduce/code/e1_calibrate_repro.py

E1a  COMPAS example: random forest, MLP and logistic regression, first without age, then with age.
     Checks that defendants aged 45+ are overpredicted without age and that adding age fixes it,
     and recomputes the paper's random-forest region numbers (also over 20 random splits).
E1b  Learned vs binned reliability curve on the breast cancer data (paper Fig. 4).
E1c  The same predictions drawn with uniform or quantile bins and 5/10/15/20 bins (paper Fig. 3),
     on the COMPAS random forest and on our 2015-2017 patent predictions.

Differences from the paper are written to e1_notes.md: interpret >= 0.3 needs feature_types=["uniform"]
instead of binning="uniform", and the paper does not give its seed, split or the max_bins values of Fig. 4
(we use seed 0, a 50/50 split and 50/100/200).
"""
from __future__ import annotations

import sys
import urllib.request
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.datasets import load_breast_cancer  # noqa: E402
from sklearn.ensemble import RandomForestClassifier  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.model_selection import train_test_split  # noqa: E402
from sklearn.neural_network import MLPClassifier  # noqa: E402

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE.parent))
from vml.common import log, write_json, write_manifest  # noqa: E402
from vml.learned import pycalibrate_curve  # noqa: E402
from vml.metrics import bin_index, reliability_table, summary  # noqa: E402
from vml.paths import stage_dir  # noqa: E402

STAGE = "e1"
COMPAS_URL = "https://raw.githubusercontent.com/propublica/compas-analysis/master/compas-scores-two-years.csv"
COMPAS_LOCAL = HERE / "data" / "compas-scores-two-years.csv"
SEED = 0
FEATS = ["sex_male", "felony", "juv_misd_count", "juv_fel_count", "priors_count"]
COLORS = {"RF": "#0072B2", "MLP": "#E69F00", "LR": "#009E73"}


def load_compas():
    if not COMPAS_LOCAL.exists():
        COMPAS_LOCAL.parent.mkdir(parents=True, exist_ok=True)
        log(STAGE, f"downloading COMPAS data from {COMPAS_URL}")
        urllib.request.urlretrieve(COMPAS_URL, COMPAS_LOCAL)
    d = pd.read_csv(COMPAS_LOCAL)
    # ProPublica's standard filters (their analysis notebook)
    d = d[(d.days_b_screening_arrest <= 30) & (d.days_b_screening_arrest >= -30) & (d.is_recid != -1)
          & (d.c_charge_degree != "O") & (d.score_text != "N/A")].copy()
    d["sex_male"] = (d.sex == "Male").astype(int)
    d["felony"] = (d.c_charge_degree == "F").astype(int)
    return d.reset_index(drop=True)


def models():
    return {"RF": RandomForestClassifier(random_state=SEED), "MLP": MLPClassifier(random_state=SEED),
            "LR": LogisticRegression()}


def rel_plot(ax, p, y, label, color, n_bins=10):
    t = reliability_table(p, y, n_bins)
    ax.plot([r["mean_p"] for r in t], [r["observed"] for r in t], "o-", color=color, label=label, ms=4)


def rf_region_numbers(d: pd.DataFrame, seed: int) -> dict:
    """The random-forest numbers the paper reports, for one 50/50 split.

    Paper definition: predictions <= 0.1.
    Our definitions (the paper brushes these regions by hand): overconfident = predictions >= 0.8;
    underconfident = the 10-bin reliability bins below 0.5 whose observed rate is above the mean prediction.
    """
    tr, te = train_test_split(d, test_size=0.5, random_state=seed)
    y, age = te.two_year_recid.to_numpy(), te.age.to_numpy()
    p0 = RandomForestClassifier(random_state=seed).fit(tr[FEATS], tr.two_year_recid).predict_proba(te[FEATS])[:, 1]
    idx, _ = bin_index(p0, 10)
    under_bins = [r["bin"] for r in reliability_table(p0, y, 10) if r["observed"] > r["mean_p"] and r["hi"] <= 0.5]
    over, under, low = p0 >= 0.8, np.isin(idx, under_bins), p0 <= 0.1
    return {"over_n": int(over.sum()), "over_p": p0[over].mean(), "over_obs": y[over].mean(),
            "over_age": age[over].mean(), "under_n": int(under.sum()), "under_age": age[under].mean(),
            "low_n": int(low.sum()), "low_age": age[low].mean() if low.any() else np.nan}


def main():
    warnings.filterwarnings("ignore")
    out = stage_dir(STAGE)
    notes = ["# E1 notes: reproducing Calibrate", ""]

    # ------------------------------------------------------------ E1a COMPAS
    d = load_compas()
    tr, te = train_test_split(d, test_size=0.5, random_state=SEED)
    rows, rel = [], {}
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.2))
    for with_age in (False, True):
        feats = FEATS + (["age"] if with_age else [])
        for name, m in models().items():
            m.fit(tr[feats], tr.two_year_recid)
            p = m.predict_proba(te[feats])[:, 1]
            y = te.two_year_recid.to_numpy()
            for grp, mask in (("all", np.ones(len(te), bool)), ("age 45+", (te.age >= 45).to_numpy()),
                              ("age < 25", (te.age < 25).to_numpy())):
                s = summary(p[mask], y[mask])
                rows.append({"with_age": with_age, "model": name, "group": grp, **s,
                             "accuracy": float(np.mean((p[mask] >= 0.5) == y[mask]))})
                rel[f"{'age' if with_age else 'no_age'}|{name}|{grp}"] = reliability_table(p[mask], y[mask], 10)
            if not with_age:
                rel_plot(axes[0], p, y, name, COLORS[name])
                m45 = (te.age >= 45).to_numpy()
                rel_plot(axes[1], p[m45], y[m45], name, COLORS[name])
            else:
                m45 = (te.age >= 45).to_numpy()
                rel_plot(axes[2], p[m45], y[m45], name, COLORS[name])
    for ax, t in zip(axes, ["All defendants, no age", "Age 45+, no age", "Age 45+, with age"]):
        ax.plot([0, 1], [0, 1], "--", color="gray", lw=1)
        ax.set(title=t, xlabel="Mean predicted probability", ylabel="Observed rate", xlim=(0, 1), ylim=(0, 1))
        ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out / "e1a_compas_reliability.png", dpi=160)
    plt.close(fig)
    ct = pd.DataFrame(rows)
    ct.to_csv(out / "e1a_compas_metrics.csv", index=False)
    write_json(out / "e1a_compas_reliability.json", rel)
    r = rf_region_numbers(d, SEED)
    notes += ["Random forest regions (paper numbers in parentheses; n = defendants in the region):",
              f"- overconfident end, predictions >= 0.8: n {r['over_n']}, mean prediction {r['over_p']:.2f}, "
              f"observed {r['over_obs']:.2f}, mean age {r['over_age']:.1f} (paper: about 0.9 vs 0.75, age 33)",
              f"- underconfident region: n {r['under_n']}, mean age {r['under_age']:.1f} (paper: 35)",
              f"- predictions <= 0.1: n {r['low_n']}, mean age {r['low_age']:.1f} (paper: 31)", ""]
    reps = pd.DataFrame([rf_region_numbers(d, s) for s in range(20)])
    rng = lambda c, f: f"{reps[c].mean():{f}} ({reps[c].min():{f}} to {reps[c].max():{f}})"  # noqa: E731
    notes += ["Our addition, not in the paper: the same numbers over 20 random 50/50 splits, mean (min to max):",
              f"- overconfident end: mean age {rng('over_age', '.1f')}; underconfident region: mean age {rng('under_age', '.1f')}",
              f"- predictions <= 0.1: n {rng('low_n', '.1f')}, mean age {rng('low_age', '.1f')}", ""]
    g45 = ct[ct.group == "age 45+"].pivot(index="model", columns="with_age", values="gap")
    notes += ["", "Signed gap (mean p - observed) for age 45+, without vs with age (positive = overprediction):",
              g45.round(3).to_markdown(), ""]
    acc = ct[ct.group == "all"].pivot(index="model", columns="with_age", values="accuracy")
    notes += ["Accuracy on all test defendants, without vs with age:", acc.round(3).to_markdown(), ""]
    log(STAGE, "E1a COMPAS done")

    # ------------------------------------------------------------ E1b learned vs binned (breast cancer)
    X, yb = load_breast_cancer(return_X_y=True)
    Xtr, Xte, ytr, yte = train_test_split(X, yb, test_size=0.5, random_state=SEED)
    pb = RandomForestClassifier(random_state=SEED).fit(Xtr, ytr).predict_proba(Xte)[:, 1]
    cur = {"binned": {nb: reliability_table(pb, yte, nb) for nb in (8, 10)}, "learned": {}}
    fig, axes = plt.subplots(1, 2, figsize=(9, 4.2))
    for nb, ls in ((8, ":"), (10, "-")):
        t = cur["binned"][nb]
        axes[0].plot([r["mean_p"] for r in t], [r["observed"] for r in t], ls, marker="o", ms=3, label=f"{nb} bins")
    for mb in (50, 100, 200):
        x, f = pycalibrate_curve(pb, yte, max_bins=mb)
        cur["learned"][mb] = {"x": x, "y": f}
        axes[1].plot(x, f, label=f"EBM max_bins={mb}")
    for ax, t in zip(axes, ["Binned (8 vs 10 bins)", "Learned (EBM)"]):
        ax.plot([0, 1], [0, 1], "--", color="gray", lw=1)
        ax.plot(pb, np.full_like(pb, -0.02), "|", color="k", alpha=0.3)
        ax.set(title=t, xlabel="Predicted probability", ylabel="Observed rate", xlim=(0, 1), ylim=(-0.05, 1.02))
        ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(out / "e1b_learned_vs_binned.png", dpi=160)
    plt.close(fig)
    write_json(out / "e1b_breast_curves.json", cur)
    log(STAGE, "E1b breast cancer done")

    # ------------------------------------------------------------ E1c binning grid (COMPAS RF + our patent model)
    grids = {}
    rf = RandomForestClassifier(random_state=SEED).fit(tr[FEATS], tr.two_year_recid)
    sources = {"COMPAS random forest": (rf.predict_proba(te[FEATS])[:, 1], te.two_year_recid.to_numpy())}
    pred_csv = stage_dir("models") / "predictions.csv"
    if pred_csv.exists():
        pp = pd.read_csv(pred_csv)
        pp = pp[(pp.block == "test") & (pp.primary == 1)]
        sources["Patent LR (profile off), test"] = (pp.lr_off.to_numpy(), pp.y.to_numpy())
    for title, (p, y) in sources.items():
        fig, axes = plt.subplots(2, 4, figsize=(13, 6.4), sharex=True, sharey=True)
        grids[title] = {}
        for i, strat in enumerate(("uniform", "quantile")):
            for j, nb in enumerate((5, 10, 15, 20)):
                t = reliability_table(p, y, nb, strat)
                grids[title][f"{strat}_{nb}"] = t
                ax = axes[i, j]
                ax.plot([0, 1], [0, 1], "--", color="gray", lw=1)
                ax.plot([r["mean_p"] for r in t], [r["observed"] for r in t], "o-", ms=3, color="#0072B2")
                e = summary(p, y)
                from vml.metrics import ece
                ax.set_title(f"{strat}, {nb} bins, ECE {ece(p, y, nb, strat):.3f}", fontsize=9)
        fig.suptitle(f"Same model, eight reliability diagrams: {title}")
        fig.tight_layout()
        safe = "compas" if "COMPAS" in title else "patent"
        fig.savefig(out / f"e1c_binning_grid_{safe}.png", dpi=160)
        plt.close(fig)
    write_json(out / "e1c_binning_grid.json", grids)
    notes += ["Deviations: interpret >= 0.3 uses feature_types=['uniform'] instead of binning='uniform'; "
              "seed 0, 50/50 split; Fig. 4 max_bins values 50/100/200 (not stated in the paper); "
              "ProPublica's standard row filters applied before the split (the paper does not say)."]
    (out / "e1_notes.md").write_text("\n".join(notes))
    write_manifest(STAGE, {"compas": COMPAS_LOCAL}, ["e1a_compas_metrics.csv", "e1a_compas_reliability.png",
                                                     "e1b_learned_vs_binned.png", "e1c_binning_grid_*.png",
                                                     "e1_notes.md"])
    log(STAGE, "\n" + "\n".join(notes))


if __name__ == "__main__":
    main()
