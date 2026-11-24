"""Experiment 3: test of the flagging procedure on a practice copy of 2014 with a known answer.
Evidence for research question 2.

    python e3_synthetic/code/e3_planted.py            (full run, a few minutes)
    python e3_synthetic/code/e3_planted.py --quick    (3 seeds, for checking the code)

Plain-words design
  1. Start from the real 2014 cases (same rows, same features, same parts A / B).
  2. Take q = the predicted allowance of one model (E3_BASE_MODEL = LR off) and draw a new outcome for every case:
     allowed with probability q (fixed seed). The predicted allowance now matches the real allowance on average in
     every group: every group's true gap is 0. This is the "practice copy with a known answer".
  3. Known gap: pick a group S fixed in advance (small / medium / large) and move its predicted allowance up or
     down on the log-odds scale by delta (0.25, 0.5, 1.0), outcomes unchanged.
     Example: q = 0.50, delta = +0.5 -> 0.62 inside S, i.e. a true gap of about +12 points, and 0 everywhere else.
  4. Run the exact same flagging procedure as the real analysis (vml.slicing.search) on this copy.
     found (exact)    S is among the five flagged groups
     found (overlap)  a flagged group shares >= 50% of its cases with S (Jaccard)
     passed by luck   groups that pass the tests and do not overlap S (at most 5 of them are flagged)
  5. Runs with no gap (delta = 0): every group that passes the tests passes by luck (true gap 0, judged significant).
     Two different counts: groups that PASS the tests (no limit) and groups that are FLAGGED (the top 5 of those).
     Reported: how many per run, and their ECE in 2014 part B.
  6. Known gap added to the REAL predictions with the REAL outcomes: does it rise above the gaps already there?

Outputs (VML_OUT/e3/): e3_runs.csv, e3_null.csv, e3_real_perturb.csv, e3_summary.json, e3_summary.md, e3_plan.json
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from vml import params  # noqa: E402
from vml.common import log, need, write_json, write_manifest  # noqa: E402
from vml.metrics import ece, wilson  # noqa: E402
from vml.paths import stage_dir  # noqa: E402
from vml.slicing import jaccard, preds_from_record, rule_id, rule_mask, search, vocab_from_tiers_file  # noqa: E402

STAGE = "e3"
VOCAB = None   # readable condition names (e.g. "examiner history 14+"), loaded in main() from profiles/tiers.json


def logit(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def sig(z):
    return 1 / (1 + np.exp(-z))


def run_once(s_df, a_df, planted, seed, B):
    tab, rules = search(s_df, a_df, ["p"], vocab=VOCAB, B=B, seed=seed)
    if tab.empty:
        return tab, rules, {}
    el = tab[tab.eligible]
    top_ids = tab.loc[tab.top_k, "rule_id"].tolist()
    res = {"n_candidates": len(tab), "n_eligible": len(el), "top5": " | ".join(top_ids)}
    if planted is not None:
        pm = rule_mask(s_df, planted)
        pid = rule_id(planted)
        res["planted_in_candidates"] = pid in tab.rule_id.values
        res["planted_eligible"] = bool(tab.loc[tab.rule_id == pid, "eligible"].any())
        res["planted_rank"] = float(tab.loc[tab.rule_id == pid, "rank"].min()) if res["planted_in_candidates"] else np.nan
        res["hit_exact"] = pid in top_ids
        jac = {rid: jaccard(rule_mask(s_df, r), pm) for rid, r in zip(tab.rule_id, rules) if rid in set(el.rule_id)}
        res["hit_overlap"] = any(jac.get(r, 0) >= params.E3_HIT_JACCARD for r in top_ids)
        res["false_finds"] = sum(1 for r, j in jac.items() if j < params.E3_HIT_JACCARD)
    return tab, rules, res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args()
    seeds = 3 if a.quick else params.E3_SEEDS
    null_seeds = 5 if a.quick else params.E3_NULL_SEEDS
    B = params.E3_BOOT_B
    out = stage_dir(STAGE)
    global VOCAB
    tiers = stage_dir("profiles") / "tiers.json"
    VOCAB = vocab_from_tiers_file(tiers) if tiers.exists() else None
    pred_csv = need(stage_dir("models") / "predictions.csv", "models/code/train_models.py")
    cand_csv = need(stage_dir("slices") / "candidates.csv", "slices/code/find_slices.py")
    df = pd.read_csv(pred_csv, dtype={"family_root": str, "art_unit": str, "tc": str})
    df = df[(df.primary == 1) & (df.block == "dev")].reset_index(drop=True)
    is_s = (df.part == "dev_search").to_numpy() if params.DEV_SPLIT == "halves" else np.ones(len(df), bool)
    q = df[params.E3_BASE_MODEL].to_numpy()

    # ---- prespecified planted slices: 2 per support class (small / medium / large), from supported candidates
    cand = pd.read_csv(cand_csv)
    sup = cand[cand.support_ok].copy()
    sup["size"] = pd.qcut(sup.search_n_families.rank(method="first"), 3, labels=["small", "medium", "large"])
    rng = np.random.default_rng(params.SEED)
    plan = []
    for size, g in sup.groupby("size", observed=True):
        pick = g.sample(n=min(2, len(g)), random_state=params.SEED)
        for _, r in pick.iterrows():
            plan.append({"size": size, "rule_id": r.rule_id, "label": r.label, "preds": json.loads(r.preds),
                         "search_n_families": int(r.search_n_families)})
    write_json(out / "e3_plan.json", plan)
    log(STAGE, "planted slices: " + "; ".join(f"{p['size']}: {p['label']} ({p['search_n_families']} fam)" for p in plan))

    def split(d):
        return d[is_s].reset_index(drop=True), (d[~is_s].reset_index(drop=True) if params.DEV_SPLIT == "halves" else None)

    # ---- planted runs
    runs = []
    for pl, delta, sign, s in itertools.product(plan, params.E3_SHIFTS, (1, -1), range(seeds)):
        r = np.random.default_rng(params.SEED + 1000 * s)
        d = df.copy()
        d["y"] = (r.random(len(d)) < q).astype(int)
        pr = preds_from_record(pl)
        m = rule_mask(d, pr)
        d["p"] = np.where(m, sig(logit(q) + sign * delta), q)
        s_df, a_df = split(d)
        _, _, res = run_once(s_df, a_df, pr, params.SEED + s, B)
        runs.append({"size": pl["size"], "planted": pl["label"], "delta": delta, "direction": "over" if sign > 0 else "under",
                     "seed": s, **res})
    runs = pd.DataFrame(runs)
    runs.to_csv(out / "e3_runs.csv", index=False)
    log(STAGE, f"{len(runs)} planted runs done")

    # ---- null controls
    nulls, tops = [], []
    for s in range(null_seeds):
        r = np.random.default_rng(params.SEED + 7000 + s)
        d = df.copy()
        d["y"] = (r.random(len(d)) < q).astype(int)
        d["p"] = q
        s_df, a_df = split(d)
        tab, rules, res = run_once(s_df, a_df, None, params.SEED + s, B)
        top = tab[tab.top_k] if not tab.empty else tab
        assess_ece = []
        if a_df is not None:
            for rid in top.rule_id:
                rr = rules[tab.index[tab.rule_id == rid][0]]
                mm = rule_mask(a_df, rr)
                assess_ece.append(ece(a_df.p[mm], a_df.y[mm]))
        tops.append(set(top.rule_id))
        nulls.append({"seed": s, **res, "overall_ece_assess": ece(a_df.p, a_df.y) if a_df is not None else np.nan,
                      "top5_mean_ece_search": float(top.search_ece_max.mean()) if len(top) else np.nan,
                      "top5_mean_ece_assess": float(np.mean(assess_ece)) if assess_ece else np.nan})
    nulls = pd.DataFrame(nulls)
    nulls.to_csv(out / "e3_null.csv", index=False)
    jac = [len(a & b) / len(a | b) for a, b in itertools.combinations(tops, 2) if (a | b)]

    # ---- sensitivity on real labels / real predictions
    real = []
    for pl, delta, sign in itertools.product(plan, params.E3_SHIFTS, (1, -1)):
        d = df.copy()
        pr = preds_from_record(pl)
        m = rule_mask(d, pr)
        d["p"] = np.where(m, sig(logit(q) + sign * delta), q)
        s_df, a_df = split(d)
        _, _, res = run_once(s_df, a_df, pr, params.SEED, B)
        real.append({"size": pl["size"], "planted": pl["label"], "delta": delta,
                     "direction": "over" if sign > 0 else "under", **res})
    real = pd.DataFrame(real)
    real.to_csv(out / "e3_real_perturb.csv", index=False)

    # ---- summary
    rec = []
    for (size, delta), g in runs.groupby(["size", "delta"], observed=True):
        for k in ("hit_exact", "hit_overlap"):
            n, h = len(g), int(g[k].sum())
            lo, hi = wilson(h, n)
            rec.append({"size": size, "delta": delta, "measure": k, "rate": h / n, "lo": float(lo), "hi": float(hi), "runs": n})
    summ = {
        "recovery": rec,
        "null": {"runs": len(nulls), "mean_false_finds": float(nulls.n_eligible.mean()),   # groups PASSING by luck
                 "share_runs_with_any_false_find": float((nulls.n_eligible > 0).mean()),
                 "share_runs_with_no_false_find": float((nulls.n_eligible == 0).mean()),
                 "mean_flagged_by_luck": float(nulls.n_eligible.clip(upper=params.SLICE_TOP_K).mean()),   # FLAGGED (≤ 5)
                 "top5_mean_ece_search": float(nulls.top5_mean_ece_search.mean()),
                 "top5_mean_ece_assess": float(nulls.top5_mean_ece_assess.mean()),
                 "overall_ece_assess": float(nulls.overall_ece_assess.mean()),
                 "top5_jaccard_across_seeds_mean": float(np.mean(jac)) if jac else np.nan},
        "real_perturb_hit_overlap_rate": float(real.hit_overlap.mean()) if len(real) else np.nan,
        "false_finds_in_planted_runs_mean": float(runs.false_finds.mean()),
    }
    write_json(out / "e3_summary.json", summ)
    rt = pd.DataFrame(rec)
    md = ["# Experiment 3 summary: the flagging procedure on a practice copy of 2014 with a known answer", "", f"Outcomes drawn from the predicted allowance of: {params.E3_BASE_MODEL}. Runs per known-gap setting: {seeds}. Runs with no gap: {null_seeds}.",
          "", "## Known gap found (share of runs; rows = group size and log-odds shift: 0.25 / 0.5 / 1.0 = about 6 / 12 / 23 points at 50%)", "",
          rt.pivot_table(index=["size", "delta"], columns="measure", values="rate").round(2).to_markdown(), "",
          "## Runs with no gap (true gap 0 everywhere): groups that pass the tests by luck; at most 5 of them are flagged", ""] + [f"- {k}: {v:.3f}" for k, v in summ["null"].items()] + [
          "", f"Known gap added to the real 2014 data, share found (overlap): {summ['real_perturb_hit_overlap_rate']:.2f}"]
    (out / "e3_summary.md").write_text("\n".join(md))
    write_manifest(STAGE, {"predictions": pred_csv, "candidates": cand_csv}, ["e3_runs.csv", "e3_null.csv",
                   "e3_real_perturb.csv", "e3_summary.json", "e3_summary.md", "e3_plan.json"], {"quick": a.quick})
    log(STAGE, "\n" + "\n".join(md))


if __name__ == "__main__":
    main()
