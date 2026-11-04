"""Turn the episode table into the prediction set: is the examiner's next letter an allowance?

    python make_target.py --episodes ../output/episodes.csv --out ../output/episodes_target.csv

Keeps only episodes whose next letter was seen and is one of:
  allowance (MN/=.)            -> y_allowance = 1
  non-final rejection (MCTNF)  -> y_allowance = 0
  final rejection (MCTFR)      -> y_allowance = 0
Drops: advisory action, Quayle action, restriction, abandonment, and no next letter in the data.
"""
import argparse
from pathlib import Path

import pandas as pd

KEEP = {"allowance": 1, "nonfinal_rejection": 0, "final_rejection": 0}
OUT_DIR = Path(__file__).resolve().parent.parent / "output"

ap = argparse.ArgumentParser()
ap.add_argument("--episodes", default=str(OUT_DIR / "episodes.csv"))
ap.add_argument("--out", default=str(OUT_DIR / "episodes_target.csv"))
a = ap.parse_args()

ep = pd.read_csv(a.episodes, dtype={"app_id": str, "family_root": str})
print(f"all episodes: {len(ep):,} rows, {ep.app_id.nunique():,} applications, "
      f"{ep.examiner_id.nunique()} examiners, replies {ep.reply_date.min()} to {ep.reply_date.max()}")
print(ep.next_type.fillna("none_shipped").value_counts().to_string())

t = ep[ep.next_type.isin(KEEP)].copy()
t["y_allowance"] = t.next_type.map(KEEP)
t.to_csv(a.out, index=False)
print(f"\nprediction set: {len(t):,} rows, {t.app_id.nunique():,} applications, "
      f"{t.examiner_id.nunique()} examiners; allowance share {t.y_allowance.mean():.1%}")
