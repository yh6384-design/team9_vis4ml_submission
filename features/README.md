# features

**What it does:** Build one row per checkpoint with every input the models and slices need.

## Run

```bash
python features/code/build_features.py
```

(Set `VML_OUT` and `VML_CORPUS` first, see the top-level `README.md`. `bash run_all.sh` runs every stage in order.)

## Inputs

VML_OUT/cohort/cohort.csv, episode_table/output/episodes.csv, the raw corpus (profile_index.csv, apps/*/text)

## Outputs (in `$VML_OUT/features/`)

features.csv, features_summary.json, ground_spotcheck.csv. Every stage also writes `_run.json` (who ran it, when, git commit, input sha1s, all parameters).
