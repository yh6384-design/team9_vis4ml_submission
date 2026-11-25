#!/bin/bash
# Run the whole pipeline in order. About 10 minutes on a laptop.
#
#   export VML_CORPUS=/path/to/profile_corpus_v2.zip      # or leave unset if it is in ../data/
#   export VML_OUT=/path/to/output/folder                 # default: ./outputs
#   bash run_all.sh            # everything
#   bash run_all.sh --from slices     # start at a later stage (earlier outputs must exist in VML_OUT)
#   bash run_all.sh --quick    # fast check: small bootstrap, no learned curves, E3 with 3 seeds
#
# Stage order (each reads the previous outputs from VML_OUT):
#   check   episode table rebuilt from the corpus = committed copy (skipped if no corpus)
#   cohort  features  profiles  models  metrics  slices  e1  e2  e3  figures  export
set -e
set -o pipefail          # a failing step stops the run (the "| tee" below must not hide errors)
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"
OUT="${VML_OUT:-$HERE/outputs}"
export VML_OUT="$OUT"
mkdir -p "$OUT"
STAGES=(check cohort features profiles models metrics slices e1 e2 e3 figures export)
FROM="check"; QUICK=""
while [ $# -gt 0 ]; do
  case "$1" in
    --from) [ $# -ge 2 ] || { echo "--from needs a stage name: ${STAGES[*]}"; exit 1; }
            FROM="$2"; shift 2;;
    --quick) QUICK="1"; shift;;
    *) echo "unknown option $1"; exit 1;;
  esac
done
case " ${STAGES[*]} " in
  *" $FROM "*) ;;
  *) echo "unknown stage '$FROM'; choose one of: ${STAGES[*]}"; exit 1;;
esac
started=0
LOG="$OUT/run_all.log"
echo "=== run_all $(date -u +%FT%TZ) by $(whoami) quick=${QUICK:-0} from=$FROM" | tee -a "$LOG"
for s in "${STAGES[@]}"; do
  [ "$s" = "$FROM" ] && started=1
  [ $started = 1 ] || continue
  echo "--- $s" | tee -a "$LOG"
  case "$s" in
    check)
      if python3 -c "import sys; sys.path.insert(0,'.'); from vml.paths import corpus_dir; c=corpus_dir(); print(c or ''); sys.exit(0 if c else 1)" > /tmp/vml_corpus_path 2>/dev/null; then
        res="$(bash episode_table/run.sh "$(tail -1 /tmp/vml_corpus_path)" 2>&1 | tail -2)"
        echo "$res" | tee -a "$LOG"
        if echo "$res" | grep -q DIFFERENT; then
          echo "the rebuilt episode table differs from the committed copy: stopping" | tee -a "$LOG"; exit 1
        fi
      else
        echo "no corpus found: skipping the episode-table check" | tee -a "$LOG"
      fi;;
    cohort)   python3 cohort/code/build_cohort.py --out "$OUT/cohort" 2>&1 | tail -3 | tee -a "$LOG";;
    features) python3 features/code/build_features.py 2>&1 | tee -a "$LOG"
              python3 -c "import json, os, sys; s = json.load(open(os.path.join(os.environ['VML_OUT'], 'features', 'features_summary.json'))); print('corpus_used:', s.get('corpus_used')); sys.exit(0 if s.get('corpus_used') else 1)" 2>&1 | tee -a "$LOG" \
                || { echo "the features were built without the raw corpus: stopping" | tee -a "$LOG"; exit 1; };;
    profiles) python3 profiles/code/build_profiles.py 2>&1 | tee -a "$LOG";;
    models)   python3 models/code/train_models.py 2>&1 | tee -a "$LOG";;
    metrics)  python3 metrics/code/run_metrics.py ${QUICK:+--fast} 2>&1 | tee -a "$LOG";;
    slices)   python3 slices/code/find_slices.py ${QUICK:+--no-curves} 2>&1 | tee -a "$LOG";;
    e1)       python3 e1_reproduce/code/e1_calibrate_repro.py 2>&1 | tail -30 | tee -a "$LOG";;
    e2)       python3 e2_evaluate/code/e2_paired.py 2>&1 | tail -12 | tee -a "$LOG";;
    e3)       python3 e3_synthetic/code/e3_planted.py ${QUICK:+--quick} 2>&1 | tail -25 | tee -a "$LOG";;
    figures)  python3 figures/code/make_figures.py 2>&1 | tee -a "$LOG";;
    export)   python3 export/code/build_interface_data.py --synthetic 2>&1 | tee -a "$LOG";;
  esac
done
echo "=== done. Outputs in $OUT ; open interface/index.html to explore." | tee -a "$LOG"
