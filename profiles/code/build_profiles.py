"""Examiner profiles.

    python profiles/code/build_profiles.py

For each checkpoint, count the earlier outcomes of the same examiner and of the same art unit.
Only outcomes mailed before the checkpoint date count, and episodes of the same family are left out.
The examiner rate itself is computed in models/, where its shrinkage strength (lambda) is tuned.
Checkpoints are then grouped into history tiers by how many earlier outcomes the examiner has.
Each examiner also gets one examiner group (G0-G5) from the examiner's decisions mailed before 2015-01-01; it is a
dashboard filter only, never a model input.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from vml import params  # noqa: E402
from vml.common import log, need, write_json, write_manifest  # noqa: E402
from vml.paths import EPISODES_TARGET, stage_dir  # noqa: E402

STAGE = "profiles"
MAX_SOURCES = 25


def make_tiers(train_n: np.ndarray, dev_n: np.ndarray, dev_fam: np.ndarray):
    """Cut training history at its tertiles, then merge tiers until each has enough dev families."""
    pos = train_n[train_n > 0]
    q = np.unique(np.floor(np.quantile(pos, [1 / 3, 2 / 3])).astype(int)) if len(pos) else np.array([], int)
    # tier upper bounds (inclusive): [0, q1, q2, inf]
    uppers = [0] + [int(v) for v in q if v > 0] + [10 ** 9]

    def assign(n, ups):
        return np.searchsorted(np.array(ups), n, side="left")

    def dev_fams(ups):
        t = assign(dev_n, ups)
        return [len(np.unique(dev_fam[t == k])) for k in range(len(ups))]

    ups = list(dict.fromkeys(uppers))
    while len(ups) > 1:
        f = dev_fams(ups)
        k = int(np.argmin(f))
        if f[k] >= params.TIER_MIN_DEV_FAMILIES:
            break
        # merge tier k with its smaller neighbour
        if k == 0:
            j = 1
        elif k == len(ups) - 1:
            j = k - 1
        else:
            j = k - 1 if f[k - 1] <= f[k + 1] else k + 1
        lo, hi = min(k, j), max(k, j)
        ups = ups[:lo] + [ups[hi]] + ups[hi + 1:]
    labels, prev = [], -1
    for u in ups:
        if u == 0:
            labels.append("0 (fallback)")
        elif u >= 10 ** 9:
            labels.append(f"{prev + 1}+")
        else:
            labels.append(f"{prev + 1}–{u}" if prev + 1 != u else f"{u}")
        prev = u
    return ups, labels, dev_fams(ups)


def examiner_groups(f: pd.DataFrame, pool: pd.DataFrame):
    """ONE group per examiner from decisions mailed before params.EXGROUP_CUTOFF; plus each examiner's full record."""
    before = pool[pool["next_date"] < params.EXGROUP_CUTOFF].groupby("examiner_id")["y"].agg(["sum", "count"])
    ok = before[before["count"] >= params.EXGROUP_MIN_N]
    k = params.EXGROUP_K
    cuts = [float(v) for v in np.quantile((ok["sum"] / ok["count"]).to_numpy(), [i / k for i in range(1, k)])]
    edges = [0.0] + cuts + [1.0]
    labels = {0: f"G0: fewer than {params.EXGROUP_MIN_N} decisions before {params.EXGROUP_CUTOFF[:4]}"}
    for i in range(1, k + 1):
        lo, hi = edges[i - 1], edges[i]
        labels[i] = (f"G{i}: under {hi:.0%} allowed" if i == 1 else
                     f"G{i}: {lo:.0%} or more allowed" if i == k else f"G{i}: {lo:.0%}–{hi:.0%} allowed")
    rate = before["sum"] / before["count"]
    grp = pd.Series(np.where(before["count"] < params.EXGROUP_MIN_N, 0,
                             1 + np.searchsorted(np.array(cuts), rate.to_numpy(), side="right")), index=before.index)
    g_row = f["examiner_id"].map(grp).fillna(0).astype(int).to_numpy()
    n_row = f["examiner_id"].map(before["count"]).fillna(0).astype(int).to_numpy()
    r_row = f["examiner_id"].map(rate).to_numpy()
    full = pool.groupby("examiner_id").agg(decisions=("y", "size"), allowances=("y", "sum"),
                                           first=("next_date", "min"), last=("next_date", "max"))
    au = pool.groupby("examiner_id")["art_unit_today"].agg(lambda v: v.value_counts().index[0])
    examiners = {}
    for e in sorted(set(f["examiner_id"]) | set(full.index)):
        rec = {"group": int(grp.get(e, 0)), "before_decisions": int(before["count"].get(e, 0)),
               "before_allowances": int(before["sum"].get(e, 0))}
        if e in full.index:
            r = full.loc[e]
            rec.update({"full_decisions": int(r.decisions), "full_allowances": int(r.allowances),
                        "first": r["first"], "last": r["last"], "art_unit": au.get(e)})
        examiners[e] = rec
    meta = {"cutoff": params.EXGROUP_CUTOFF, "min_decisions": params.EXGROUP_MIN_N, "cuts": cuts, "labels": labels,
            "examiners": examiners,
            "rule": "one group per examiner from decisions mailed before %s; cut points = quintiles of those rates "
                    "(examiners with >= %d decisions); full record = all decisions in the data (examiner card only)"
                    % (params.EXGROUP_CUTOFF, params.EXGROUP_MIN_N)}
    return g_row, n_row, r_row, meta


