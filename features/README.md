# features

**Owner:** Nancy  ·  **What it does:** builds one row per case (one applicant reply) with every input the models and
the flagging procedure need: round, RCE, tech center, art unit, letter answered, rejection grounds read from the letter
text (§101 / §102 / §103 / §112 / double patenting), filing year, years since filing, confirmed-examiner flag, and the
2014 parts A / B.

## Run
```bash
python features/code/build_features.py
```
(Set `VML_OUT` and `VML_CORPUS` first, see the top-level `README.md`. `bash run_all.sh` runs every stage in order, in conda env `vml`.)

## Inputs
VML_OUT/cohort/cohort.csv, episode_table/output/episodes.csv, the raw corpus (profile_index.csv, apps/*/text)

## Outputs (in `$VML_OUT/features/`)
features.csv, features_summary.json, ground_spotcheck.csv. Every stage also writes `_run.json` (who ran it, when, git commit, input sha1s, all parameters).

## What to check when you review a run
- [ ] 5,595 rows; grounds found for ~99.7%.
- [ ] ground_spotcheck.csv: read the 20 letters by hand; write "x of 20 correct" in docs/DATA_CARD.md.

## How this matches the course
Lec 11: only information available at the case date.
