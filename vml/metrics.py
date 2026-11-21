"""Calibration and quality measures.

All functions take numpy arrays: p = predicted probability of allowance, y = 0/1 outcome.

  ece(p, y, n_bins, strategy)   expected calibration error: weighted average |observed rate - mean prediction|
                                over bins. strategy "uniform" (fixed-width, our main choice) or "quantile".
  mce                           the largest bin gap
  signed_gap(p, y)              mean(p - y). Positive = the model predicts allowance too often (overprediction).
                                Opposite errors cancel here, which is why we report it next to ECE.
  brier, log_loss, auroc        proper scores and ranking quality
  summary(...)                  everything at once, plus counts
  reliability_table(...)        one row per bin: mean prediction, observed rate, count, Wilson 95% interval
"""
from __future__ import annotations

import numpy as np
from sklearn.metrics import roc_auc_score

from .params import CLIP, N_BINS


def bin_index(p: np.ndarray, n_bins: int = N_BINS, strategy: str = "uniform", edges: np.ndarray | None = None):
    p = np.asarray(p, float)
    if edges is None:
        edges = bin_edges(p, n_bins, strategy)
    idx = np.searchsorted(edges[1:-1], p, side="right")
    return idx, edges


def bin_edges(p: np.ndarray, n_bins: int = N_BINS, strategy: str = "uniform") -> np.ndarray:
    if strategy == "uniform":
        return np.linspace(0.0, 1.0, n_bins + 1)
    if strategy == "quantile":
        e = np.unique(np.quantile(p, np.linspace(0, 1, n_bins + 1)))
        e[0], e[-1] = 0.0, 1.0
        return e
    raise ValueError(strategy)


def ece(p, y, n_bins: int = N_BINS, strategy: str = "uniform") -> float:
    p, y = np.asarray(p, float), np.asarray(y, float)
    if len(p) == 0:
        return np.nan
    idx, edges = bin_index(p, n_bins, strategy)
    k = len(edges) - 1
    cnt = np.bincount(idx, minlength=k)
    sp = np.bincount(idx, weights=p, minlength=k)
    sy = np.bincount(idx, weights=y, minlength=k)
    m = cnt > 0
    return float(np.sum(np.abs(sy[m] - sp[m])) / len(p))


def mce(p, y, n_bins: int = N_BINS, strategy: str = "uniform") -> float:
    p, y = np.asarray(p, float), np.asarray(y, float)
    if len(p) == 0:
        return np.nan
    idx, edges = bin_index(p, n_bins, strategy)
    k = len(edges) - 1
    cnt = np.bincount(idx, minlength=k)
    sp = np.bincount(idx, weights=p, minlength=k)
    sy = np.bincount(idx, weights=y, minlength=k)
    m = cnt > 0
    return float(np.max(np.abs(sy[m] - sp[m]) / cnt[m]))


def signed_gap(p, y) -> float:
    p, y = np.asarray(p, float), np.asarray(y, float)
    return float(np.mean(p - y)) if len(p) else np.nan


def brier(p, y) -> float:
    p, y = np.asarray(p, float), np.asarray(y, float)
    return float(np.mean((p - y) ** 2)) if len(p) else np.nan


def log_loss(p, y) -> float:
    p = np.clip(np.asarray(p, float), CLIP, 1 - CLIP)
    y = np.asarray(y, float)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))) if len(p) else np.nan


def auroc(p, y) -> float:
    y = np.asarray(y)
    if len(np.unique(y)) < 2:
        return np.nan          # single-class group: AUROC is not defined (proposal: "AUROC will be unavailable")
    return float(roc_auc_score(y, p))


def summary(p, y, fam=None) -> dict:
    p, y = np.asarray(p, float), np.asarray(y, float)
    out = {
        "n": int(len(p)),
        "n_families": int(len(np.unique(fam))) if fam is not None else np.nan,
        "prevalence": float(np.mean(y)) if len(y) else np.nan,
        "mean_p": float(np.mean(p)) if len(p) else np.nan,
        "single_class": bool(len(np.unique(y)) < 2),
        "ece": ece(p, y, N_BINS),
        "ece_5": ece(p, y, 5),
        "ece_15": ece(p, y, 15),
        "ece_q10": ece(p, y, N_BINS, "quantile"),
        "mce": mce(p, y, N_BINS),
        "gap": signed_gap(p, y),
        "brier": brier(p, y),
        "log_loss": log_loss(p, y),
        "auroc": auroc(p, y),
    }
    return out


def wilson(k, n, z=1.96):
    k, n = np.asarray(k, float), np.asarray(n, float)
    with np.errstate(invalid="ignore", divide="ignore"):
        ph = k / n
        den = 1 + z * z / n
        c = (ph + z * z / (2 * n)) / den
        h = z * np.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / den
    return c - h, c + h


def reliability_table(p, y, n_bins: int = N_BINS, strategy: str = "uniform"):
    """Rows: bin, lo, hi, n, mean_p, observed, ci_lo, ci_hi, gap (= mean_p - observed)."""
    p, y = np.asarray(p, float), np.asarray(y, float)
    idx, edges = bin_index(p, n_bins, strategy)
    k = len(edges) - 1
    cnt = np.bincount(idx, minlength=k)
    sp = np.bincount(idx, weights=p, minlength=k)
    sy = np.bincount(idx, weights=y, minlength=k)
    lo, hi = wilson(sy, cnt)
    rows = []
    for b in range(k):
        if cnt[b] == 0:
            continue
        rows.append({"bin": b, "lo": edges[b], "hi": edges[b + 1], "n": int(cnt[b]),
                     "mean_p": sp[b] / cnt[b], "observed": sy[b] / cnt[b],
                     "ci_lo": float(lo[b]), "ci_hi": float(hi[b]), "gap": sp[b] / cnt[b] - sy[b] / cnt[b]})
    return rows
