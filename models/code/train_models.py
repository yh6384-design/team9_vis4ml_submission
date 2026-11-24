"""Models: a base rate, logistic regression and boosted trees, each with the examiner profile off and on.

    python models/code/train_models.py

The off and on versions use the same training cases and the same number of tuning settings.
Off = case inputs only. On = the same inputs + the examiner ID + the examiner's history known before the reply date.
An examiner never seen in training gets no ID effect.
Settings are tuned on the training block only, by forward validation over 2011, 2012 and 2013.
Predictions are made for every dev and test checkpoint.
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, OrdinalEncoder, StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from vml import params  # noqa: E402
from vml.common import log, need, write_json, write_manifest  # noqa: E402
from vml.metrics import log_loss  # noqa: E402
from vml.paths import stage_dir  # noqa: E402

STAGE = "models"
CAT = ["tc", "art_unit", "prior_type"]
NUM = ["round_n", "rce", "g101", "g102", "g103", "g112", "g_dp", "ground_text_ok", "filing_year", "elapsed_years"]
PROF = ["prof_logit", "prof_log_n", "prof_log_s", "prof_avail"]
NAME = "ex_name"            # examiner ID as a model input (profile on only); empty for unconfirmed identity


def add_profile(df: pd.DataFrame, lam: float) -> pd.DataFrame:
    """Add the profile inputs: the examiner's shrunk allowance rate and history counts."""
    d = df.copy()
    fallback = d["primary"] == 0                      # unconfirmed examiner: use the art-unit rate only
    s = np.where(fallback, 0, d["prof_s"])
    n = np.where(fallback, 0, d["prof_n"])
    rate = (s + lam * d["au_rate"]) / (n + lam)
    rate = np.clip(rate, 1e-4, 1 - 1e-4)
    d["prof_rate"] = rate
    d["prof_logit"] = np.log(rate / (1 - rate))
    d["prof_log_n"] = np.log1p(n)
    d["prof_log_s"] = np.log1p(s)
    d["prof_avail"] = (n > 0).astype(int)
    d[NAME] = np.where(fallback, np.nan, d["examiner_id"]).astype(object)
    return d


def make_model(kind: str, profile: bool, cfg: dict):
    """Logistic regression or boosted trees, with or without the profile inputs."""
    num = NUM + (PROF if profile else [])
    cat = CAT + ([NAME] if profile else [])
    if kind == "lr":
        parts = [("cat", OneHotEncoder(handle_unknown="infrequent_if_exist", min_frequency=params.ART_UNIT_MIN_FREQ,
                                       sparse_output=False), CAT)]
        if profile:   # examiner ID: unknown or unconfirmed examiner gets all ID columns 0 (no personal effect)
            parts.append(("name", make_pipeline(
                SimpleImputer(strategy="constant", fill_value="__none__"),
                OneHotEncoder(handle_unknown="ignore", min_frequency=params.EXAMINER_MIN_FREQ,
                              sparse_output=False)), [NAME]))
        parts.append(("num", make_pipeline(SimpleImputer(strategy="median", add_indicator=True), StandardScaler()), num))
        return make_pipeline(ColumnTransformer(parts), LogisticRegression(C=cfg["C"], max_iter=5000))
    pre = ColumnTransformer([
        ("cat", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=np.nan,
                               encoded_missing_value=np.nan), cat),
        ("num", "passthrough", num)])
    hgb = HistGradientBoostingClassifier(categorical_features=list(range(len(cat))),
                                         random_state=params.SEED, **params.GBT_FIXED, **cfg)
    return make_pipeline(pre, hgb)


def forward_folds(train: pd.DataFrame):
    """For each validation year, fit on earlier rows and leave out families seen in that year."""
    folds = []
    for V in params.FORWARD_VAL_YEARS:
        start = f"{V}-01-01"
        val = train[train.reply_year == V]
        fit = train[(train.reply_date < start) & (train.next_date < start) & ~train.family_root.isin(val.family_root)]
        if len(val) and len(fit) and fit.y.nunique() == 2:
            folds.append((fit, val))
    return folds


