# e2_evaluate · Experiment 2: profile off vs on

**What it does:** on the same 2015–2017 cases, compares each model with the examiner profile
off and on (on = off inputs + examiner ID + history). For each measure: on − off with a **paired** 95% CI (1,000
family re-draws, the same draws for both). Answers research question 1. Examiner groups are **not** used here.

## Run
```bash
python e2_evaluate/code/e2_paired.py
```
(Set `VML_OUT` and `VML_CORPUS` first, see the top-level `README.md`. `bash run_all.sh` runs every stage in order.)

## Inputs
VML_OUT/models/predictions.csv, VML_OUT/slices/frozen_top5.json (the flagged groups)

## Outputs (in `$VML_OUT/e2/`)
e2_paired.csv (one row per group × model pair: ECE, Brier score, log loss, AUROC, gap for off and on, on − off and
95% CI), e2_worst_slice.csv, e2_summary.md. Every stage also writes `_run.json` (who ran it, when, git commit, input sha1s, all parameters).
