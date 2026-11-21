"""Learned reliability curve (Calibrate, Xenopoulos et al. 2023).

Idea in plain words: instead of cutting predictions into bins, fit a small model that answers
"when the classifier said p, how often was the outcome 1?" and draw that function. Calibrate uses an
Explainable Boosting Machine (EBM) with one input (p). We copy pycalibrate's settings exactly
(ExplainableBoostingClassifier(binning="uniform", max_bins=256), evaluated on a grid) so E1 can compare.

What we add (proposal: "EBM curves will use family-grouped cross-fitting"):
  * split families into 5 groups; fit the EBM on 4 groups, read the curve and the held-out points' fitted values
    on the 5th; rotate. The curve we draw is the average of the 5 fold curves, the band is their min-max.
  * learned ECE = mean |f_hat(p_i) - p_i| using each point's out-of-fold f_hat, so no point grades itself.
Always draw it next to the binned points, counts and intervals: Calibrate's own study reports a participant
reading the EBM steps as sudden calibration changes.
"""
from __future__ import annotations

import warnings

import numpy as np
from sklearn.model_selection import GroupKFold

from .params import CURVE_GRID, EBM_CROSSFIT_FOLDS, EBM_MAX_BINS, SEED


def make_ebm(seed, max_bins: int = EBM_MAX_BINS, **extra):
    """EBM with uniform-width binning of p, as pycalibrate asks for.

    pycalibrate (2022) passes binning="uniform"; interpret >= 0.3 removed that argument and expresses the same
    choice as feature_types=["uniform"]. We support both so E1 runs on old and new interpret versions.
    """
    from interpret.glassbox import ExplainableBoostingClassifier
    try:
        return ExplainableBoostingClassifier(random_state=seed, binning="uniform", max_bins=max_bins, **extra)
    except TypeError:
        return ExplainableBoostingClassifier(random_state=seed, feature_types=["uniform"], max_bins=max_bins, **extra)


def _ebm(seed):
    return make_ebm(seed, interactions=0)


def pycalibrate_curve(p, y, max_bins: int = EBM_MAX_BINS, seed: int = 42, grid: int = 100):
    """Exact re-implementation of pycalibrate.callbacks.learned_reliability_diagram (for E1)."""
    ebm = make_ebm(seed, max_bins=max_bins)
    ebm.fit(np.asarray(p).reshape(-1, 1), np.asarray(y))
    x = np.linspace(0, 1, grid)
    return x, ebm.predict_proba(x.reshape(-1, 1))[:, 1]


def crossfit_curve(p, y, families, folds: int = EBM_CROSSFIT_FOLDS, seed: int = SEED, grid: int = CURVE_GRID):
    p, y, families = np.asarray(p, float), np.asarray(y, int), np.asarray(families)
    x = np.linspace(0, 1, grid)
    n_groups = len(np.unique(families))
    k = min(folds, n_groups)
    if k < 2 or len(np.unique(y)) < 2:
        return None
    oof = np.full(len(p), np.nan)
    curves = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for tr, te in GroupKFold(n_splits=k).split(p, y, families):
            if len(np.unique(y[tr])) < 2:
                continue
            m = _ebm(seed)
            m.fit(p[tr].reshape(-1, 1), y[tr])
            curves.append(m.predict_proba(x.reshape(-1, 1))[:, 1])
            oof[te] = m.predict_proba(p[te].reshape(-1, 1))[:, 1]
    if not curves:
        return None
    C = np.vstack(curves)
    ok = ~np.isnan(oof)
    return {
        "x": x, "y": C.mean(0), "lo": C.min(0), "hi": C.max(0),
        "learned_ece": float(np.mean(np.abs(oof[ok] - p[ok]))) if ok.any() else np.nan,
        "folds": len(curves), "n": int(len(p)),
    }
