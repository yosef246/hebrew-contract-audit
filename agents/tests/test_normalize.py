# tests/test_normalize.py — unit tests ל-normalize + שלושת המחסומים (size / preamble / monotonicity).
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from extract import normalize_section_numbers as norm, extract_clauses

NORM_CASES = [   # (name, input, expected) — normalize_section_numbers (string→string)
    ("1 reversed (.N end, supplier format)", "הצהרות הצדדים .1", "1. הצהרות הצדדים"),
    ("2 trailing sub N.N",                    "בזה חוזה 1.1",     "1.1 בזה חוזה"),
    ("3 trailing sub-sub N.N.N",              "השוכר 6.1.2",      "6.1.2 השוכר"),
    ("4 trailing main N.",                    "השוכר 2.",         "2. השוכר"),
    ("5 slash skip (38/1)",                   'עבודות תמ"א 38/1', 'עבודות תמ"א 38/1'),
    ("6 mid-line digit, not at $",            "השוכר יודיע 30 ימים", "השוכר יודיע 30 ימים"),
    ("7 REAL LeaseLink main (. text digit)",  ". הצהרות הצדדים1", "1. הצהרות הצדדים"),
    # מחסום 1 (size): שנה בקצה שורה לא מוזזת כסעיף
    ("8 threshold: 4-digit year not moved",   "נחתם בפתח תקווה שנת 2019", "נחתם בפתח תקווה שנת 2019"),
]

def _norm_tests():
    failed = 0
    for name, inp, expected in NORM_CASES:
        got = norm(inp)
        ok = got == expected
        print(f"{'PASS' if ok else 'FAIL'}  {name}")
        if not ok:
            print(f"      in={inp!r} exp={expected!r} got={got!r}"); failed += 1
    return failed

def _main_ids(clauses):
    return [c.section_number for c in clauses if c.section_number and "." not in c.section_number]

def test_preamble_boundary():
    doc = ("נחתם ביום 12.5.2020 בפתח תקווה בין הצדדים\n"
           "1. הצהרות הצדדים ובעל הדירה מצהיר בזאת כדלקמן\n"
           "1.1 כי הדירה ראויה למגורים ואין מניעה חוקית\n"
           "1.2 כי לא הוקנתה זכות לצד שלישי\n"
           "2. מטרת השכירות תהיה למגורים בלבד")
    clauses, t = extract_clauses(doc)
    assert "12.5.2020" in t.preamble_text, f"preamble missing date: {t.preamble_text!r}"
    assert clauses[0].section_number == "1", f"body should start at §1, got {clauses[0].section_number!r}"
    print("PASS  test_preamble_boundary")

def test_monotonicity_rejects_outlier():
    doc = ("1. סעיף ראשון עם תוכן ארוך דיו כאן\n"
           "2. סעיף שני עם תוכן\n"
           "40. סעיף חורג שקפץ\n"
           "3. סעיף שלישי עם תוכן")
    clauses, t = extract_clauses(doc)
    ids = _main_ids(clauses)
    assert ids == ["1", "2", "3"], f"expected [1,2,3], got {ids}"
    assert any(r["id"] == "40" for r in t.rejected_ids), f"40 not rejected: {t.rejected_ids}"
    print("PASS  test_monotonicity_rejects_outlier")

def test_year_never_becomes_section():
    doc = ("1. סעיף ראשון עם תוכן ארוך דיו כאן\n"
           "2. סעיף שני עם תוכן\n"
           "נחתם בשנת 2019 והושלם במעמד הצדדים\n"
           "3. סעיף שלישי עם תוכן")
    clauses, t = extract_clauses(doc)
    ids = _main_ids(clauses)
    assert ids == ["1", "2", "3"], f"expected [1,2,3], got {ids}"
    assert not any("2019" in (c.section_number or "") for c in clauses), "2019 leaked as section"
    print("PASS  test_year_never_becomes_section")

if __name__ == "__main__":
    failed = _norm_tests()
    for fn in (test_preamble_boundary, test_monotonicity_rejects_outlier, test_year_never_becomes_section):
        try:
            fn()
        except AssertionError as e:
            print(f"FAIL  {fn.__name__}: {e}"); failed += 1
    print(f"\n{'ALL PASS' if not failed else str(failed) + ' FAILED'}")
    sys.exit(1 if failed else 0)