def cv_score(kind, profile, cfg, folds, lam):
    """Average validation log loss over the forward folds."""
    scores = []
    for fit, val in folds:
        fit, val = add_profile(fit, lam), add_profile(val, lam)
        m = make_model(kind, profile, cfg).fit(fit, fit.y)
        scores.append(log_loss(m.predict_proba(val)[:, 1], val.y))
    return float(np.mean(scores))


def main():
    warnings.filterwarnings("ignore")
    out = stage_dir(STAGE)
    feat = need(stage_dir("features") / "features.csv", "features/code/build_features.py")
    prof = need(stage_dir("profiles") / "profiles.csv", "profiles/code/build_profiles.py")
    df = pd.read_csv(feat, dtype={"family_root": str, "app_id": str, "art_unit": str}).merge(
        pd.read_csv(prof), on="episode_id", validate="one_to_one")
    train = df[(df.block == "train") & (df.primary == 1)].copy()
    folds = forward_folds(train)
    log(STAGE, f"training rows {len(train)}; forward folds: " +
        ", ".join(f"{v.reply_year.iloc[0]}: fit {len(f)} / val {len(v)}" for f, v in folds))

    # 1. tune lambda, each lambda scored with its best C from the LR grid
    lam_scores = {lam: min(cv_score("lr", True, cfg, folds, lam) for cfg in params.LR_GRID)
                  for lam in params.LAMBDA_GRID}
    lam = min(lam_scores, key=lam_scores.get)
    log(STAGE, f"lambda scores {lam_scores}, chosen lambda = {lam}")

    # 2. tune each model, then fit it on all training rows
    card = {"lambda": lam, "lambda_cv_log_loss": lam_scores,
            "features": {"off": {"categorical": CAT, "numeric": NUM},
                         "on": {"categorical": CAT + [NAME], "numeric": NUM + PROF},
                         "note": "on = off + examiner ID + examiner history (dated before each reply)"},
            "models": {}}
    df_p = add_profile(df, lam)
    train_p = df_p.loc[train.index]
    preds = {}
    base = float(train.y.mean())
    preds["base"] = np.full(len(df_p), base)
    card["models"]["base"] = {"rate": base}
    for kind, grid in (("lr", params.LR_GRID), ("gbt", params.GBT_GRID)):
        for profile in (False, True):
            name = f"{kind}_{'on' if profile else 'off'}"
            sc = [cv_score(kind, profile, cfg, folds, lam) for cfg in grid]
            best = grid[int(np.argmin(sc))]
            m = make_model(kind, profile, best).fit(train_p, train_p.y)
            preds[name] = m.predict_proba(df_p)[:, 1]
            card["models"][name] = {"grid": list(grid), "cv_log_loss": sc, "chosen": best}
            if kind == "lr":
                lr = m[-1]
                names = m[0].get_feature_names_out()
                coef = sorted(zip(names, lr.coef_[0]), key=lambda t: -abs(t[1]))[:25]
                card["models"][name]["top_coefficients"] = [(n, round(float(c), 4)) for n, c in coef]
            log(STAGE, f"{name}: cv log loss {np.round(sc, 4).tolist()}, chosen: {best}")

    # save dev and test predictions
    keep = ["episode_id", "family_root", "examiner_id", "app_id", "block", "part", "primary", "y", "reply_date",
            "reply_year", "next_date", "prior_type", "art_unit", "tc", "round_n", "round_c", "rce", "g101", "g102",
            "g103", "g112", "g_dp", "filing_year", "elapsed_years", "prof_s", "prof_n", "au_rate", "prof_rate",
            "hist_tier", "ex_group", "ex_n_before", "ex_rate_before",   # examiner group: filters/slices only
            "prior_doc_ids", "reply_doc_ids", "next_doc_ids", "ground_doc", "prior_date"]
    res = df_p[keep].copy()
    for k, v in preds.items():
        res[k] = np.clip(v, params.CLIP, 1 - params.CLIP)
    res = res[res.block.isin(["dev", "test"])].reset_index(drop=True)
    res.to_csv(out / "predictions.csv", index=False)
    write_json(out / "model_card.json", card)
    write_manifest(STAGE, {"features": feat, "profiles": prof}, ["predictions.csv", "model_card.json"],
                   {"lambda": lam})
    log(STAGE, f"{len(res)} dev/test predictions saved to {out/'predictions.csv'}")


if __name__ == "__main__":
    main()
