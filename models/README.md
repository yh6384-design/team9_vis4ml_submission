# models

**What it does:** Train a base rate, logistic regression and boosted trees, each with the examiner profile off and on, and predict every dev and test checkpoint.

## Run

```bash
python models/code/train_models.py
```

(Set `VML_OUT` and `VML_CORPUS` first, see the top-level `README.md`. `bash run_all.sh` runs every stage in order.)

## Inputs

VML_OUT/features/features.csv, VML_OUT/profiles/profiles.csv

## Outputs (in `$VML_OUT/models/`)

predictions.csv (the case table every later stage reads), model_card.json. Every stage also writes `_run.json` (who ran it, when, git commit, input sha1s, all parameters).
