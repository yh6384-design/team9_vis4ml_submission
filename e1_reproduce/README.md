# e1_reproduce · Experiment 1: reproduce Calibrate

**What it does:** reproduces the Calibrate paper (Xenopoulos et al.): the COMPAS age example,
the learned-vs-binned reliability diagram (paper Fig. 4) and the binning grid (Fig. 3), then the binning grid on our
2015–2017 predictions.

## Run
```bash
python e1_reproduce/code/e1_calibrate_repro.py
```
`e1_pycalibrate_widget.ipynb` opens the original Calibrate widget in Jupyter. It is not part of `run_all.sh` and needs an extra install (see the notebook).
(Set `VML_OUT` and `VML_CORPUS` first, see the top-level `README.md`. `bash run_all.sh` runs every stage in order.)

## Inputs
e1_reproduce/data/compas-scores-two-years.csv (ProPublica), VML_OUT/models/predictions.csv

## Outputs (in `$VML_OUT/e1/`)
e1_notes.md, e1a_compas_metrics.csv, e1a/e1b/e1c figures. Every stage also writes `_run.json` (who ran it, when, git commit, input sha1s, all parameters).
