# -*- coding: utf-8 -*-
"""Force every failure mode of the worksheet parser. A parser that only proves the
happy path is the false-green pattern this repo already paid for five times."""
import io, json, os, re, shutil, sys, importlib.util
HERE = os.path.dirname(os.path.abspath(__file__))
AGENTS = os.path.dirname(HERE)
os.chdir(os.path.dirname(AGENTS))
spec = importlib.util.spec_from_file_location(
    "pw", os.path.join(AGENTS, "parse_worksheet.py"))
pw = importlib.util.module_from_spec(spec); spec.loader.exec_module(pw)

SRC = "data/rental-02.worksheet.md"
TMP = os.path.join(os.environ.get("TEMP", "/tmp"), "ws_case.md")
_b = open(SRC, "rb").read()
for _e in ("utf-8-sig", "utf-16", "utf-8"):
    try:
        base = _b.decode(_e); break
    except UnicodeDecodeError:
        continue
base = base.lstrip("﻿").replace(chr(13)+chr(10), chr(10))
# נירול: מרוקנים כל מילוי קיים. אחרת הטסט תלוי בהתקדמות התיוג
# של יוסף — וישתנה מתחת לרגליו בכל פעם שיעבוד.
base = re.sub(r"^STATUS:.*$", "STATUS: ", base, flags=re.M)
base = re.sub(r"^NOTES:.*$", "NOTES: ", base, flags=re.M)

def case(name, mutate, expect_error):
    io.open(TMP, "w", encoding="utf-8", newline="\n").write(mutate(base))
    try:
        parsed = pw.parse(TMP)
        pw.apply(parsed, dry=True)
        got = None
    except Exception as e:
        got = f"{type(e).__name__}: {e}"
    ok = (got is not None) == expect_error
    print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    if got: print(f"        -> {got[:110]}")
    return 0 if ok else 1

def fill(t, sid, status, notes=""):
    return re.sub(rf"(## \d+/37 — סעיף {re.escape(sid)}\n(?:.|\n)*?STATUS:) (?:\n)?",
                  rf"\1 {status}\nNOTES: {notes}\n", t, count=1)

bad = 0
print("=== failure modes (must be caught) ===")
bad += case("invalid STATUS value",
            lambda t: fill(t, "1.1", "fine"), True)
bad += case("NOTES written but STATUS blank",
            lambda t: t.replace("STATUS: \nNOTES: ", "STATUS: \nNOTES: נראה מקפח", 1), True)
bad += case("a STATUS line deleted entirely",
            lambda t: t.replace("STATUS: \nNOTES: ", "NOTES: ", 1), True)
bad += case("clause block duplicated",
            lambda t: t + "\n## 99/37 — סעיף 1.1\n\nSTATUS: ok\nNOTES: x\n", True)
bad += case("unknown clause id in worksheet",
            lambda t: t.replace("— סעיף 1.1", "— סעיף 99.9", 1), True)

print("\n=== valid input (must pass and report honestly) ===")
def good(t):
    t = fill(t, "1.1", "ok", "מבוא סטנדרטי")
    t = fill(t, "12.2", "corrected", "פיצוי יומי בלי תקרה")
    return t
io.open(TMP, "w", encoding="utf-8", newline="\n").write(good(base))
p = pw.parse(TMP)
d, f = pw.apply(p, dry=True)
print(f"  parsed {len(p)} blocks, filled {f}")
assert f == 2, f
rows = {r["clause_id"]: r for r in d["annotations"]}
assert rows["1.1"]["expected_status"] == "ok" and rows["1.1"]["annotated_by"] == "yosef"
assert rows["12.2"]["expected_status"] == "corrected"
# שורה ריקה בגיליון לא משנה את מה שכבר ב-JSON — לא "מורידה ל-null".
# אחרת הטסט נשבר ברגע שיוסף מתייג סעיף כלשהו.
before = {r["clause_id"]: dict(r)
          for r in json.load(io.open(pw.J, encoding="utf-8"))["annotations"]}
for cid in [c for c in before if c not in ("1.1", "12.2")]:
    assert rows[cid] == before[cid], f"blank worksheet row altered {cid}"
print("  PASS  filled rows written, blank rows left untouched as null")
pw.report(d, f, len(p))

print("\nALL PASS" if not bad else f"\n{bad} FAILED"); sys.exit(1 if bad else 0)
