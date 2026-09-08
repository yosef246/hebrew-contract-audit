# -*- coding: utf-8 -*-
"""diag_placeholder — מדידת בסיס: איך ה-analyzer מתייחס לשדה ריק ('____')?

NEVER RUN AGAINST THE LIVE API. Written before credentials existed, deliberately: a
before/after probe authored after the answer is known is worthless. Its full path IS
exercised offline by tests/test_diag_placeholder_offline.py, which stubs RAG and the LLM —
that is what the numbers below have been checked against, never a real analyzer verdict.
__main__-gated; never imported by the graph.

מריץ את analyze_node על שמונת הסעיפים נושאי-ה-'____' בלבד (לא eval מלא).
שני כיווני-כשל שמחפשים:
  A. סימון הסעיף כפגום/חריג *בגלל* שהשדה ריק  → מנפח flag_rate
  B. התייחסות ל-'₪_______' כאילו יש בו סכום    → ממצא מומצא

הרצה (מכל תיקייה):
  ANTHROPIC_API_KEY=... RAG_INTERNAL_TOKEN=... [RAG_URL=...] python agents/diag_placeholder.py
"""
import io, os, re, sys, json

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

# שמונת יחידות-הניתוח שנושאות רצף '____' (ראה CLAUDE.md, "Empty form fields are NULL")
TARGETS = {
    "rental-01": ["3.1", "4.1", "4.2-א", "13.1"],
    "rental-02": ["2", "6.1", "12.2", "16.1"],
}

def main() -> int:
    for var in ("ANTHROPIC_API_KEY", "RAG_INTERNAL_TOKEN"):
        if not os.environ.get(var):
            print(f"MISSING ENV: {var}")
            return 2
    # חייבים להישאר בתוך main(): rag_client קורא os.environ["RAG_INTERNAL_TOKEN"] ברמת המודול
    # (fail-fast), כך שייבוא graph בלי טוקן זורק KeyError. שער ה-env שלמעלה חייב לרוץ קודם.
    # אל תיתן ל-isort/E402 להרים אותם למעלה — זה שובר את השער בשקט.
    from extract import extract_clauses
    from state import GraphState
    from graph import analyze_node

    rows = []
    for fixture, ids in TARGETS.items():
        path = os.path.join(ROOT, "fixtures", f"{fixture}.txt")
        clauses, _ = extract_clauses(io.open(path, encoding="utf-8").read())
        for sid in ids:
            c = next((x for x in clauses if x.section_number == sid and x.analyze), None)
            if c is None:
                print(f"SKIP {fixture} {sid}: not an analysis unit")
                continue
            st = GraphState(contractId=f"diag-{fixture}", originalContract="",
                            clauses=[c], currentClauseIndex=0)
            analyze_node(st)
            res = st.analysisResults.get(c.id)
            rows.append({
                "fixture": fixture, "clause": sid,
                "status": st.clauseStatus.get(c.id),
                "is_problematic": res.is_problematic if res else None,
                "norm_dev_no_source": res.norm_deviation_without_source if res else None,
                "used_markers": res.used_markers if res else None,
                "severity": res.severity if res else None,
                "missing_info": res.missing_info if res else None,
                "analysis": (res.analysis if res else "")[:400],
                "placeholder_runs": len(re.findall(r"_{3,}", c.text)),
            })
            print(json.dumps(rows[-1], ensure_ascii=False, indent=2))

    print("\n=== SUMMARY ===")
    for r in rows:
        flagged = r["status"] == "unverified_concern" or r["is_problematic"]
        print(f'{r["fixture"]} {r["clause"]:<7} status={str(r["status"]):<20} '
              f'flagged={"YES" if flagged else "no":<4} markers={r["used_markers"]}')
    print("\nכיוון A: האם analysis/missing_info נוקבים בחוסר עצמו כעילה לסימון?")
    print("כיוון B: האם analysis מצטט סכום/תאריך/שם שאינו קיים בטקסט?")
    return 0

if __name__ == "__main__":
    sys.exit(main())
