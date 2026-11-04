"""Build the episode table: one row per "applicant reply -> examiner's next letter".

    python build_episode_table.py --corpus path/to/profile_corpus --out path/to/output

Input (the corpus folder written by profile_corpus/code/v2_profile_package.py, i.e. the unzipped
profile_corpus_v2.zip):
  profile_index.csv                 one row per (examiner_id, app_id): family_root, art_unit_today, ...
  actions.csv                       one row per CTNF/CTFR with signed_by_this_examiner (true / false / empty)
  apps/<app>/transactions.csv       event_date, event_code, event_description
  apps/<app>/catalog.csv            official_date, doc_code, direction, doc_id
  apps/<app>/text/                  file names only (for the text path columns)

Output
  episodes.csv          one row per episode, from all data in the corpus
  build_summary.json    counts and input sha1s

Rules
  Reply          transaction A... (response after non-final), A.NE (response after final) or RCEX (RCE).
                 Same-day replies are one reply. A reply starts an episode only if it is the first reply after the
                 last examiner letter (a supplemental reply before the next letter does not restart the clock).
  Prior letter   the last mailed examiner letter before the reply (MCTNF, MCTFR, MCTAV, MCTRS, MCTEQ).
  Next letter    the first mailed MCTNF, MCTFR, MCTAV, MCTRS, MCTEQ, MN/=. or MABN* after the reply.
  Ending         the first mailed MN/=. (allowance) or MABN* (abandonment) after the reply. ABN9 is RCE bookkeeping,
                 not an abandonment. A revived case keeps its first ending.
  Signature      a next letter that is a CTNF/CTFR: true / false from actions.csv signed_by_this_examiner
                 (actions_csv_verified / actions_csv_signed_by_other); no USPTO text = no_uspto_text_unverified.
                 NOA / advisory / restriction / Quayle / abandonment notices are not in actions.csv =
                 assigned_examiner_unverified.
"""
import argparse, csv, hashlib, json, os
from collections import Counter, defaultdict
from datetime import date

REPLY_CODES = {"A...", "A.NE", "RCEX"}
LETTER_CODES = {"MCTNF", "MCTFR", "MCTAV", "MCTRS", "MCTEQ"}
OA_CODES = {"MCTNF", "MCTFR"}
NEXT_TYPE = {"MCTNF": "nonfinal_rejection", "MCTFR": "final_rejection", "MCTAV": "advisory_action",
             "MCTRS": "restriction", "MCTEQ": "quayle_action", "MN/=.": "allowance"}
CAT_CODE = {"MCTNF": "CTNF", "MCTFR": "CTFR", "MCTAV": "CTAV", "MCTRS": "CTRS", "MCTEQ": "CTEQ", "MN/=.": "NOA",
            "MABN": "ABN"}
REPLY_DOCS = {"A...", "A.NE", "REM", "CLM", "RCEX", "AMSB", "A.AF", "A.I."}


def d(s):
    return date.fromisoformat(s)


def days(a, b):
    return (d(b) - d(a)).days


def rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def sha1(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def is_end(code):
    return code == "MN/=." or code.startswith("MABN")


def is_next(code):
    return code in LETTER_CODES or is_end(code)


def kind(code):
    return "abandonment" if code.startswith("MABN") else NEXT_TYPE.get(code, code)


def app_episodes(app, examiner_id, family_root, art_unit, corpus, sig):
    """All reply -> next-letter episodes in the data of one application."""
    T = sorted(rows(os.path.join(corpus, "apps", app, "transactions.csv")), key=lambda t: (t["event_date"], t["event_code"]))
    cat = rows(os.path.join(corpus, "apps", app, "catalog.csv"))
    tdir = os.path.join(corpus, "apps", app, "text")
    texts = os.listdir(tdir) if os.path.isdir(tdir) else []
    by_day_code = defaultdict(list)
    for c in cat:
        by_day_code[(c["official_date"], c["doc_code"])].append(c["doc_id"])

    def letter_doc(day, code):
        key = CAT_CODE["MABN"] if code.startswith("MABN") else CAT_CODE.get(code)
        ids = sorted(by_day_code.get((day, key), []))
        return ids

    def signature(day, code):
        if code not in OA_CODES:
            return "", "assigned_examiner_unverified"
        ids = letter_doc(day, code)
        flags = [sig.get(i) for i in ids]
        if any(f is False for f in flags):
            return "false", "actions_csv_signed_by_other"
        if any(f is True for f in flags):
            return "true", "actions_csv_verified"
        return "", "no_uspto_text_unverified"

    def text_path(day, doc_ids):
        return sorted({f"apps/{app}/text/{n}" for i in doc_ids for n in texts
                       if n.startswith(day) and i in n and n.endswith(".txt") and not n.endswith(".substantive.txt")})

    letters = [t for t in T if t["event_code"] in LETTER_CODES]
    first_oa = next((t["event_date"] for t in T if t["event_code"] in OA_CODES), None)
    reply_days = sorted({t["event_date"] for t in T if t["event_code"] in REPLY_CODES})
    eps, used_reply_after_letter = [], set()
    for r in reply_days:
        prior = [t for t in letters if t["event_date"] < r]
        if not prior:
            continue  # a reply with no examiner letter before it (e.g. preliminary) is not an episode
        p = prior[-1]
        # first reply after the last letter only
        if p["event_date"] in used_reply_after_letter:
            continue
        # an ending between the prior letter and this reply means the reply is after the case ended (e.g. revival)
        if any(is_end(t["event_code"]) and p["event_date"] < t["event_date"] <= r for t in T):
            continue
        used_reply_after_letter.add(p["event_date"])
        rcodes = sorted({t["event_code"] for t in T if t["event_date"] == r and t["event_code"] in REPLY_CODES})
        after = [t for t in T if t["event_date"] > r]
        nxt = next((t for t in after if is_next(t["event_code"])), None)
        end = next((t for t in after if is_end(t["event_code"])), None)
        n_sig, basis = signature(nxt["event_date"], nxt["event_code"]) if nxt else ("", "")
        p_sig, _ = signature(p["event_date"], p["event_code"])
        reply_ids = sorted({c["doc_id"] for c in cat if c["official_date"] == r and c["doc_code"] in REPLY_DOCS})
        next_ids = letter_doc(nxt["event_date"], nxt["event_code"]) if nxt else []
        eps.append(dict(
            episode_id=f"{examiner_id}:{app}:{r}:{next_ids[0] if next_ids else 'none'}",
            examiner_id=examiner_id, app_id=app, family_root=family_root, art_unit_today=art_unit,
            reply_date=r, reply_codes=";".join(rcodes), reply_doc_ids=";".join(reply_ids),
            reply_text_paths=";".join(text_path(r, reply_ids)),
            prior_code=p["event_code"], prior_type=kind(p["event_code"]), prior_date=p["event_date"],
            prior_doc_ids=";".join(letter_doc(p["event_date"], p["event_code"])), prior_signed=p_sig,
            is_first_reply=bool(first_oa and p["event_date"] == first_oa and p["event_code"] in OA_CODES
                                and not any(q["event_date"] < p["event_date"] for q in letters if q["event_code"] in OA_CODES)),
            next_code=nxt["event_code"] if nxt else "", next_type=kind(nxt["event_code"]) if nxt else "",
            next_date=nxt["event_date"] if nxt else "", next_doc_ids=";".join(next_ids),
            next_text_paths=";".join(text_path(nxt["event_date"], next_ids)) if nxt else "",
            next_days=days(r, nxt["event_date"]) if nxt else "",
            next_signed=n_sig, signature_basis=basis,
            end_event=("allowance" if end["event_code"] == "MN/=." else "abandonment") if end else "",
            end_date=end["event_date"] if end else "",
            shipped_until=T[-1]["event_date"] if T else "",
        ))
    return eps


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", required=True, help="folder with profile_index.csv, actions.csv and apps/")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    corpus, out_dir = a.corpus, a.out
    os.makedirs(out_dir, exist_ok=True)
    index = rows(os.path.join(corpus, "profile_index.csv"))
    sig = {}
    for r in rows(os.path.join(corpus, "actions.csv")):
        v = r["signed_by_this_examiner"].strip().lower()
        sig[r["doc_id"]] = True if v == "true" else False if v == "false" else None

    all_eps = []
    for r in index:
        all_eps += app_episodes(r["app_id"], r["examiner_id"], r["family_root"], r["art_unit_today"], corpus, sig)
    with open(os.path.join(out_dir, "episodes.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(all_eps[0].keys()))
        w.writeheader()
        w.writerows(all_eps)

    summ = dict(
        episodes=len(all_eps), applications=len(index),
        applications_with_episodes=len({e["app_id"] for e in all_eps}),
        examiners=len({e["examiner_id"] for e in all_eps}),
        reply_dates=[min(e["reply_date"] for e in all_eps), max(e["reply_date"] for e in all_eps)],
        episodes_by_next_type=dict(Counter(e["next_type"] or "none_shipped" for e in all_eps)),
        signature_basis=dict(Counter(e["signature_basis"] or "none" for e in all_eps)),
        reply_text_available=sum(bool(e["reply_text_paths"]) for e in all_eps),
        first_reply_episodes=sum(e["is_first_reply"] for e in all_eps),
        inputs_sha1={n: sha1(os.path.join(corpus, n)) for n in ["profile_index.csv", "actions.csv"]},
        builder_sha1=sha1(__file__),
    )
    with open(os.path.join(out_dir, "build_summary.json"), "w") as f:
        json.dump(summ, f, indent=1)
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
