# models

**What it does:** base-rate model + logistic regression (LR) and boosted trees (Trees), each with
the examiner profile **off** and **on** (same training cases, same tuning budget).
* **Off:** tech center, art unit, letter answered, round, RCE, the five ground flags, ground-text-found flag, filing
  year, years since filing.
* **On:** the same + **examiner ID** (anonymized code; LR: one column per examiner, examiners with < 5 training cases share a "rare"
  column, an examiner unseen in training gets no ID effect; Trees: one categorical input) + **examiner history**
  (shrunk allowance rate on the log-odds scale, log(1 + decisions), log(1 + allowances), has-history flag).
* Examiner group is **not** an input.

## Run
```bash
python models/code/train_models.py
```
(Set `VML_OUT` and `VML_CORPUS` first, see the top-level `README.md`. `bash run_all.sh` runs every stage in order.)

## Inputs
VML_OUT/features/features.csv, VML_OUT/profiles/profiles.csv

## Outputs (in `$VML_OUT/models/`)
predictions.csv (the shared case table for every later stage; it also carries `ex_group`, `ex_n_before`,
`ex_rate_before` for the dashboard filter, not as model inputs), model_card.json. Every stage also writes `_run.json` (who ran it, when, git commit, input sha1s, all parameters).
