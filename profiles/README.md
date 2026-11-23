# profiles

**What it does:** dated examiner history (the examiner's earlier decisions mailed **before** each case,
from other families), art-unit rate, history tiers (0–5 / 6–13 / 14+), the source list for Visualization 6, and the
**examiner groups**.

**Examiner group:** one label per examiner, from all the examiner's decisions mailed before 2015-01-01 (training and
2014 years): allowance rate cut at 21% / 36% / 52% / 70% into G1 (allows least) … G5 (allows most); G0 = fewer than 5
such decisions. Also each examiner's full record (all years) for the examiner card. **A dashboard filter only**: not a
model input, not used in training, prediction or any measure.

## Run
```bash
python profiles/code/build_profiles.py
```
(Set `VML_OUT` and `VML_CORPUS` first, see the top-level `README.md`. `bash run_all.sh` runs every stage in order.)

## Inputs
VML_OUT/features/features.csv, episode_table/output/episodes_target.csv (reference pool)

## Outputs (in `$VML_OUT/profiles/`)
profiles.csv (incl. `ex_group`, `ex_n_before`, `ex_rate_before`), tiers.json, examiner_groups.json,
profile_sources.json, profiles_summary.json. Every stage also writes `_run.json` (who ran it, when, git commit, input sha1s, all parameters).
