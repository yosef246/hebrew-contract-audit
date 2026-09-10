# -*- coding: utf-8 -*-
"""make_worksheet — build the annotation worksheet: clause_id + clause text + fill-in lines.
Lives under data/ (gitignored) because it contains contract text."""
import io, os, re, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
os.chdir(ROOT)
from extract import extract_clauses

raw = io.open("fixtures/rental-02.txt", encoding="utf-8").read()
clauses, tel = extract_clauses(raw)
units = [c for c in clauses if c.analyze]
ids = [a["clause_id"] for a in json.load(
    io.open("fixtures/annotations/rental-02.annotations.json", encoding="utf-8"))["annotations"]]
assert [c.section_number for c in units] == ids, "worksheet would drift from the annotation file"

CAV = {
    "6.2-1": "גדם — פירוט התשלומים לא שרד את החילוץ. שופט על מה שיש.",
    "6.2-2": "החוזה ממספר שני סעיפים '6.2'. הפיצול לפי מיקום במסמך, לא לפי תוכן.",
    "16.1":  "יחידה ממוזגת: סעיף הכתובות + בלוק החתימה. עגן את התווית על סעיף הכתובות.",
}

# זרעים מהתוויות שכבר ב-JSON: ייצור מחדש לעולם לא מאבד עבודה שנשמרה.
SEED = {r["clause_id"]: (r["expected_status"], r["notes"])
        for r in json.load(io.open("fixtures/annotations/rental-02.annotations.json",
                                   encoding="utf-8"))["annotations"]
        if r["expected_status"]}

L = ["# rental-02 — גיליון תיוג",
     "",
     f"{len(units)} יחידות ניתוח, לפי סדר החוזה. מלא `STATUS:` ו-`NOTES:` בכל בלוק.",
     "",
     "`STATUS` = אחד מ: `ok` / `corrected` / `unverified_concern` / `requires_human_review` / ריק (לא הוכרע)",
     "",
     "- `ok` — תקין, אין חשש",
     "- `corrected` — בעייתי **וגם** יש מקור בקורפוס החוקי שתומך בסימון",
     "- `unverified_concern` — נראה חורג מנורמות אבל אין מקור שמעגן",
     "- `requires_human_review` — דורש עין של עו\"ד, מחוץ להישג הקורפוס",
     "",
     "`NOTES` = משפט קצר. **אל תעתיק טקסט מהסעיף** — זה מה ששומר את קובץ התוויות נקי מ-PII.",
     "",
     "שדה ריק (`____`) הוא NULL — לא ערך ולא פגם. אל תסמן סעיף בגללו.",
     "",
     "---", ""]

for i, c in enumerate(units, 1):
    L.append(f"## {i}/{len(units)} — סעיף {c.section_number}")
    if c.parent_heading:
        L.append(f"*תחת: {c.parent_heading.strip()}*")
    if c.section_number in CAV:
        L.append(f"> ⚠️ {CAV[c.section_number]}")
    _st, _nt = SEED.get(c.section_number, (None, None))
    L += ["", "```", c.text.strip(), "```", "",
          "STATUS: " + (_st or ""), "NOTES: " + (_nt or ""), "", "---", ""]

os.makedirs("data", exist_ok=True)
P = "data/rental-02.worksheet.md"
# הגיליון git-ignored. דריסת מילוי שטרם נכתב ל-JSON אינה ניתנת לשחזור.
if os.path.exists(P) and "--force" not in sys.argv:
    _raw = open(P, "rb").read()
    _prev = ""
    for _enc in ("utf-8-sig", "utf-16", "utf-8"):
        try:
            _prev = _raw.decode(_enc); break
        except UnicodeDecodeError:
            continue
    _ids, _cur = [], None
    for _l in _prev.split(chr(10)):
        if _l.startswith("## ") and "סעיף " in _l:
            _cur = _l.split("סעיף ", 1)[1].strip()
        elif _l.startswith("STATUS:") and _l[7:].strip() and _cur:
            _ids.append(_cur)
    _extra = sorted(set(_ids) - set(SEED))
    if _extra:
        raise SystemExit(
            "refusing to overwrite " + P + ": it holds labels for " + ", ".join(_extra) +
            " that are not committed to the JSON. run: "
            "python agents/parse_worksheet.py --write   (or --force to discard)")
io.open(P, "w", encoding="utf-8", newline="\n").write("\n".join(L))
print("written:", P, "|", len(units), "units |", os.path.getsize(P), "bytes")
