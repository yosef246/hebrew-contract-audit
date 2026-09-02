# tests/test_normalize.py — unit tests ל-normalize_section_numbers.
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from extract import normalize_section_numbers as norm

CASES = [
    # (name, input, expected)
    ("1 reversed (.N end, supplier format)", "הצהרות הצדדים .1", "1. הצהרות הצדדים"),
    ("2 trailing sub N.N",                    "בזה חוזה 1.1",     "1.1 בזה חוזה"),
    ("3 trailing sub-sub N.N.N",              "השוכר 6.1.2",      "6.1.2 השוכר"),
    ("4 trailing main N.",                    "השוכר 2.",         "2. השוכר"),
    ("5 slash skip (38/1)",                   'עבודות תמ"א 38/1', 'עבודות תמ"א 38/1'),   # unchanged
    ("6 mid-line digit, not at $",            "השוכר יודיע 30 ימים", "השוכר יודיע 30 ימים"),  # unchanged
    # case 7 — הפורמט האמיתי של LeaseLink (נקודה יתומה בתחילה + ספרה חשופה בסוף):
    ("7 REAL LeaseLink main (. text digit)",  ". הצהרות הצדדים1", "1. הצהרות הצדדים"),
]

if __name__ == "__main__":
    failed = 0
    for name, inp, expected in CASES:
        got = norm(inp)
        ok = got == expected
        print(f"{'PASS' if ok else 'FAIL'}  {name}")
        if not ok:
            print(f"      in : {inp!r}")
            print(f"      exp: {expected!r}")
            print(f"      got: {got!r}")
            failed += 1
    print(f"\n{len(CASES) - failed}/{len(CASES)} passed.")
    sys.exit(1 if failed else 0)
