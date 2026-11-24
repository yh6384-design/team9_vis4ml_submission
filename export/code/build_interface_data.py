"""Export everything the dashboard needs into one JavaScript file.

    python export/code/build_interface_data.py [--synthetic]

Writes interface/data/vml_data.js (window.VML = {...}) and a copy in VML_OUT/export/. A .js file (not .json) lets the
dashboard open straight from disk with a double click, without a web server.

Contents: meta (models, colors, periods, parameters, run dates), cases (every 2014 and 2015-2017 case with the
features a user can filter on, the predicted allowances and the flagged groups it belongs to), examiner history
sources, the candidate and flagged groups with their re-check, learned curves, measures and the Experiment 2 table.
--synthetic also writes the practice copy with a known answer (vml_data_synthetic.js, index_practice.html).
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from vml import params  # noqa: E402
from vml.common import NpEncoder, log, need, read_json, write_manifest  # noqa: E402
from vml.paths import REPO, stage_dir  # noqa: E402

STAGE = "export"
COLORS = {"base": "#999999", "lr_off": "#56B4E9", "lr_on": "#0072B2", "gbt_off": "#F0A35E", "gbt_on": "#D55E00"}


def run_id(stage):
    p = stage_dir(stage) / "_run.json"
    if p.exists():
        r = read_json(p)
        return {"finished_utc": r["finished_utc"], "git_commit": r["git_commit"]}   # no user name, no local path on the page
    return None


def source_files():
    """Footer of the page: the files (inside the run folder VML_OUT) that each part of the page is built from."""
    root = stage_dir("models").parent
    items = [
        ["Cases and predicted allowances (Visualizations 1, 6)", ["models/predictions.csv"], "built from features/features.csv"],
        ["Examiner history and examiner groups (filters, examiner card)", ["profiles/profile_sources.json", "profiles/examiner_groups.json", "profiles/tiers.json"]],
        ["Full population measures and learned curves (Visualizations 2–3)", ["metrics/metrics_overall.csv", "metrics/learned_curves.json"]],
        ["Flagged groups ⚑1–⚑5 (Visualizations 4–5)", ["slices/candidates.csv", "slices/frozen_top5.json", "slices/frozen_assessment.csv",
                                  "slices/slice_curves.json"]],
        ["Experiment 2 (profile off vs on, same 2015–2017 cases; Visualization 3 Answer)", ["e2/e2_paired.csv"]],
    ]
    for it in items:
        it[1] = [f for f in it[1] if (root / f).exists()]
    r = run_id("models")
    return {"page": "interface/data/vml_data.js", "made": (r or {}).get("finished_utc", "")[:10],
            "items": [it for it in items if it[1]]}


def r4(x):
    return None if pd.isna(x) else round(float(x), 4)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--synthetic", action="store_true",
                    help="also write the practice copy with a known answer for walkthrough task T0 (one group's predicted allowance raised on purpose)")
    a = ap.parse_args()
    pred_csv = need(stage_dir("models") / "predictions.csv", "models/code/train_models.py")
    df = pd.read_csv(pred_csv, dtype={"family_root": str, "art_unit": str, "tc": str, "app_id": str})
    build(df, pred_csv, synthetic=False)
    if a.synthetic:
        build(df, pred_csv, synthetic=True)


def make_synthetic(df: pd.DataFrame):
    """Practice copy with a known answer, for walkthrough task T0: outcomes drawn from q = LR-off predicted allowance
    (so every group's true gap is 0); in ONE group fixed in advance (the medium group of Experiment 3) the profile-OFF
    predicted allowance is raised by +0.75 on the log-odds scale (about +18 points at 50%); profile-ON models are left
    equal to q. The answer is written to VML_OUT/export/synthetic_answer.json only."""
    from vml.slicing import preds_from_record, rule_mask
    rng = np.random.default_rng(params.SEED + 99)
    d = df.copy()
    q = d["lr_off"].to_numpy()
    d["y"] = (rng.random(len(d)) < q).astype(int)
    plan_p = stage_dir("e3") / "e3_plan.json"
    plan = read_json(plan_p) if plan_p.exists() else []
    pick = next((p for p in plan if p["size"] == "medium"), plan[0] if plan else None)
    if pick is None:
        raise SystemExit("run e3_synthetic first (it fixes the groups chosen in advance)")
    m = rule_mask(d, preds_from_record(pick))
    z = np.log(np.clip(q, 1e-6, 1 - 1e-6) / (1 - np.clip(q, 1e-6, 1 - 1e-6)))
    dist = 1 / (1 + np.exp(-(z + 0.75)))
    for c in ("lr_off", "gbt_off"):
        d[c] = np.where(m, dist, q)
    for c in ("lr_on", "gbt_on"):
        d[c] = q
    return d, pick


def build(df: pd.DataFrame, pred_csv, synthetic: bool):
    pick = None
    if synthetic:
        df, pick = make_synthetic(df)
    tiers = read_json(need(stage_dir("profiles") / "tiers.json", "profiles"))
    sources = read_json(stage_dir("profiles") / "profile_sources.json")
    cand = pd.read_csv(need(stage_dir("slices") / "candidates.csv", "slices/code/find_slices.py"))
    frozen = read_json(stage_dir("slices") / "frozen_top5.json")
    fa = pd.read_csv(stage_dir("slices") / "frozen_assessment.csv")
    curves = read_json(stage_dir("metrics") / "learned_curves.json") if (stage_dir("metrics") / "learned_curves.json").exists() else {}
    scurves = read_json(stage_dir("slices") / "slice_curves.json") if (stage_dir("slices") / "slice_curves.json").exists() else {}
    mt = pd.read_csv(stage_dir("metrics") / "metrics_overall.csv") if (stage_dir("metrics") / "metrics_overall.csv").exists() else pd.DataFrame()
    e2 = pd.read_csv(stage_dir("e2") / "e2_paired.csv") if (stage_dir("e2") / "e2_paired.csv").exists() else pd.DataFrame()
    if synthetic:   # re-run the same flagging procedure on the practice copy so Visualizations 4/5 match it; no curves / tables
        from vml.slicing import search
        from vml.slicing import vocab_from_tiers_file
        prim = df[df.primary == 1]
        s_df = prim[prim.part == "dev_search"].reset_index(drop=True)
        a_df = prim[prim.part == "dev_assess"].reset_index(drop=True)
        cand, _ = search(s_df, a_df, list(params.LEARNED_MODELS), vocab=vocab_from_tiers_file(stage_dir("profiles") / "tiers.json"))
        top = cand[cand.top_k]
        frozen = {"rule_ids": top.rule_id.tolist(), "slices": [{"rule_id": r.rule_id, "label": r.label,
                  "preds": json.loads(r.preds)} for r in top.itertuples()], "synthetic": True}
        fa = pd.DataFrame()
        curves, scurves, mt, e2 = {}, {}, pd.DataFrame(), pd.DataFrame()

    from vml.slicing import PRIOR_TYPE_TEXT, preds_from_record, rule_mask
    gpath = stage_dir("profiles") / "examiner_groups.json"
    groups = read_json(gpath) if gpath.exists() else {"labels": {}}
    # which of the five flagged groups each case belongs to (⚑1-⚑5), for the ⚑ column in Visualization 6
    star_of = {}
    for rank, srec in enumerate(frozen.get("slices", []), start=1):
        m = rule_mask(df, preds_from_record(srec))
        for eid in df.loc[m, "episode_id"]:
            star_of.setdefault(eid, []).append(rank)
    fam_codes = {f: i for i, f in enumerate(sorted(df.family_root.unique()))}
    cases = []
    for r in df.itertuples(index=False):
        c = {"id": r.episode_id, "fam": fam_codes[r.family_root], "family": r.family_root, "app": r.app_id,
             "examiner": r.examiner_id, "block": r.block, "part": r.part, "primary": int(r.primary), "y": int(r.y),
             "date": r.reply_date, "year": int(r.reply_year), "outcome_date": r.next_date, "prior_type": r.prior_type,
             "prior_date": r.prior_date, "art_unit": r.art_unit, "tc": r.tc, "round_n": int(r.round_n),
             "round_c": int(r.round_c), "rce": int(r.rce), "g101": int(r.g101), "g102": int(r.g102),
             "g103": int(r.g103), "g112": int(r.g112), "g_dp": int(r.g_dp), "filing_year": int(r.filing_year)
             if not pd.isna(r.filing_year) else None, "ex_group": int(r.ex_group), "ex_n_before": int(r.ex_n_before),
             "ex_rate_before": r4(r.ex_rate_before), "stars": star_of.get(r.episode_id, []),
             "hist_tier": int(r.hist_tier), "prof_n": int(r.prof_n),
             "prof_s": int(r.prof_s), "prof_rate": r4(r.prof_rate), "au_rate": r4(r.au_rate),
             "docs": {"prior": r.prior_doc_ids if isinstance(r.prior_doc_ids, str) else "",
                      "reply": r.reply_doc_ids if isinstance(r.reply_doc_ids, str) else "",
                      "next": r.next_doc_ids if isinstance(r.next_doc_ids, str) else "",
                      "ground_letter": r.ground_doc if isinstance(r.ground_doc, str) else ""}}
        for m in params.ALL_MODELS:
            c[m] = r4(getattr(r, m))
        cases.append(c)

    def clean_records(t: pd.DataFrame):
        t = t.copy()
        for col in t.columns:
            if t[col].dtype == object or pd.api.types.is_string_dtype(t[col]):
                t[col] = t[col].apply(lambda v: json.loads(v) if isinstance(v, str) and v[:1] in "[{" else v)
        return json.loads(t.to_json(orient="records"))

    data = {
        "meta": {
            "synthetic": synthetic,
            "title": "Can You Trust Personalized Odds? Calibration of patent-prosecution predictors",
            "models": list(params.ALL_MODELS), "learned_models": list(params.LEARNED_MODELS),
            "pairs": [list(p) for p in params.PAIRS], "labels": params.MODEL_LABEL, "short": params.MODEL_SHORT,
            "colors": COLORS, "tiers": tiers["labels"], "min_families": params.SLICE_MIN_FAMILIES,
            "ex_groups": groups.get("labels", {}), "ex_group_cutoff": groups.get("cutoff", ""),
            "examiners": groups.get("examiners", {}),   # full record (all years) + group, for the examiner card
            "ex_group_min_decisions": groups.get("min_decisions"), "prior_types": PRIOR_TYPE_TEXT,
            "view_min_cases": params.VIEW_MIN_CASES, "top_k": params.SLICE_TOP_K,
            "effect_min": params.SLICE_EFFECT_MIN, "n_bins": params.N_BINS,
            "parts": {"dev_search": "Dev 2014, search half", "dev_assess": "Dev 2014, assessment half",
                      "dev": "Dev 2014 (both halves)", "test": "Test 2015-2017"},
            "runs": {s: run_id(s) for s in ("features", "profiles", "models", "metrics", "slices", "e2", "e3")},
            "files": source_files(),   # page footer: which file each part of the page comes from
        },
        "cases": cases,
        "sources": sources,
        "slices": {"candidates": clean_records(cand), "frozen": frozen, "assessment": clean_records(fa)},
        "curves": {"all": curves, "slices": scurves},
        "metrics": json.loads(mt.to_json(orient="records")) if len(mt) else [],
        "e2": json.loads(e2.to_json(orient="records")) if len(e2) else [],
    }
    js = "window.VML = " + json.dumps(data, cls=NpEncoder, separators=(",", ":")) + ";\n"
    name = "vml_data_synthetic.js" if synthetic else "vml_data.js"
    if synthetic:
        data["meta"]["title"] = "PRACTICE COPY with a known answer (one group's predicted allowance raised on purpose)"
        data["meta"]["files"]["page"] = "interface/data/vml_data_synthetic.js"
        js = "window.VML = " + json.dumps(data, cls=NpEncoder, separators=(",", ":")) + ";\n"
    target = REPO / "interface" / "data" / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(js)
    out = stage_dir(STAGE)
    shutil.copy(target, out / name)
    if synthetic:
        html = (REPO / "interface" / "index.html").read_text()
        html = html.replace('src="data/vml_data.js"', 'src="data/vml_data_synthetic.js"').replace(
            "<h1>Can You Trust Personalized Odds?</h1>",
            '<h1 style="color:#b42318">PRACTICE COPY with a known answer</h1>')
        (REPO / "interface" / "index_practice.html").write_text(html)
        from vml.common import write_json
        # flagged groups that share >= 50% of their 2014 part A cases with the planted group (also a correct answer)
        a_df = df[(df.primary == 1) & (df.part == "dev_search")].reset_index(drop=True)
        pm = rule_mask(a_df, preds_from_record(pick))
        overlap = []
        for rank, srec in enumerate(frozen.get("slices", []), start=1):
            fm = rule_mask(a_df, preds_from_record(srec))
            jac = float((fm & pm).sum() / max((fm | pm).sum(), 1))
            if jac >= params.E3_HIT_JACCARD:
                overlap.append({"flag": rank, "label": srec["label"], "jaccard": round(jac, 2)})
        write_json(out / "synthetic_answer.json", {"planted": pick, "shift_logit": 0.75, "models": ["lr_off", "gbt_off"],
                                                   "found_in_top5": pick["rule_id"] in frozen["rule_ids"],
                                                   "overlapping_flagged_groups": overlap})
        log(STAGE, f"practice data saved to {target}; answer key in {out/'synthetic_answer.json'} (do not show participants)")
        return
    write_manifest(STAGE, {"predictions": pred_csv}, [str(target), "vml_data.js"],
                   {"cases": len(cases), "candidates": len(cand), "bytes": len(js)})
    log(STAGE, f"{len(cases)} cases, {len(cand)} candidate groups saved to {target} ({len(js) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
