"""Audit examiner identity and next-notification labels on a seeded sample.

The episode table supplies the recorded values and the sampling population.
The audit checks those values against saved USPTO Open Data Portal (ODP)
records, transaction histories, and available letter texts:

1. Identity: hash the examiner name in the ODP record and compare it with the
   episode's examiner ID. Separately, check the prior and next letters for a
   slash-delimited signature line containing the surname or matching initials.
   An ID match alone does not establish who signed either letter.
2. Label: check whether the first relevant transaction strictly after the
   reply has the recorded notification type and date. The sampled targets
   are notices of allowance and final or non-final rejections. Other relevant
   events, such as advisory actions and abandonment, can precede those targets.
3. Reply: check that a transaction with a recorded reply code appears on the
   recorded reply date.

Records with a failed check or no extracted prior signature line are listed
for manual review with available text excerpts. If no signature line is
extracted for a letter, its signature-match field is left blank.

Usage:
    python3 audit/code/audit_50.py EPISODES_CSV CORPUS_APPS_DIR OUT_DIR [--n 50] [--seed 20261103]
"""
import argparse
import csv
import glob
import hashlib
import json
import os
import random
import re

ELIGIBLE_NEXT = {"allowance", "final_rejection", "nonfinal_rejection"}
NEXT_CODES = {"MCTNF": "nonfinal_rejection", "MCTFR": "final_rejection", "MN/=.": "allowance"}
# Other mailed letters that end an episode under the label rule (advisory action,
# restriction, Quayle action, abandonment); interview summaries do not.
OTHER_LETTERS = {"MCTAV", "MCTRS", "MCTEQ"}
SIG = re.compile(r"^\s*/([^/\n]{3,60})/\s*$", re.M)


def examiner_hash(name):
    return "ex_" + hashlib.sha1(name.encode()).hexdigest()[:10]


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def text_for(apps_dir, app_id, doc_ids):
    for doc in (doc_ids or "").split(";"):
        if not doc:
            continue
        hits = [h for h in glob.glob(os.path.join(apps_dir, app_id, "text", f"*_{doc}.txt"))
                if not h.endswith(".substantive.txt")]
        if hits:
            with open(sorted(hits)[0], encoding="utf-8", errors="replace") as f:
                return os.path.basename(hits[0]), f.read()
    return None, None


def signers(text):
    return [s.strip() for s in SIG.findall(text or "")]


def surname(odp_name):
    return odp_name.split(",")[0].strip().upper()


def initials_match(odp_name, sig):
    """Check initials using all given names or only the first, plus the surname."""
    if not re.fullmatch(r"(?:[A-Z]\.?\s*){2,4}", sig.strip()):
        return False
    letters = re.sub(r"[^A-Z]", "", sig)
    sur, _, given = odp_name.partition(",")
    g = [w[0] for w in given.split() if w]
    s0 = sur.strip()[:1]
    return letters in {"".join(g) + s0, (g[0] if g else "") + s0}


def signed_by(odp_name, sig_list):
    sn = surname(odp_name)
    return any(sn in s.upper() or initials_match(odp_name, s) for s in sig_list)


def events(apps_dir, app_id):
    t = load_json(os.path.join(apps_dir, app_id, "raw", "transactions.json"))
    bag = t["patentFileWrapperDataBag"][0]["eventDataBag"]
    return sorted((e["eventDate"], e["eventCode"]) for e in bag)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("episodes_csv")
    ap.add_argument("apps_dir")
    ap.add_argument("out_dir")
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--seed", type=int, default=20261103)
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)

    with open(a.episodes_csv, newline="") as f:
        rows = [r for r in csv.DictReader(f)
                if r["next_type"] in ELIGIBLE_NEXT and r["prior_type"] in ("nonfinal_rejection", "final_rejection", "advisory_action")]
    rows.sort(key=lambda r: r["episode_id"])
    sample = random.Random(a.seed).sample(rows, a.n)

    out, review = [], []
    for r in sample:
        app = r["app_id"]
        meta = load_json(os.path.join(a.apps_dir, app, "raw", "search_record.json"))["applicationMetaData"]
        odp_name = meta.get("examinerNameText", "")
        prior_file, prior_text = text_for(a.apps_dir, app, r["prior_doc_ids"])
        next_file, next_text = text_for(a.apps_dir, app, r["next_doc_ids"])
        prior_sigs, next_sigs = signers(prior_text), signers(next_text)

        ev = events(a.apps_dir, app)
        after = [(d, c) for d, c in ev if d > r["reply_date"]
                 and (c in NEXT_CODES or c in OTHER_LETTERS or c.startswith("MABN"))]
        first = after[0] if after else ("", "")
        reply_ok = any(d == r["reply_date"] and c in r["reply_codes"].split(";") for d, c in ev)

        rec = {
            "episode_id": r["episode_id"], "app_id": app, "reply_date": r["reply_date"],
            "prior_type": r["prior_type"], "label_next_type": r["next_type"], "label_next_date": r["next_date"],
            "odp_examiner_hash_matches": examiner_hash(odp_name) == r["examiner_id"],
            "prior_text_file": prior_file or "", "prior_signers": " | ".join(prior_sigs),
            "prior_signed_by_odp_examiner": signed_by(odp_name, prior_sigs) if prior_sigs else "",
            "next_text_file": next_file or "", "next_signers": " | ".join(next_sigs),
            "next_signed_by_odp_examiner": signed_by(odp_name, next_sigs) if next_sigs else "",
            "raw_first_letter_code": first[1], "raw_first_letter_date": first[0],
            "label_matches_raw": NEXT_CODES.get(first[1]) == r["next_type"] and first[0] == r["next_date"],
            "reply_transaction_found": reply_ok,
            "pipeline_signature_basis": r["signature_basis"],
        }
        out.append(rec)
        failed = [k for k in ("odp_examiner_hash_matches", "prior_signed_by_odp_examiner",
                              "next_signed_by_odp_examiner", "label_matches_raw", "reply_transaction_found")
                  if rec[k] is False]
        if failed or not prior_sigs:
            review.append({"episode_id": r["episode_id"], "failed_checks": failed or ["no_prior_signature_line"],
                           "odp_examiner": odp_name,
                           "prior_tail": (prior_text or "")[-400:], "next_tail": (next_text or "")[-400:]})

    with open(os.path.join(a.out_dir, "audit_50.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    with open(os.path.join(a.out_dir, "audit_50_review.json"), "w") as f:
        json.dump(review, f, indent=1)

    def count(key):
        vals = [o[key] for o in out if o[key] != ""]
        return f"{sum(1 for v in vals if v is True)}/{len(vals)}"

    summary = {k: count(k) for k in ("odp_examiner_hash_matches", "prior_signed_by_odp_examiner",
                                     "next_signed_by_odp_examiner", "label_matches_raw", "reply_transaction_found")}
    summary["n"] = len(out)
    summary["records_for_manual_review"] = len(review)
    with open(os.path.join(a.out_dir, "audit_50_summary.json"), "w") as f:
        json.dump(summary, f, indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
