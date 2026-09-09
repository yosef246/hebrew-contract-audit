# -*- coding: utf-8 -*-
"""tests/test_diag_placeholder_offline.py — מריץ את diag_placeholder מקצה לקצה בלי רשת.

קיים בגלל באג אמיתי: diag_placeholder נמסר פעם אחת עם GraphState חסר contractId/
originalContract. הוא "יצא נקי" בקוד 2 רק מפני ששער ה-credentials חוסם לפני השורה
השבורה — כלומר בדיקת-השער העידה על השער, לא על הקוד שמאחוריו. הטסט הזה מזריק
RAG ו-LLM מזויפים ומריץ את כל המסלול, כך שכל שורה אחרי השער באמת מתבצעת.

מגבלה: קורא fixtures/*.txt שהם git-ignored (PII), ולכן ב-clone נקי הוא ייכשל ב-
FileNotFoundError. שומר-הדריפט הזה יכול לפעול רק אצל מי שה-fixtures אצלו מקומית —
לא ב-CI.
"""
import glob, io, os, re, sys, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
AGENTS = os.path.join(ROOT, "agents")
sys.path.insert(0, AGENTS)

os.environ.setdefault("ANTHROPIC_API_KEY", "stub-offline-test")
os.environ.setdefault("RAG_INTERNAL_TOKEN", "stub-offline-test")

import graph
from state import AnalyzerVerdict, Source

CALLS: list[tuple[str, str | None]] = []

EXPECTED_UNITS = 5      # ראה CLAUDE.md, "Empty form fields are NULL, not content"

def _blank_bearing_units() -> dict[str, list[str]]:
    """אמת-קרקע עצמאית מה-fixtures: אילו יחידות-ניתוח באמת נושאות רצף '____'.
    לא נגזר מ-TARGETS — אחרת הבדיקה מעגלית ותעבור גם אם TARGETS יצומצם או יתרוקן.
    סורק את כל fixtures/*.txt ולא רשימה קשיחה: רשימה קשיחה הייתה חולקת עם TARGETS
    את אותה הנחת-תיחום, ו-fixture שלישי נושא-'____' היה חומק משתיהן בשקט."""
    from extract import extract_clauses
    out: dict[str, list[str]] = {}
    for path in sorted(glob.glob(os.path.join(ROOT, "fixtures", "*.txt"))):
        clauses, _ = extract_clauses(io.open(path, encoding="utf-8").read())
        ids = [c.section_number for c in clauses
               if c.analyze and re.search(r"_{3,}", c.text)]
        if ids:                     # sample-00 ואחרים ללא שדות ריקים — לא נכנסים
            out[os.path.splitext(os.path.basename(path))[0]] = ids
    return out

def _fake_retrieve(query, k=4):
    CALLS.append(("retrieve", query[:30]))
    return [Source(marker="1", label="חוק דמה", section_number="1",
                   text="מקור דמה", similarity=0.9)], 0

def _fake_structured(schema, messages, *, node, clause_id=None, attempts=None):
    CALLS.append(("llm", clause_id))
    return AnalyzerVerdict(analysis="ניתוח דמה", is_problematic=False, severity=2,
                           reason="offline-test", used_markers=[],
                           norm_deviation_without_source=True, missing_info=["offline"])

def test_diag_placeholder_runs_end_to_end():
    # בלי איפוס, קריאה שנייה באותו תהליך תעבור על רשומות מהקריאה הקודמת —
    # הבדיקה llm == expected תסתפק בנתונים ישנים גם אם הריצה הנוכחית לא ניתחה כלום.
    CALLS.clear()
    # ה-stubs נכתבים על graph ברמת המודול — חייבים לשחזר ב-finally, אחרת כל טסט
    # אחר באותו תהליך (למשל pytest agents/tests/) ירוץ מול פייקים ויעבור על לא-כלום.
    real_retrieve, real_structured = graph._retrieve_with_retries, graph._structured
    graph._retrieve_with_retries = _fake_retrieve
    graph._structured = _fake_structured
    try:
        spec = importlib.util.spec_from_file_location(
            "diag_ph", os.path.join(AGENTS, "diag_placeholder.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        # אמת-קרקע מה-fixtures, לא מ-TARGETS: תופס גם צמצום של TARGETS וגם שינוי
        # ב-fixtures/extractor שמזיז אילו סעיפים נושאים '____'.
        ground = _blank_bearing_units()
        total = sum(len(v) for v in ground.values())
        assert total == EXPECTED_UNITS, f"fixtures carry {total} blank-bearing units, expected {EXPECTED_UNITS}"
        assert ground == mod.TARGETS, f"TARGETS={mod.TARGETS} drifted from fixtures={ground}"

        rc = mod.main()
        llm = sum(1 for c in CALLS if c[0] == "llm")
        assert rc == 0, f"main() returned {rc}"
        assert llm == EXPECTED_UNITS, f"analyzed {llm} clauses, fixtures declare {EXPECTED_UNITS}"
        print(f"PASS  test_diag_placeholder_runs_end_to_end ({llm}/{EXPECTED_UNITS} units)")
    finally:
        graph._retrieve_with_retries = real_retrieve
        graph._structured = real_structured

if __name__ == "__main__":
    try:
        test_diag_placeholder_runs_end_to_end()
        print("\nALL PASS")
    except AssertionError as e:
        print(f"FAIL  {e}\n\n1 FAILED"); sys.exit(1)
