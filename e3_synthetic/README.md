# e3_synthetic · Experiment 3: test of the flagging procedure

**What it does:** checks how reliable the flagging procedure of `slices/` is. Real data cannot
tell us which groups truly have a gap, so the procedure is run on a **practice copy of 2014 with a known answer**:

1. keep the 947 cases of 2014 (features and LR-off predicted allowance unchanged); replace each outcome by a draw:
   random number 0–100 below the predicted allowance → allowed, else rejected (fixed seed). Every case is then allowed
   with probability equal to its prediction, so every group's true gap is 0;
2. run the same procedure (200 family re-draws per group): every group that passes the tests passes by luck. Two
   different counts: groups that **pass** the tests (no limit) and groups that are **flagged** (the top 5 of those);
3. optionally raise the predicted allowance of one group chosen in advance (+0.25 / +0.5 / +1.0 on the log-odds scale,
   about +6 / +12 / +23 points at 50%; both directions; small / medium / large groups) and see whether it is flagged;
4. repeat with new random numbers: 50 runs with no gap, 20 runs per setting with a known gap.

Outcomes are drawn as Y ∼ Bernoulli(q(X)) with p = q(X), then known distortions are planted; the Slice Finder paper
tested itself the same way.

## Run

```bash
python e3_synthetic/code/e3_planted.py
```

Add `--quick` (3 runs per setting) to test the code.
(Set `VML_OUT` and `VML_CORPUS` first, see the top-level `README.md`. `bash run_all.sh` runs every stage in order, in conda env `vml`.)

## Inputs

VML_OUT/models/predictions.csv, VML_OUT/slices/candidates.csv

## Outputs (in `$VML_OUT/e3/`)

e3_runs.csv (runs with a known gap), e3_null.csv (runs with no gap), e3_real_perturb.csv (known gap added to the real
data), e3_summary.json/.md, e3_plan.json (the groups chosen in advance). Every stage also writes `_run.json` (who ran it, when, git commit, input sha1s, all parameters).
