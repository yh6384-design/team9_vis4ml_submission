"""The flagging procedure: groups described by at most two simple conditions, e.g. "TC 2800 and round >= 2".
Words: predicted allowance, real allowance, gap = predicted - real, group vs full population.

Pipeline :

1. Groups
   a. every single condition and every pair of conditions on different attributes, over tech center / art unit,
      examiner history, round, RCE, letter answered and rejection grounds (§101 / §102 / §103 / §112 / double
      patenting) = params.SLICE_ATTRS. Examiner group is NOT used (dashboard filter only);
   b. plus the leaves of a depth-2 tree that predicts (predicted allowance - outcome) from the same attributes:
      each leaf is a group where the model is unusually high or low, written as <= 2 conditions.
2. Size: >= 100 distinct families in 2014 part A AND in part B.
3. The two tests (Slice Finder: high error alone is not a finding), on part A, per model:
      gap_diff = group gap - full population gap
      (i)  its 95% CI (family bootstrap) does not include 0     -> not just noise
      (ii) |gap_diff| >= 0.05 (5 points)                        -> big enough to matter
   A group passes if both hold for at least one of the four learned models.
   Why gap_diff and not the group gap alone: the real allowance rises from 38% (train) to ~50% (2014), so almost
   every group has a negative gap in 2014. Subtracting the full population gap removes that shared part.
4. Rank the groups that pass by their largest ECE among the four learned models; the top five are the
   flagged groups ⚑1-⚑5 (⚑ = "look here"). Same data -> same five.

Worked example (an eligible group, "history >= 6 and no §102 rejection", LR off, 2014 part A): group 195 cases,
predicted allowance 51.3%, real allowance 62.1%, gap -10.7 points; full population 467 cases, gap -4.1; gap_diff
-6.6, 95% CI -11.1 to -2.0 -> both tests pass.
"""
from __future__ import annotations

import itertools
import json

import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeRegressor

from . import params
from .metrics import ece as ece_fn

# attribute -> (kind, display column, nice name)
ATTR_INFO = {
    "tc": ("cat", "Technology", "TC"),
    "art_unit": ("cat", "Technology", "AU"),
    "ex_group": ("cat", "Examiner", "examiner group"),
    "hist_tier": ("ord", "Examiner", "history"),
    "round_c": ("ord", "Stage", "round"),
    "rce": ("bin", "Stage", "RCE"),
    "prior_type": ("cat", "Stage", "letter answered"),
    "g101": ("bin", "Ground", "§101"),
    "g102": ("bin", "Ground", "§102"),
    "g103": ("bin", "Ground", "§103"),
    "g112": ("bin", "Ground", "§112"),
    "g_dp": ("bin", "Ground", "double-patenting"),
}
# yes / no wording of the 0/1 attributes
BIN_TEXT = {"rce": ("no RCE", "RCE filed")}
DISPLAY_COLUMNS = ["Technology", "Examiner", "Stage", "Ground"]
PRIOR_TYPE_TEXT = {"nonfinal_rejection": "non-final rejection", "final_rejection": "final rejection",
                   "advisory_action": "advisory action"}


# ------------------------------------------------------------------ predicates and rules
def pred_label(attr, op, value, vocab=None):
    kind, _, name = ATTR_INFO[attr]
    if kind == "bin":
        yes = (value == 1) == (op == "==")
        if attr in BIN_TEXT:
            return BIN_TEXT[attr][int(yes)]
        return f"{name} rejection" if yes else f"no {name} rejection"
    key = attr + (op if op in (">=", "<=") else "")
    shown = (vocab or {}).get(key, (vocab or {}).get(attr, {})).get(value, value)
    if op == "==":
        return f"{name} = {shown}"
    if op == "!=":
        return f"{name} ≠ {shown}"
    return f"{name} {op.replace('>=', '≥').replace('<=', '≤')} {shown}"


def rule_id(preds):
    return " & ".join(f"{a}{o}{v}" for a, o, v in sorted(preds, key=lambda t: (t[0], t[1], str(t[2]))))


def rule_mask(df: pd.DataFrame, preds) -> np.ndarray:
    m = np.ones(len(df), bool)
    for a, o, v in preds:
        col = df[a].to_numpy()
        if o == "==":
            m &= col == v
        elif o == "!=":
            m &= col != v
        elif o == ">=":
            m &= col >= v
        elif o == "<=":
            m &= col <= v
        else:
            raise ValueError(o)
    return m


