# metrics

**What it does:** All calibration measures, reported together, with family-bootstrap intervals; binned and learned reliability; by year.

## Run

```bash
python metrics/code/run_metrics.py
```

Add `--fast` (fewer bootstrap re-draws) while debugging.

(Set `VML_OUT` and `VML_CORPUS` first, see the top-level `README.md`. `bash run_all.sh` runs every stage in order.)

## Inputs

VML_OUT/models/predictions.csv

## Outputs (in `$VML_OUT/metrics/`)

metrics_overall.csv, reliability_bins.csv, learned_curves.json, by_year.csv, confirmed_share.csv. Every stage also writes `_run.json` (who ran it, when, git commit, input sha1s, all parameters).
