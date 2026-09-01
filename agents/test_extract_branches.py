# test_extract_branches.py — unit tests ישירים על ה-branches של extract_clauses.
# input סינתטי בקוד = בדיקת קוד (מותר), לא הרצת extractor על "מסמך אמיתי".
from extract import (extract_clauses, WINDOW_SIZE,
                     MIN_SECTIONS, MAX_AVG_CHARS, MAX_SINGLE_CHARS)

def _sec(n: int, chars: int) -> str:
    """סעיף ממוספר 'n. ' + מילוי עד ~chars תווים."""
    head = f"{n}. "
    return head + "א" * max(0, chars - len(head))

def _doc(sections: list[str]) -> str:
    return "\n".join(sections)

def test_regex_clean():
    clauses, t = extract_clauses(_doc([_sec(i, 60) for i in range(1, 6)]))
    assert t.path == "regex", t.path
    assert t.regex_sections == 5
    assert t.fallback_reason is None

def test_count_fallback():
    clauses, t = extract_clauses(_doc([_sec(1, 60), _sec(2, 60)]))   # 2 < MIN_SECTIONS(3)
    assert t.path == "fallback", t.path
    assert "numbered sections" in t.fallback_reason

def test_avg_fallback():                                             # ← ה-branch שביקשת
    clauses, t = extract_clauses(_doc([_sec(i, 2500) for i in range(1, 4)]))  # 3 סעיפים, avg 2500 > 2000
    assert t.path == "fallback", t.path
    assert "avg section length" in t.fallback_reason
    assert t.regex_sections == 3          # ה-count עבר (3); מה שהפיל זה ה-avg

def test_single_char_window_mixed():
    # סעיף 1 = 4500 > MAX_SINGLE_CHARS(4000) → מחולן; avg=(4500+300)/4=1200 < 2000 → לא avg-fallback
    clauses, t = extract_clauses(_doc([_sec(1, 4500), _sec(2, 100), _sec(3, 100), _sec(4, 100)]))
    assert t.path == "mixed", t.path
    assert any(len(c.text) <= WINDOW_SIZE for c in clauses)   # קיימות פיסות מחולנות

def test_subsection_absorbed():
    doc = "1. הגדרות.\n1.א תת סעיף ראשון.\n1.1 תת סעיף שני.\n2. שני.\n3. שלישי."
    clauses, t = extract_clauses(doc)
    sec1 = next(c for c in clauses if c.section_number == "1")
    assert "1.א" in sec1.text and "1.1" in sec1.text   # תת-סעיפים נבלעים לתוך ההורה
    assert t.regex_sections == 3

if __name__ == "__main__":
    tests = [test_regex_clean, test_count_fallback, test_avg_fallback,
             test_single_char_window_mixed, test_subsection_absorbed]
    for fn in tests:
        fn()
        print(f"PASS  {fn.__name__}")
    print(f"\nAll {len(tests)} extract branch tests passed. "
          f"(MIN_SECTIONS={MIN_SECTIONS}, MAX_AVG_CHARS={MAX_AVG_CHARS}, MAX_SINGLE_CHARS={MAX_SINGLE_CHARS})")