def rule_record(preds, source, vocab=None):
    cols = {c: [] for c in DISPLAY_COLUMNS}
    for a, o, v in preds:
        cols[ATTR_INFO[a][1]].append(pred_label(a, o, v, vocab))
    return {"rule_id": rule_id(preds),
            "preds": [{"attr": a, "op": o, "value": (int(v) if isinstance(v, (int, np.integer)) else v)}
                      for a, o, v in preds],
            "label": " and ".join(pred_label(a, o, v, vocab) for a, o, v in preds),
            "columns": {c: "; ".join(x) for c, x in cols.items()},
            "n_preds": len(preds), "source": source}


def single_predicates(df: pd.DataFrame, attrs=params.SLICE_ATTRS):
    out = []
    for a in attrs:
        if a not in df.columns or df[a].isna().all():
            continue
        kind = ATTR_INFO[a][0]
        vals = sorted(df[a].dropna().unique().tolist())
        if kind == "bin":
            out += [(a, "==", int(v)) for v in vals]
        elif kind == "cat":
            out += [(a, "==", v) for v in vals]
        else:
            vals = [int(v) for v in vals]
            out += [(a, "==", v) for v in vals]
            out += [(a, ">=", v) for v in vals[1:-1]] if len(vals) > 2 else []
            out += [(a, "<=", v) for v in vals[1:-1]] if len(vals) > 2 else []
    return out


def families_in(df, mask):
    return int(df.loc[mask, "family_root"].nunique())


def enumerate_rules(search: pd.DataFrame, assess: pd.DataFrame | None, min_fam=params.SLICE_MIN_FAMILIES):
    """Singles with enough support in both parts, then pairs of those on different attributes."""
    singles = []
    for pr in single_predicates(search):
        ms = rule_mask(search, [pr])
        if families_in(search, ms) < min_fam:
            continue
        if assess is not None and families_in(assess, rule_mask(assess, [pr])) < min_fam:
            continue
        singles.append(pr)
    rules = [[s] for s in singles]
    for a, b in itertools.combinations(singles, 2):
        if a[0] == b[0]:
            continue
        rules.append([a, b])
    return rules


def tree_rules(search: pd.DataFrame, model_cols, depth=params.RESIDUAL_TREE_DEPTH,
               min_leaf=params.RESIDUAL_TREE_MIN_LEAF, seed=params.SEED):
    """Leaves of a depth-2 regression tree on (p - y), one tree per model, written as <= 2 predicates."""
    feats, spec = [], []
    for a in params.SLICE_ATTRS:
        if a not in search.columns or search[a].isna().all():
            continue
        kind = ATTR_INFO[a][0]
        if kind == "cat":
            if a == "art_unit":
                continue            # 170+ dummies would make the tree pick tiny art units; TC covers technology
            for v in sorted(search[a].dropna().unique()):
                feats.append((search[a] == v).astype(float).to_numpy())
                spec.append((a, "cat", v))
        else:
            feats.append(search[a].astype(float).to_numpy())
            spec.append((a, kind, None))
    X = np.column_stack(feats)
    out = []
    for mc in model_cols:
        r = (search[mc] - search["y"]).to_numpy()
        t = DecisionTreeRegressor(max_depth=depth, min_samples_leaf=min_leaf, random_state=seed).fit(X, r)
        tr = t.tree_

        def walk(node, path):
            if tr.children_left[node] == -1:
                if path:
                    out.append(path)
                return
            j, th = tr.feature[node], tr.threshold[node]
            a, kind, v = spec[j]
            if kind == "cat":
                left, right = (a, "!=", v), (a, "==", v)
            elif kind == "bin":
                left, right = (a, "==", 0), (a, "==", 1)
            else:
                left, right = (a, "<=", int(np.floor(th))), (a, ">=", int(np.floor(th)) + 1)
            walk(tr.children_left[node], path + [left])
            walk(tr.children_right[node], path + [right])

        walk(0, [])
    # keep leaves whose two conditions are not on the same attribute twice, dedupe
    clean, seen = [], set()
    for p in out:
        p = _simplify(p)
        rid = rule_id(p)
        if rid not in seen:
            seen.add(rid)
            clean.append(p)
    return clean


