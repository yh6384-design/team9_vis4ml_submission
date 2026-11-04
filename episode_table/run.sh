#!/bin/bash
# Rebuild the episode table and the prediction set, and check them against output/.
#
#   bash episode_table/run.sh                 # uses ../profile_corpus/share/profile_corpus_v2.zip
#   bash episode_table/run.sh <corpus>        # a profile_corpus_v2.zip, or an unzipped profile_corpus/ folder
#
# Needs Python 3 and pandas. Writes only to episode_table/work/ (not tracked by git).
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
CORPUS="${1:-$HERE/../profile_corpus/share/profile_corpus_v2.zip}"
WORK="$HERE/work"
mkdir -p "$WORK"

if [ -f "$CORPUS" ]; then
  echo "unzipping $CORPUS"
  rm -rf "$WORK/profile_corpus"
  unzip -q "$CORPUS" -d "$WORK"
  CORPUS="$WORK/profile_corpus"
fi
[ -f "$CORPUS/profile_index.csv" ] || { echo "no profile_index.csv in $CORPUS"; exit 1; }

python3 "$HERE/code/build_episode_table.py" --corpus "$CORPUS" --out "$WORK/rebuild" > /dev/null
python3 "$HERE/code/make_target.py" --episodes "$WORK/rebuild/episodes.csv" --out "$WORK/rebuild/episodes_target.csv"

echo
for f in episodes.csv episodes_target.csv; do
  if cmp -s "$WORK/rebuild/$f" "$HERE/output/$f"; then echo "$f: identical to output/$f"
  else echo "$f: DIFFERENT from output/$f"; fi
done
