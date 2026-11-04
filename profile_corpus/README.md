# Profile corpus v2: build scripts and run logs

Built by Wynnian Yang, 26–28 October 2026, from public USPTO Open Data Portal (ODP) records. The packaged corpus is `profile_corpus_v2.zip`. Every later step in this repository starts from it.

## What the corpus is

There are 100 `test_core` examples, which are applications from the 1,000-application sample. For each one, the corpus holds other applications by the same examiner (target: 30), plus the same for one control examiner from the same art unit. It contains 5,369 profile applications, 99 own and 98 control examiners, and 79,532 files. File format and column meanings are in `docs/PROFILE_CORPUS_FORMAT.md`.

## How each step is done

| Step | Script | Rule |
|---|---|---|
| Examiner of each example | `code/v2_profile_corpus.py` (`o1_info`, `resolve_examiners`) | The examiner who signed the example's first office action ("should be directed to NAME", else the first full-name signature block). ODP's current examiner name is used only when the action has no signature. |
| Picking the 5,369 profile applications | `code/v2_profile_corpus.py` (`run_job`) | Utility applications of that examiner filed between 8 years and 1 year before the example's cutoff (A1 filing date; the earliest cutoff when an examiner has several examples). The 1,000 sample applications, their families and their continuity parents/children are excluded. Candidates are taken in a seeded random order. An application is usable if a CTNF/CTFR signed by this examiner was mailed before the cutoff. |
| Control examiner | `code/v2_profile_corpus.py` (`--phase control`) | A different examiner of the same art unit (printed on the example's first action), downloaded the same way with the example's cutoff. Falls back to the work group; the level used is recorded. |
| Signature of each rejection (`signed_by_this_examiner` in `actions.csv`) | `code/v2_profile_corpus.py` (`oa_signer`, `same_person`); rechecked in `code/v2_profile_package.py` | The signer is read from the USPTO XML of each CTNF/CTFR and compared with the examiner's name. The value is `true` or `false`, or empty when the action has no USPTO text. Packaging rechecks every signature with the final name rule and drops applications that no longer qualify. Counts: 9,290 true, 160 false, 189 empty; 4 changed and 3 applications dropped on recheck. |
| USPTO XML to text | `code/v1_text.py` (`process`), called by `code/v2_profile_corpus.py` | Tags are stripped from the USPTO XML of examiner actions and applicant replies. Claim listings become `.claims.json`. Examiner actions also get a `.substantive.txt` with form paragraphs removed. No OCR. |
| Removing everything on or after the cutoff | `code/v2_profile_package.py` | For each examiner, texts, transactions, catalog rows and PGPUB files dated on or after the latest cutoff that uses the examiner are not packaged. Not shipped: 51,415 transactions and 8 texts. Users cut again at each example's own cutoff (16 examiners serve several cutoffs). |
| Packaging and checks | `code/v2_profile_package.py` | Writes `cases.csv`, `profile_index.csv`, `actions.csv`, `MANIFEST.csv` (SHA-1 of every file) and `checks.json`. Any failed check stops the script before the zip is written. No examiner names and no ODP status field are written. |
| Independent check of the zip | `code/verify_profile_zip.py` | Written separately from the packager; shares no code. Rechecks dates, families and signatures from the zip and the raw records. |

Helper modules: `code/v1_fetch.py`, `code/odp_fetch.py`, `code/build_rounds.py` and `code/full_fetch.py` (download, document naming, PGPUB lookup). These are the versions the October 26–28 run used, not the October 6 versions.

## Raw download

The raw download is `data_v1/profile_corpus/`, about 2.7 GB. For every downloaded application it holds `raw/search_record.json`, `raw/documents.json`, `raw/transactions.json`, `raw/continuity.json`, `xml/*.xml.bin` and `pub/pgpub.*`. It is not in this repository: it is too large, and the zip (157 MB) exceeds GitHub's 100 MB file limit.

- Download dates: raw JSON written 26 October 2026 20:35 to 28 October 2026 02:09 (US Eastern). Some XML files came from a local cache of an earlier profile download on 9 October 2026 (`data_v1/profiles/apps`); the script reuses a cached file instead of downloading it again.
- `logs/fetch_log.jsonl`: one line per ODP API call (URL, status, bytes, seconds); 66,863 calls.
- `logs/v2_run.log`: console output of the run.
- `profile_corpus_v2.zip` SHA-256: `9f889f13fccd71fd27f24d936e8fba85099b12e1e011c9febe1c311e57392500`. Shared with the team on Google Drive.

## Rerun

Needs an ODP API key in the environment (`USPTO_API_KEY`). Calls are sequential and resumable; files already on disk are skipped. The scripts look for `data_v1/` one level above `code/`; in the original run this was `~/examinerbench/data_v1/`. It holds the sample inputs: `index.jsonl`, `examples/*.json` (cutoffs and first-action texts), and `apps/<app>/raw/continuity.json` and `xml/`. Outputs go to `data_v1/profile_corpus/` and `share/`.

```sh
python3 code/v2_profile_corpus.py --dry-run          # no API calls: prints the plan
python3 code/v2_profile_corpus.py --phase own
python3 code/v2_profile_corpus.py --phase control
python3 code/v2_profile_package.py                   # writes share/profile_corpus_v2.zip
python3 code/verify_profile_zip.py <project folder>
```

ODP records change over time, so a new download can differ from the October 2026 one. Use the zip with the SHA-256 above to reproduce later results exactly.