def _simplify(preds):
    """Merge two bounds on the same ordinal attribute (e.g. round >= 2 & round <= 2 -> round == 2)."""
    by = {}
    for a, o, v in preds:
        by.setdefault(a, []).append((o, v))
    out = []
    for a, lst in by.items():
        ops = dict(lst) if len(lst) > 1 else None
        if ops and ">=" in ops and "<=" in ops and ops[">="] == ops["<="]:
            out.append((a, "==", ops[">="]))
        else:
            out += [(a, o, v) for o, v in lst]
    return out


# ------------------------------------------------------------------ statistics for many rules at once
class RuleStats:
    """Point statistics and family-bootstrap tests for many rules on one data part."""

    def __init__(self, df: pd.DataFrame, model_cols, B=params.SLICE_BOOT_B, seed=params.SEED):
        self.df, self.model_cols = df, list(model_cols)
        self.fam_codes, self.fam = np.unique(df["family_root"].to_numpy(), return_inverse=True)
        self.F = len(self.fam_codes)
        rng = np.random.default_rng(seed)
        self.W = rng.multinomial(self.F, np.full(self.F, 1 / self.F), size=B).astype(float) if B else None
        self.y = df["y"].to_numpy(float)

    def masks(self, rules):
        return np.column_stack([rule_mask(self.df, r) for r in rules]) if rules else np.zeros((len(self.df), 0), bool)

    def table(self, rules, with_tests=True):
        M = self.masks(rules)
        rows = []
        n = M.sum(0)
        famcount = np.array([len(np.unique(self.fam[M[:, j]])) for j in range(M.shape[1])])
        prev = (self.y[:, None] * M).sum(0) / np.maximum(n, 1)
        diffs, los, his = {}, {}, {}
        for mc in self.model_cols:
            r = self.df[mc].to_numpy(float) - self.y
            g_all = r.mean()
            g = (r[:, None] * M).sum(0) / np.maximum(n, 1)
            diffs[mc] = g - g_all
            if with_tests and self.W is not None:
                S = np.column_stack([np.bincount(self.fam[M[:, j]], weights=r[M[:, j]], minlength=self.F)
                                     for j in range(M.shape[1])])
                N = np.column_stack([np.bincount(self.fam[M[:, j]], minlength=self.F) for j in range(M.shape[1])])
                s_all = np.bincount(self.fam, weights=r, minlength=self.F)
                n_all = np.bincount(self.fam, minlength=self.F).astype(float)
                with np.errstate(invalid="ignore", divide="ignore"):
                    G = (self.W @ S) / (self.W @ N)
                    Ga = (self.W @ s_all) / (self.W @ n_all)
                D = G - Ga[:, None]
                los[mc] = np.nanquantile(D, (1 - params.CI) / 2, axis=0)
                his[mc] = np.nanquantile(D, 1 - (1 - params.CI) / 2, axis=0)
        for j in range(M.shape[1]):
            row = {"n": int(n[j]), "n_families": int(famcount[j]), "prevalence": float(prev[j]),
                   "single_class": bool(prev[j] in (0.0, 1.0))}
            m = M[:, j]
            passes = []
            for mc in self.model_cols:
                p = self.df[mc].to_numpy(float)[m]
                row[f"ece_{mc}"] = ece_fn(p, self.y[m]) if m.any() else np.nan
                row[f"gap_{mc}"] = float(np.mean(p - self.y[m])) if m.any() else np.nan
                row[f"gapdiff_{mc}"] = float(diffs[mc][j])
                if with_tests and self.W is not None:
                    lo, hi = float(los[mc][j]), float(his[mc][j])
                    ok = (lo > 0 or hi < 0) and abs(diffs[mc][j]) >= params.SLICE_EFFECT_MIN
                    row[f"gapdiff_lo_{mc}"], row[f"gapdiff_hi_{mc}"], row[f"pass_{mc}"] = lo, hi, bool(ok)
                    passes.append(ok)
            row["ece_max"] = max(row[f"ece_{mc}"] for mc in self.model_cols)
            row["ece_max_model"] = max(self.model_cols, key=lambda mc: row[f"ece_{mc}"])
            if with_tests and self.W is not None:
                row["passes_tests"] = bool(any(passes))
            rows.append(row)
        return pd.DataFrame(rows)


