# Episode table: applicant reply → next examiner letter

This folder turns the examiner profile corpus into one table, `output/episodes.csv`:
**8,364 episodes from 4,417 patent applications and 181 examiners, with applicant replies dated 2008-08-13 to
2017-05-17.** Each episode links one applicant reply to the next examiner letter after it. The prediction target is
whether that letter is a **notice of allowance** rather than a **non-final or final office action**, among episodes
whose next letter is one of these three (7,014 rows).

## Where it sits in the pipeline

```
profile_corpus/code/          raw USPTO Open Data Portal downloads  ->  profile_corpus/share/profile_corpus_v2.zip
        |                     (v2_profile_corpus.py, v2_profile_package.py, verify_profile_zip.py)
        v
episode_table/code/           profile_corpus_v2.zip  ->  output/episodes.csv  ->  output/episodes_target.csv
                              (build_episode_table.py, make_target.py)
```

This folder reads only these files from the corpus: `profile_index.csv`, `actions.csv`, and
`apps/<app_id>/transactions.csv`, `catalog.csv` and the file names in `text/`.

## Files

| Path | What it is |
|---|---|
| `code/build_episode_table.py` | Builds `episodes.csv` from the corpus. Standard library only. |
| `code/make_target.py` | Keeps the allowance / non-final / final episodes and adds the 0/1 target `y_allowance`. |
| `run.sh` | Runs both steps and checks the results against `output/`. |
| `output/episodes.csv` | The 8,364-row episode table. |
| `output/episodes_target.csv` | The 7,014-row prediction set with `y_allowance`. |
| `output/build_summary.json` | Counts and sha1 of the inputs (`profile_index.csv`, `actions.csv`) and of the builder. |
| `docs/episode_rules.md` | The episode rules, a worked example, and what each column means. |

## Run

From the repository root, after `profile_corpus/share/profile_corpus_v2.zip` exists:

```bash
bash episode_table/run.sh                       # default corpus: profile_corpus/share/profile_corpus_v2.zip
bash episode_table/run.sh path/to/profile_corpus_v2.zip      # or a zip somewhere else
bash episode_table/run.sh path/to/profile_corpus             # or an unzipped corpus folder
```

It unzips into `episode_table/work/` (ignored by git), rebuilds both tables, and prints whether each one is
identical to the copy in `output/`. It takes about 15 seconds. Needs Python 3 and pandas.

To run the two steps by hand:

```bash
python3 episode_table/code/build_episode_table.py --corpus <unzipped profile_corpus folder> --out <out folder>
python3 episode_table/code/make_target.py --episodes <out folder>/episodes.csv --out <out folder>/episodes_target.csv
```

## How the table is built (step by step)

For each of the 5,369 applications in `profile_index.csv`:

1. **Find replies.** A reply is a transaction with code `A...` (reply to a non-final), `A.NE` (reply to a final)
   or `RCEX` (request for continued examination). Replies on the same day count as one.
2. **Keep only the first reply after each examiner letter.** A second, supplemental reply before the examiner
   answers does not start a new episode. A reply with no examiner letter before it (e.g. a preliminary
   amendment) is skipped. A reply after the case already ended (e.g. after a revival) is skipped.
3. **Find the next letter.** The first mailed `MCTNF` (non-final), `MCTFR` (final), `MCTAV` (advisory),
   `MCTRS` (restriction), `MCTEQ` (Quayle), `MN/=.` (allowance) or `MABN*` (abandonment) after the reply.
4. **Record extras:** days from reply to next letter, the prior letter, whether the examiner signed the
   rejection (from `actions.csv`), how the case ended, and text file paths.

Result: 8,364 episodes. Only 4,417 of the 5,369 applications have at least one episode (the rest have no reply
after an examiner letter in the data). 181 examiners. Reply dates 2008-08-13 to 2017-05-17.

Next letter types in the 8,364 rows:

| next_type | rows |
|---|---|
| allowance | 2,893 |
| final_rejection | 2,817 |
| nonfinal_rejection | 1,304 |
| advisory_action | 866 |
| none (no next letter in the data) | 446 |
| quayle_action | 18 |
| restriction | 11 |
| abandonment | 9 |

**The target** (`make_target.py`): keep only rows whose next letter is allowance, final or non-final:
2,893 + 2,817 + 1,304 = **7,014 rows** (4,154 applications, 181 examiners). `y_allowance = 1` for allowance,
0 otherwise. Allowance share = 2,893 / 7,014 = **41.2%**.

## Reproducibility check

The reference outputs in `output/` were built from the corpus with these input hashes
(also in `output/build_summary.json`):

| corpus file | sha1 |
|---|---|
| `profile_index.csv` | `4cbe10c3bcd9824fc000feb2301d7ca41fcfe1a2` |
| `actions.csv` | `d129a0f9d2eaf67af188e0cd9029102b29e76c16` |

If a rebuilt corpus has the same two hashes and the same `apps/` files, `run.sh` reports both tables identical.
