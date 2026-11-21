"""Family bootstrap: the way we put a 95% interval on every number.

Why families? Rounds of the same application, and applications of the same continuity family, are not
independent: they share the claims, the examiner and the applicant. If we resampled single checkpoints, one big
family would look like many independent cases and the interval would be too narrow. So we resample whole families
with replacement and keep all their checkpoints together 

Worked example. Three families: A has 3 checkpoints, B has 1, C has 2. One bootstrap draw might be {A, A, C}:
the resampled data set then holds A's 3 checkpoints twice and C's 2 once (8 rows). We compute the metric on those
rows, repeat 1,000 times, and report the 2.5% and 97.5% percentiles.

Implementation: a draw is a vector of family weights w (how many times each family was drawn). Any metric that is
a ratio of sums (signed gap, Brier, log loss, prevalence, and ECE through per-bin sums) is then
   sum_f w_f * (family sum) / sum_f w_f * (family count),
so all draws are one matrix product. AUROC needs ranks, so it loops over draws with repeated rows.
"""
from __future__ import annotations

import numpy as np

from .metrics import CLIP, N_BINS, auroc, bin_index
from .params import BOOT_B, CI, SEED


class FamilyBootstrap:
    def __init__(self, families, B: int = BOOT_B, seed: int = SEED):
        fam = np.asarray(families)
        self.codes, self.fam_idx = np.unique(fam, return_inverse=True)
        self.F = len(self.codes)
        rng = np.random.default_rng(seed)
        self.W = rng.multinomial(self.F, np.full(self.F, 1.0 / self.F), size=B).astype(float)  # B x F
        self.B = B

    # -- family-level sums
    def _fsum(self, x, mask=None):
        x = np.asarray(x, float)
        if mask is not None:
            return np.bincount(self.fam_idx[mask], weights=x[mask], minlength=self.F)
        return np.bincount(self.fam_idx, weights=x, minlength=self.F)

    def _ratio(self, num, den):
        a, b = self.W @ num, self.W @ den
        with np.errstate(invalid="ignore", divide="ignore"):
            return np.where(b > 0, a / b, np.nan)

    def mean_stat(self, x, mask=None):
        """Bootstrap distribution of mean(x) (within mask)."""
        ones = np.ones(len(x))
        return self._ratio(self._fsum(x, mask), self._fsum(ones, mask))

    def gap(self, p, y, mask=None):
        return self.mean_stat(np.asarray(p) - np.asarray(y), mask)

    def brier(self, p, y, mask=None):
        return self.mean_stat((np.asarray(p) - np.asarray(y)) ** 2, mask)

    def log_loss(self, p, y, mask=None):
        p = np.clip(np.asarray(p, float), CLIP, 1 - CLIP)
        y = np.asarray(y, float)
        return self.mean_stat(-(y * np.log(p) + (1 - y) * np.log(1 - p)), mask)

    def prevalence(self, y, mask=None):
        return self.mean_stat(y, mask)

    def ece(self, p, y, n_bins=N_BINS, mask=None, strategy="uniform"):
        p, y = np.asarray(p, float), np.asarray(y, float)
        idx, edges = bin_index(p, n_bins, strategy)
        k = len(edges) - 1
        m = np.ones(len(p), bool) if mask is None else mask
        # per family x bin sums -> F*k vectors
        key = self.fam_idx[m] * k + idx[m]
        cnt = np.bincount(key, minlength=self.F * k).reshape(self.F, k)
        sp = np.bincount(key, weights=p[m], minlength=self.F * k).reshape(self.F, k)
        sy = np.bincount(key, weights=y[m], minlength=self.F * k).reshape(self.F, k)
        C, P, Y = self.W @ cnt, self.W @ sp, self.W @ sy          # B x k
        n = C.sum(1)
        with np.errstate(invalid="ignore", divide="ignore"):
            return np.where(n > 0, np.abs(Y - P).sum(1) / n, np.nan)

    def auroc(self, p, y, mask=None):
        """Weighted Mann-Whitney AUROC per draw (exact, ties count 1/2), no sklearn loop.

        For one draw, each row carries the weight of its family. With predictions grouped by distinct value:
        AUROC = sum_v Pos_v * (Neg_below_v + Neg_v / 2) / (sum Pos * sum Neg)."""
        p, y = np.asarray(p, float), np.asarray(y, float)
        m = np.ones(len(p), bool) if mask is None else mask
        fi, pp, yy = self.fam_idx[m], p[m], y[m]
        uv, uidx = np.unique(pp, return_inverse=True)
        U = len(uv)
        out = np.full(self.B, np.nan)
        for b in range(self.B):
            w = self.W[b][fi]
            P = np.bincount(uidx, weights=w * yy, minlength=U)
            N = np.bincount(uidx, weights=w * (1 - yy), minlength=U)
            tp, tn = P.sum(), N.sum()
            if tp > 0 and tn > 0:
                below = np.cumsum(N) - N
                out[b] = float(np.sum(P * (below + 0.5 * N)) / (tp * tn))
        return out


def interval(draws, ci: float = CI):
    d = np.asarray(draws, float)
    d = d[~np.isnan(d)]
    if len(d) == 0:
        return (np.nan, np.nan)
    a = (1 - ci) / 2
    return (float(np.quantile(d, a)), float(np.quantile(d, 1 - a)))


def metric_draws(bs: FamilyBootstrap, metric: str, p, y, mask=None):
    if metric == "ece":
        return bs.ece(p, y, mask=mask)
    if metric == "gap":
        return bs.gap(p, y, mask)
    if metric == "brier":
        return bs.brier(p, y, mask)
    if metric == "log_loss":
        return bs.log_loss(p, y, mask)
    if metric == "auroc":
        return bs.auroc(p, y, mask)
    if metric == "prevalence":
        return bs.prevalence(y, mask)
    raise ValueError(metric)
