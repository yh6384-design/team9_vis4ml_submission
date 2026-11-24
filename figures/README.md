# figures

**What it does:** paper and slide figures, drawn only from stage outputs,
with the same terms as the dashboard (predicted allowance, real allowance, gap, ECE, AUROC, flagged group).

## Run
```bash
python figures/code/make_figures.py
```
(Set `VML_OUT` and `VML_CORPUS` first, see the top-level `README.md`. `bash run_all.sh` runs every stage in order.)

## Inputs
outputs of metrics, e2, slices, e3

## Outputs (in `$VML_OUT/figures/`)
fig_reliability_overall.png (reliability diagram, 2015–2017), fig_by_year.png (gap by year), fig_e2_forest.png
(Experiment 2: on − off with 95% CI), fig_frozen_replication.png (flagged groups re-checked in 2014 part B and
2015–2017), fig_e3_recovery.png (Experiment 3). Every stage also writes `_run.json` (who ran it, when, git commit, input sha1s, all parameters).
