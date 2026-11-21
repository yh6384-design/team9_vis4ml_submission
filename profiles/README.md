# profiles

**What it does:** For each checkpoint, count the examiner's and the art unit's earlier outcomes, and group checkpoints into history tiers.

## Run

```bash
python profiles/code/build_profiles.py
```

(Set `VML_OUT` and `VML_CORPUS` first, see the top-level `README.md`. `bash run_all.sh` runs every stage in order.)

## Inputs

VML_OUT/features/features.csv, episode_table/output/episodes_target.csv (reference pool)

## Outputs (in `$VML_OUT/profiles/`)

profiles.csv, tiers.json, profile_sources.json (the history behind each dev/test checkpoint, shown in the interface), profiles_summary.json. Every stage also writes `_run.json` (who ran it, when, git commit, input sha1s, all parameters).
