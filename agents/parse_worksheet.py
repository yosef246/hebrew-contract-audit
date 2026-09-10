# -*- coding: utf-8 -*-
"""parse_worksheet — ממיר את data/rental-02.worksheet.md חזרה ל-JSON, עם אימות.

הבחנה מרכזית: STATUS ריק = *טרם הוכרע*, לא "הוכרע כ-null". שורות כאלה נשארות null
ומדווחות בקול — אחרת מסת המדידה מצטמצמת בלי שאיש רואה.
"""
import datetime, io, json, os, re, sys, collections
HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(os.path.dirname(HERE))

VALID = {"ok", "corrected", "unverified_concern", "requires_human_review"}
WS = "data/rental-02.worksheet.md"
J  = "fixtures/annotations/rental-02.annotations.json"

def parse(path=WS):
    # עורכי Windows שומרים לעתים UTF-16 עם BOM — לא להפיל על זה את המשתמש.
    b = open(path, "rb").read()
    for enc in ("utf-8-sig", "utf-16", "utf-8"):
        try:
            txt = b.decode(enc); break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError(f"{path}: cannot decode as utf-8/utf-8-sig/utf-16")
    txt = txt.lstrip("﻿")
    blocks = re.split(r"^## \d+/\d+ — סעיף ", txt, flags=re.M)[1:]
    out = {}
    for b in blocks:
        sid = b.split("\n", 1)[0].strip()
        body = re.sub(r"```.*?```", "", b, flags=re.S)          # never read inside the clause text
        m_s = re.search(r"^STATUS:[ \t]*(.*)$", body, flags=re.M)
        m_n = re.search(r"^NOTES:[ \t]*(.*)$", body, flags=re.M)
        if m_s is None or m_n is None:
            raise ValueError(f"clause {sid}: worksheet block missing STATUS/NOTES line")
        st = (m_s.group(1).strip().strip("`").lower() or None)   # OK / Ok / ok — הכל עובר
        nt = m_n.group(1).strip() or None
        if st is not None and st not in VALID:
            raise ValueError(f"clause {sid}: STATUS {st!r} not one of {sorted(VALID)}")
        if st is None and nt:
            raise ValueError(f"clause {sid}: NOTES written but STATUS left blank — decide or clear")
        if sid in out:
            raise ValueError(f"clause {sid}: appears twice in the worksheet")
        out[sid] = (st, nt)
    return out

def apply(parsed, dry=True, today=None):
    today = today or datetime.date.today().isoformat()   # תאריך ההכרעה האמיתי, לא קבוע
    d = json.load(io.open(J, encoding="utf-8"),
                  object_pairs_hook=collections.OrderedDict)
    ids = [r["clause_id"] for r in d["annotations"]]
    if sorted(parsed) != sorted(ids):
        miss = [i for i in ids if i not in parsed]
        extra = [i for i in parsed if i not in ids]
        raise ValueError(f"worksheet/JSON key mismatch — missing {miss}, unexpected {extra}")
    filled = 0
    for r in d["annotations"]:
        st, nt = parsed[r["clause_id"]]
        if st is None:
            continue                       # טרם הוכרע — נשאר null, לא נכתב
        r["expected_status"], r["notes"] = st, nt
        r["annotated_by"], r["annotated_at"] = "yosef", today
        filled += 1
    if not dry:
        leaks = pii_leaks(d)          # לפני הכתיבה, לא אחריה
        if leaks:
            raise ValueError(
                f"refusing to write: notes in {leaks} copy clause text verbatim. "
                f"rewrite them in your own words — this file is pushed to GitHub.")
        io.open(J, "w", encoding="utf-8", newline="\n").write(
            json.dumps(d, ensure_ascii=False, indent=2) + "\n")
    return d, filled

def pii_leaks(d):
    """notes בעברית תקינות. מה שאסור הוא העתקת טקסט מהסעיף — טקסט החוזה מכיל
    ת.ז וטלפון אמיתיים, וקובץ התוויות נדחף ל-GitHub. 5+ מילים רצופות = העתקה."""
    contract = re.sub(r"\s+", " ", io.open("fixtures/rental-02.txt", encoding="utf-8").read())
    out = []
    for r in d["annotations"]:
        w = re.sub(r"\s+", " ", (r["notes"] or "").strip()).split()
        for i in range(len(w) - 4):
            if " ".join(w[i:i + 5]) in contract:
                out.append(r["clause_id"]); break
    return out

def report(d, filled, total):
    c = collections.Counter(str(r["expected_status"]) for r in d["annotations"])
    print(f"\nfilled: {filled}/{total}   left blank (not yet decided): {total-filled}")
    print("distribution:", dict(c))
    scored = [r for r in d["annotations"]
              if r["expected_status"] is not None and r["annotated_by"] != "gervis-draft"]
    print(f"scored comparisons this fixture would contribute: {len(scored)}")
    if scored:
        nonok = sum(1 for r in scored if r["expected_status"] != "ok")
        base = 100.0 * (len(scored) - nonok) / len(scored)
        print(f"non-ok labels: {nonok}/{len(scored)}  ->  an 'always ok' analyzer scores {base:.1f}%")
    leaks = pii_leaks(d)
    print("PII scan on rows: verbatim clause text =",
          "none" if not leaks else f"LEAK in {leaks}")

if __name__ == "__main__":
    p = parse()
    d, f = apply(p, dry="--write" not in sys.argv)
    report(d, f, len(p))
    print("\nDRY RUN — nothing written. rerun with --write to apply."
          if "--write" not in sys.argv else "\nWRITTEN to " + J)