def search(search_df, assess_df, model_cols, vocab=None, B=params.SLICE_BOOT_B, seed=params.SEED,
           top_k=params.SLICE_TOP_K, min_fam=params.SLICE_MIN_FAMILIES, include_tree=True):
    """Full slice search. Returns (ranked candidate table, list of rules aligned with the table rows)."""
    enum = enumerate_rules(search_df, assess_df, min_fam)
    tree = tree_rules(search_df, model_cols, seed=seed) if include_tree else []
    rules, src, seen = [], [], set()
    for r, s in [(r, "enumerated") for r in enum] + [(r, "residual_tree") for r in tree]:
        rid = rule_id(r)
        if rid in seen:
            continue
        seen.add(rid)
        rules.append(r)
        src.append(s)
    if not rules:
        return pd.DataFrame(), []
    st = RuleStats(search_df, model_cols, B=B, seed=seed).table(rules)
    meta = pd.DataFrame([rule_record(r, s, vocab) for r, s in zip(rules, src)])
    meta["preds"] = meta["preds"].map(lambda v: json.dumps(v, ensure_ascii=False))      # stored as JSON text so
    meta["columns"] = meta["columns"].map(lambda v: json.dumps(v, ensure_ascii=False))  # CSV / JS read it the same way
    tab = pd.concat([meta, st.add_prefix("search_").rename(columns={"search_passes_tests": "passes_tests"})], axis=1)
    if assess_df is not None:
        a_fam = [families_in(assess_df, rule_mask(assess_df, r)) for r in rules]
        tab["assess_n_families"] = a_fam
    else:
        tab["assess_n_families"] = tab["search_n_families"]
    tab["support_ok"] = (tab["search_n_families"] >= min_fam) & (tab["assess_n_families"] >= min_fam)
    tab["eligible"] = tab["support_ok"] & tab["passes_tests"]
    tab = tab.sort_values(["eligible", "search_ece_max"], ascending=[False, False]).reset_index(drop=True)
    order = {rule_id(r): r for r in rules}
    # Two differently written rules can select exactly the same cases (e.g. "round = 1" and "round <= 1").
    # Among eligible groups with the same 2014 part A cases, only the best-ranked one is kept for ranking.
    dup_of, seen = [""] * len(tab), {}
    for i in np.flatnonzero(tab["eligible"].to_numpy()):
        rid = tab.at[i, "rule_id"]
        key = rule_mask(search_df, order[rid]).tobytes()
        if key in seen:
            dup_of[i] = seen[key]
        else:
            seen[key] = rid
    tab["duplicate_of"] = dup_of
    distinct = tab["eligible"] & (tab["duplicate_of"] == "")
    tab["rank"] = np.where(distinct, distinct.cumsum(), np.nan)
    tab["top_k"] = distinct & (tab["rank"] <= top_k)
    return tab, [order[rid] for rid in tab["rule_id"]]


def preds_from_record(rec):
    pr = rec["preds"]
    if isinstance(pr, str):
        pr = json.loads(pr)
    return [(d["attr"], d["op"], d["value"]) for d in pr]


def jaccard(a: np.ndarray, b: np.ndarray) -> float:
    u = np.logical_or(a, b).sum()
    return float(np.logical_and(a, b).sum() / u) if u else 0.0


def vocab_from_tiers_file(path):
    """Text for each value. For >= / <= on history tiers we show the tier's bound in earlier cases, e.g.
    tiers 0-5 / 6-13 / 14+:  hist_tier >= 1 -> "history ≥ 6",  hist_tier <= 1 -> "history ≤ 13".
    Examiner-group names come from examiner_groups.json in the same folder (written by the profiles stage)."""
    import json as _json
    from pathlib import Path as _Path
    with open(path) as f:
        t = _json.load(f)
    gpath = _Path(path).with_name("examiner_groups.json")
    groups = {}
    if gpath.exists():
        with open(gpath) as f:
            groups = {int(k): v.split(":")[0] for k, v in _json.load(f)["labels"].items()}
    ups = t["upper_bounds_inclusive"]
    lows = [0] + [u + 1 for u in ups[:-1]]
    return {"ex_group": groups, "prior_type": PRIOR_TYPE_TEXT,
            "hist_tier": {i: lab for i, lab in enumerate(t["labels"])},
            "hist_tier>=": {i: str(lows[i]) for i in range(len(ups))},
            "hist_tier<=": {i: (str(ups[i]) if ups[i] < 10 ** 9 else "any") for i in range(len(ups))},
            "round_c": {1: "1", 2: "2", 3: "3+"}, "round_c>=": {1: "1", 2: "2", 3: "3"},
            "round_c<=": {1: "1", 2: "2", 3: "3+"}}
