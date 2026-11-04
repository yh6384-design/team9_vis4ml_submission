# Episode rules and columns of `episodes.csv`

One row = one **episode**: an applicant reply and the examiner's next letter after it.
Built by `code/build_episode_table.py` (function `app_episodes()`), from each application's `transactions.csv`.
The table is not cut at any case date: it uses all data in the corpus.

## Rules

- **Reply** = transaction `A...` (response after a non-final rejection), `A.NE` (response after a final
  rejection) or `RCEX` (request for continued examination). Same-day replies count as one.
- **Prior letter** = the last mailed examiner letter before the reply: `MCTNF`, `MCTFR`, `MCTAV`, `MCTRS` or
  `MCTEQ`.
- **One episode per prior letter.** Only the first reply after a letter starts an episode; a supplemental reply
  before the examiner answers does not restart the clock. A reply with no letter before it, or a reply after the
  case already ended, is skipped.
- **Next letter** = the first mailed `MCTNF` (non-final), `MCTFR` (final), `MCTAV` (advisory), `MCTRS`
  (restriction), `MCTEQ` (Quayle), `MN/=.` (allowance) or `MABN*` (abandonment) after the reply.
- **Ending** = the first mailed `MN/=.` (allowance) or `MABN*` (abandonment) after the reply. `ABN9` is RCE
  bookkeeping, not an abandonment. A revived case keeps its first ending.
- **Signature** (rejections only): a next non-final / final rejection signed by someone other than the
  application's examiner is marked `actions_csv_signed_by_other` (60 episodes). Allowances, advisory actions,
  restrictions, Quayle actions and abandonments have no signature data and are marked
  `assigned_examiner_unverified`.
- **No status field is used.** Every outcome comes from the dated transactions.

## Worked example (one application, real codes)

```
2013-09-04  MCTNF  non-final rejection mailed        <- prior letter
2013-09-13  A...   applicant replies                 <- reply: the episode starts
2013-09-24  MN/=.  notice of allowance mailed        <- next letter (and the ending)
```

Episode: reply_date 2013-09-13, prior_type nonfinal_rejection, next_type allowance, next_days 11,
end_event allowance. In the prediction set, `y_allowance = 1`.

## Columns

| column | meaning |
|---|---|
| episode_id | `examiner_id:app_id:reply_date:next_doc_id` |
| examiner_id | the application's examiner (hashed name) |
| app_id | application number |
| family_root | smallest application number in the application's continuity family |
| art_unit_today | art unit from the USPTO record |
| reply_date | date of the reply that starts the episode |
| reply_codes | reply transaction codes on that day (`A...`, `A.NE`, `RCEX`) |
| reply_doc_ids | document ids filed with the reply (A..., A.NE, REM, CLM, RCEX, AMSB, A.AF, A.I.) |
| reply_text_paths | text files of those documents, when USPTO text exists |
| prior_code / prior_type / prior_date | the last examiner letter before the reply |
| prior_doc_ids | document id(s) of that letter |
| prior_signed | `true` / `false` / empty: whether the application's examiner signed the prior rejection |
| is_first_reply | True if this is the reply to the application's first non-final / final rejection |
| next_code / next_type / next_date | the next examiner letter after the reply (empty if none in the data) |
| next_doc_ids, next_text_paths | its document id(s) and text file(s) |
| next_days | days from reply to next letter |
| next_signed | `true` / `false` / empty, as for prior_signed |
| signature_basis | `actions_csv_verified`, `actions_csv_signed_by_other`, `no_uspto_text_unverified`, `assigned_examiner_unverified`, or empty (no next letter) |
| end_event / end_date | first allowance or abandonment after the reply (empty if none in the data) |
| shipped_until | date of the application's last transaction in the data |

## Counts

| | |
|---|---|
| episodes | 8,364 |
| applications with ≥ 1 episode | 4,417 of 5,369 |
| examiners | 181 |
| reply dates | 2008-08-13 to 2017-05-17 |
| first-reply episodes | 4,407 |
| episodes with reply text | 7,306 |
| signature_basis | verified 3,965; signed by other 60; unverified (no text) 96; assigned examiner 3,797; none 446 |
