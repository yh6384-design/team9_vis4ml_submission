# Data card 


## Source and license
Public USPTO Patent File Wrapper records (Open Data Portal): application metadata, transaction histories, document
lists and office-action texts, downloaded by `profile_corpus/code/` and packaged as `profile_corpus_v2.zip`
(inputs sha1: `profile_index.csv` 4cbe10c3…, `actions.csv` d129a0f9…; full list in the zip's MANIFEST.csv).
Examiner names are replaced by hashed ids (`ex_` + sha1[:10]). No application status field is used.


## Units
* **Episode** = applicant reply → the examiner's next letter (rules: `episode_table/docs/episode_rules.md`).
* **Checkpoint** = the reply date of an episode in the modelling cohort.
* **Label** `y` = 1 if the next letter is a notice of allowance, 0 if a non-final or final rejection
  (observed-event population: episodes whose next letter is another type, or not yet observed, are excluded).

## Construction counts
| Step | Rows | Notes |
|---|---|---|
| applications in corpus | 5,369 | 181 examiners |
| episodes | 8,364 | 4,417 applications; replies 2008-08-13 … 2017-05-17 |
| with target (NOA / CTNF / CTFR) | 7,014 | allowance 41.2% |
| prior letter = rejection or advisory | 7,010 | |
| label after block end (dropped) | dev 265, train 368 | labels must exist before the block ends |
| family already in an earlier block (dropped) | dev 427, test 355 | family purge |
| **cohort** | **5,595** | train 3,055 · dev 1,027 · test 1,513 |
(source: `VML_OUT/cohort/cohort_counts.json`; re-check against the official run)

## Blocks and confirmed identity (rule: < 80% confirmed → descriptive only)
| Block | Dates (reply) | Checkpoints | Families | Allowance | Confirmed share |
|---|---|---|---|---|---|
| train | 2008–2013 | 3,055 | 1,923 | 0.379 | 0.889 |
| dev | 2014 | 1,027 | 861 | 0.500 | 0.922 |
| test | 2015–2017 | 1,513 | 1,089 | 0.468 | 0.897 |
Dev halves (by family, seed 20261119): search 512 rows / 430 families; assessment 515 / 431.

## Columns of `features.csv` (one row per checkpoint)
| Column | Meaning |
|---|---|
| episode_id, examiner_id, app_id, family_root | ids (examiner hashed; family = smallest application number in the continuity family) |
| block, part, primary | time block; train / dev_search / dev_assess / test; 1 = confirmed examiner identity |
| y, reply_date, reply_year, prior_type, prior_date, next_type, next_date | label and dates |
| art_unit, tc | art unit; technology center = first two digits + "00" |
| round_n, round_c, rce | reply number within the application (round_c capped at 3 = "3+"); RCE flag |
| filing_date, filing_year, elapsed_years | from `profile_index.csv` |
| g101, g102, g103, g112, g_dp, ground_text_ok, ground_doc | rejection grounds read from the latest rejection letter mailed on or before the answered letter |
| *_doc_ids, *_text_paths | USPTO document ids / text files for provenance (V5) |

## Rejection-ground extraction check 
Regex on the letter text: `rejected under (pre-AIA) 35 U.S.C. (§) 101|102|103|112` and the section headings.
Text found for 99.7% of checkpoints *(first run)*. Rates when found: §101 11.5%, §102 49.5%, §103 75.1%, §112 34.6%.
**By-hand check of `VML_OUT/features/ground_spotcheck.csv`:** all letters fully correct. 

## Known limitations
* Observed-event population; pending cases excluded.
* Examiner history is short (median 7 / 17 / 23 earlier outcomes in train / dev / test).
* Allowance rate rises over time (0.38 → 0.50 → 0.47).
* Art unit is "today's" art unit from the record, not necessarily the art unit at the checkpoint.
* 50-record audit: 46/50 identities confirmed from the answered letter; 3 only from a later letter; 1 discrepant.
