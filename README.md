# Can You Trust Personalized Odds? Visual Calibration Analysis of Patent-Prosecution Predictors

Team 9 · DS-GA 3001 Visualization for Machine Learning (NYU Center for Data Science, Fall 2026) ·
Wynnian Yang, Crissy Chen, Nancy Hu

A model predicts whether the next examiner letter in a patent application will be a notice of allowance (the
**predicted allowance**). We ask whether that number can be trusted: is it close to the **real allowance** (the share
really allowed), and does adding the examiner's profile (his examiner ID and his earlier decisions, dated before the case)
bring it closer and rank cases better? We build a visual analysis dashboard, extending Calibrate (Xenopoulos et al.,
IEEE VIS 2022), for the applicant who filed the patent: they describe their own case with filters on every case
feature and see predicted allowance next to real allowance for cases like theirs, from their exact case out to the
full population. Six linked D3 visualizations answer the research questions, each with a live answer. Groups where
the gap (predicted allowance − real allowance) differs most from the full population in 2014 are shown as five
flagged groups (⚑1–⚑5, fixed rule) and re-checked in 2015–2017.

## Run

```bash
pip install -r requirements.txt
# raw data: public USPTO file-wrapper records packaged as profile_corpus_v2.zip
export VML_CORPUS=/path/to/profile_corpus_v2.zip      # or place it at ../data/profile_corpus_v2.zip
export VML_OUT=/path/to/outputs                       # default: ./outputs
bash run_all.sh                                       # all steps, 10–15 minutes (use conda env vml)
open interface/index.html                             # the interface (works from file://)
```

`bash run_all.sh --quick` runs a fast check; `bash run_all.sh --from <step>` restarts at a step. Every step writes
`VML_OUT/<step>/_run.json` (time, git commit, input checksums, all parameters). All parameters are in `vml/params.py`.

## Pipeline

| #  | Folder                                  | What it does                                                                                                                                                                                                          |
| -- | --------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 0  | `profile_corpus/`, `episode_table/` | USPTO records → 8,364 reply → next-letter episodes; outcome: allowed (notice of allowance) vs rejected (non-final/final office action)                                                                              |
| 0  | `cohort/`, `audit/`                 | time split (train 2008–13, 2014, test 2015–17) with family purge; 50-record audit                                                                                                                                   |
| 1  | `features/`                           | round, RCE, tech center, rejection grounds from the letter text, filing year, 2014 parts A/B                                                                                                                          |
| 2  | `profiles/`                           | examiner history dated before each case; history tiers; examiner groups G0–G5 (one label per examiner from decisions before 2015; dashboard filter only)                                                             |
| 3  | `models/`                             | base rate; logistic regression and boosted trees, each with the examiner profile off / on (on = off inputs + examiner ID + history)                                                                                   |
| 4  | `metrics/`                            | ECE (+ binning checks), MCE, gap, Brier score, log loss, AUROC, 95% CI (family bootstrap), learned (EBM) curves                                                                                                       |
| 5  | `slices/`                             | flagging procedure (≤ 2 conditions, ≥ 100 families, \|group gap − full population gap\| ≥ 0.05 and its 95% CI does not include 0) → flagged groups ⚑1–⚑5, re-checked in 2014 part B and 2015–2017            |
| 6  | `e1_reproduce/`                       | Experiment 1: reproduction of Calibrate (COMPAS, Figs. 3–4)                                                                                                                                                          |
| 7  | `e2_evaluate/`                        | Experiment 2: profile off vs on on the same 2015–2017 cases, paired 95% CI                                                                                                                                           |
| 8  | `e3_synthetic/`                       | Experiment 3: test of the flagging procedure on a practice copy of 2014 with a known answer                                                                                                                           |
| 9  | `figures/`                            | report figures                                                                                                                                                                                                        |
| 10 | `export/`, `interface/`             | data export and the D3 dashboard: Visualization 1 your case, 2 reliability diagram, 3 profile off vs on (ROC curve + groups), 4 flagged groups (+ 2015–2017 re-check), 5 groups × models, 6 cases and their sources |

Shared code: `vml/`. Data description: `docs/DATA_CARD.md`. Each folder's `README.md` explains its inputs and outputs.

## Data and licenses

USPTO Open Data Portal records (public). COMPAS data from ProPublica (`e1_reproduce/data/`). D3 7.9.0 vendored
under its ISC license (`interface/vendor/`).
