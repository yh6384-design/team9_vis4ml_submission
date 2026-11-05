# Initial 50-record audit

This audit checks the recorded reply date, next-notification label, and examiner
identity for a fixed sample of 50 prosecution episodes. The script selects the
sample from the [episode table](../episode_table/output/episodes.csv) with seed
`20261103` after sorting eligible episodes by `episode_id`. Eligible episodes
have an advisory action or a final or non-final rejection before the reply, and
a notice of allowance or a final or non-final rejection after it.

## Results

| Check | Result |
| --- | ---: |
| Examiner ID matches the hash of the name in the saved USPTO Open Data Portal (ODP) record | 50/50 |
| Prior-letter signature matches the ODP name by the script's heuristic | 43/47 |
| Next-letter signature matches the ODP name by the script's heuristic | 42/45 |
| First relevant transaction after the reply matches the recorded notification type and date | 50/50 |
| Recorded reply transaction found | 50/50 |

The signature check looks for surnames or initials in slash-delimited
signature lines. Its denominators include only letters for which the script
extracted a signature line. An ODP name hash match checks the recorded ID;
it does not establish who signed a letter.

All eight flagged records received follow-up manual review: one
`agree` and seven `agree_with_limit`. Combining the automatic checks with
the recorded adjudications, 46 of 50 episodes had prior-letter evidence
consistent with the saved ODP name, including cases supported by initials.
Three had support from the next letter only, so prior-letter identity remains
unverified. One had a mismatch between the letter signatures and the ODP
record. `confirmed_by` records who reviewed the adjudication, including
adjudications that identify a mismatch or an evidence limit.

## Reproduce the automatic checks

Use Python 3 and the saved USPTO source bundle for these 50 episodes. Pass the
bundle's `apps` directory, whose per-application subdirectories contain
`raw/search_record.json`, `raw/transactions.json`, and the available letter
texts under `text/`. The run uses saved files and does not query the live
portal. The episode table used in this audit has SHA-256
`7deec37c677edb0ec864bfa0d06ccf7f2296e5eb1c7d52fced3c9f4f03498dbe`.

From the repository root, replace the example path and run:

```sh
AUDIT_APPS_DIR="/path/to/audit_sources/apps"
AUDIT_OUT_DIR="$(mktemp -d)"

python3 audit/code/audit_50.py \
  episode_table/output/episodes.csv \
  "$AUDIT_APPS_DIR" "$AUDIT_OUT_DIR" \
  --n 50 --seed 20261103

for file in audit_50.csv audit_50_summary.json audit_50_review.json; do
  cmp "$AUDIT_OUT_DIR/$file" "audit/output/$file" || exit 1
done
```

## Files

| File | Contents |
| --- | --- |
| [`code/audit_50.py`](code/audit_50.py) | Sampling and automatic checks. |
| [`output/audit_50.csv`](output/audit_50.csv) | Per-episode results and source filenames. |
| [`output/audit_50_summary.json`](output/audit_50_summary.json) | Counts from the automatic checks. |
| [`output/audit_50_review.json`](output/audit_50_review.json) | Flagged records and excerpts used in manual review. |
| [`output/audit_50_adjudication.csv`](output/audit_50_adjudication.csv) | Original manual adjudications and follow-up evidence. This file is maintained separately from the script outputs. |
