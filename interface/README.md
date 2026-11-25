# Calibration dashboard

The six linked views compare predicted allowance with observed allowance for patent-prosecution cases. The outcome is a notice of allowance versus a non-final or final office action among cases with an observed notification in one of those categories.

## Run

Open `interface/index.html` in Chrome or Firefox after running the pipeline. To refresh the data and generate the practice page from existing pipeline outputs, run the export from the project root.

```bash
python3 export/code/build_interface_data.py --synthetic
```

Open `interface/index_practice.html` for the simulated practice examples.

Use **More filters** for rejection grounds, filing year, and examiner history. The **Data sources** panel at the bottom lists the dashboard export and its upstream files.

## Inputs

- `interface/data/vml_data.js` contains cases, matched predictions, dated profile sources, flagged group assessments and the Experiment 2 comparison.
- `interface/data/vml_data_synthetic.js` contains simulated predictions and outcomes for the practice page.
- Examiner groups use decisions mailed before January 1, 2015. The dashboard enables this filter for 2015–2017 and clears it when switching to a 2014 period.

## Outputs

| Visualization | What it shows |
| --- | --- |
| 1. Your case | Predicted and observed allowance for the selection and progressively broader groups. The full population provides context. |
| 2. Reliability | Binned and fitted calibration curves and the distribution of predicted allowance. Drag the histogram to select a probability interval. |
| 3. Profile comparison | ROC curves and paired measures for profile-off and profile-on predictions. The full 2015–2017 selection uses the exported Experiment 2 results. |
| 4. Flagged groups | Select a group and compare its gap across periods. The confirmed cohort uses the exported re-checks for the selected profile-off model. |
| 5. Groups × models | Compare ECE, gap, or group gap relative to the full population of the same period and cohort. |
| 6. Cases and sources | Inspect the selected cases and their document IDs. Confirmed profiles show the available dated examiner outcomes. |

The browser recomputes interactive measures from the exported probabilities. Low-support results are descriptive. The Python output tables provide the reported experiment estimates and intervals.

D3 7.9.0 is vendored under the ISC license in `vendor/D3-LICENSE`. The color vision deficiency simulation uses matrices from Machado, Oliveira, and Fernandes (2009).
