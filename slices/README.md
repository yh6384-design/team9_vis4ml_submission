# slices · the flagging procedure (flagged groups ⚑1–⚑5)

**What it does:** on **2014 part A only**, with the real predictions and real outcomes:
1. lists groups described by one or two conditions over tech center, art unit, examiner history, round, RCE, letter
   answered and the grounds (each condition needs ≥ 100 families in 2014 part A and part B), plus small-tree leaves;
2. for each group and each of the four learned models: group gap − full population gap (gap = predicted allowance −
   real allowance), 95% CI from 500 family re-draws;
3. keeps groups with ≥ 100 families in both parts whose difference is ≥ 5 points with a 95% CI excluding 0, for at
   least one model;
4. ranks them by their largest ECE among the four models; the top five = **flagged groups ⚑1–⚑5** (⚑ = "look here",
   not "good");
5. re-checks the five on 2014 part B and 2015–2017 with the same comparison.

Worked example (⚑4 "examiner history ≥ 6 and no §102 rejection", LR off): group 195 cases, predicted allowance 51.3%,
real allowance 62.1%, gap −10.7; full population 467 cases, 50.2%, 54.4%, gap −4.1; difference −6.6, 95% CI −11.1 to
−2.0 → passes. Fixed, seeded rule: same data → byte-identical `frozen_top5.json` (file names kept; "frozen" = fixed by
the rule). The dashboard filters work on every feature without the five.

## Run
```bash
python slices/code/find_slices.py
```
(Set `VML_OUT` and `VML_CORPUS` first, see the top-level `README.md`. `bash run_all.sh` runs every stage in order, in conda env `vml`.)

## Inputs
VML_OUT/models/predictions.csv, VML_OUT/profiles/tiers.json

## Outputs (in `$VML_OUT/slices/`)
candidates.csv (every group listed, its numbers, pass/fail), frozen_top5.json (⚑1–⚑5), frozen_assessment.csv (the
five re-checked per period), slice_curves.json. Every stage also writes `_run.json` (who ran it, when, git commit, input sha1s, all parameters).