def main():
    out = stage_dir(STAGE)
    feat_csv = need(stage_dir("features") / "features.csv", "features/code/build_features.py")
    f = pd.read_csv(feat_csv, dtype={"family_root": str, "app_id": str, "art_unit": str})
    # reference pool: resolved episodes whose examiner is verified
    pool = pd.read_csv(EPISODES_TARGET, dtype=str)
    pool["y"] = pool["y_allowance"].astype(int)
    if params.PROFILE_POOL_VERIFIED_ONLY:
        pool = pool[pool["prior_signed"].fillna("").str.lower() == "true"]   # stored as True/true
    pool = pool[["examiner_id", "app_id", "family_root", "art_unit_today", "reply_date", "next_date", "y",
                 "next_doc_ids", "episode_id"]].copy()
    log(STAGE, f"reference pool: {len(pool)} resolved episodes")

    nd = pool["next_date"].to_numpy()
    py = pool["y"].to_numpy()
    pfam = pool["family_root"].to_numpy()
    pex = pool["examiner_id"].to_numpy()
    pau = pool["art_unit_today"].to_numpy()

    # count the history known before each checkpoint
    rows, sources, violations = [], {}, 0
    by_ex = {k: v.index.to_numpy() for k, v in pool.reset_index(drop=True).groupby("examiner_id")}
    by_au = {k: v.index.to_numpy() for k, v in pool.reset_index(drop=True).groupby("art_unit_today")}
    pool = pool.reset_index(drop=True)
    for r in f.itertuples(index=False):
        t, fam = r.reply_date, r.family_root
        known = (nd < t) & (pfam != fam)
        s_g, n_g = py[known].sum(), known.sum()
        g = (s_g + 0.5) / (n_g + 1)
        ia = by_au.get(r.art_unit, np.array([], int))
        ka = ia[known[ia]]
        s_au, n_au = py[ka].sum(), len(ka)
        a_au = (s_au + params.AU_PRIOR_KAPPA * g) / (n_au + params.AU_PRIOR_KAPPA)
        ie = by_ex.get(r.examiner_id, np.array([], int))
        ke = ie[known[ie]]
        s_e, n_e = py[ke].sum(), len(ke)
        rows.append((r.episode_id, int(s_e), int(n_e), int(s_au), int(n_au), float(g), float(a_au)))
        if r.block in ("dev", "test"):
            src = pool.loc[ke].sort_values("next_date", ascending=False).head(MAX_SOURCES)
            violations += int((src["next_date"] >= t).sum())
            sources[r.episode_id] = [[s.app_id, s.reply_date, s.next_date, int(s.y), s.next_doc_ids]
                                     for s in src.itertuples(index=False)]
    p = pd.DataFrame(rows, columns=["episode_id", "prof_s", "prof_n", "au_s", "au_n", "glob_rate", "au_rate"])
    f = f.merge(p, on="episode_id", how="left", validate="one_to_one")

    # history tiers
    tr = f[(f.block == "train") & (f.primary == 1)]
    dv = f[(f.block == "dev") & (f.primary == 1)]
    ups, labels, dev_f = make_tiers(tr.prof_n.to_numpy(), dv.prof_n.to_numpy(), dv.family_root.to_numpy())
    f["hist_tier"] = np.searchsorted(np.array(ups), f["prof_n"].to_numpy(), side="left")
    # save
    f["ex_group"], f["ex_n_before"], f["ex_rate_before"], gmeta = examiner_groups(f, pool)
    f[["episode_id", "prof_s", "prof_n", "au_s", "au_n", "glob_rate", "au_rate", "hist_tier",
       "ex_group", "ex_n_before", "ex_rate_before"]].to_csv(out / "profiles.csv", index=False)
    write_json(out / "examiner_groups.json", gmeta)
    write_json(out / "tiers.json", {"upper_bounds_inclusive": ups, "labels": labels, "dev_families": dev_f,
                                    "rule": "tier 0 = no history; tertiles of positive training history; "
                                            "merge until >= %d dev families" % params.TIER_MIN_DEV_FAMILIES})
    write_json(out / "profile_sources.json", {"columns": ["app_id", "reply_date", "outcome_date", "allowance",
                                                          "outcome_doc_ids"], "sources": sources})
    summ = {"pool_size": len(pool), "leakage_violations": violations,
            "history_n_by_block": f.groupby("block").prof_n.describe().round(1).to_dict("index"),
            "tiers": dict(zip(labels, dev_f)),
            "examiner_groups_rows": {f"{b} G{g}": int(n) for (b, g), n in
                                     f.groupby(["block", "ex_group"]).size().items()}}
    write_json(out / "profiles_summary.json", summ)
    write_manifest(STAGE, {"features": feat_csv, "episodes_target": EPISODES_TARGET},
                   ["profiles.csv", "tiers.json", "examiner_groups.json", "profile_sources.json", "profiles_summary.json"],
                   {"leakage_violations": violations})
    log(STAGE, f"tiers {labels} with dev families {dev_f}; leakage violations: {violations}")


if __name__ == "__main__":
    main()
