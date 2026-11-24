# export

**What it does:** writes `interface/data/vml_data.js`, everything the dashboard needs: every
case with all the features a user can filter on (examiner, examiner group, art unit, tech center, letter answered,
round, RCE, grounds incl. double patenting, filing year, examiner history), its four predicted allowances and the
flagged groups it belongs to; examiner records and group names; the group tables; curves; measures; Experiment 2; the
footer list of source files. `--synthetic` also writes the practice page `interface/index_practice.html`.

## Run
```bash
python export/code/build_interface_data.py --synthetic
```
(Set `VML_OUT` and `VML_CORPUS` first, see the top-level `README.md`. `bash run_all.sh` runs every stage in order.)

## Inputs
outputs of models, profiles (incl. examiner_groups.json), metrics, slices, e2, e3 (practice data)

## Outputs
interface/data/vml_data.js, vml_data_synthetic.js, interface/index_practice.html (+ copies and the practice answer key
in VML_OUT/export/). Every stage also writes `_run.json` (who ran it, when, git commit, input sha1s, all parameters).
