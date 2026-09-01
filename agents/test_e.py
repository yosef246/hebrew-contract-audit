# test_e.py — Stage E: חוזה רב-סעיפי דרך כל הצינור → coherence → report.
from state import GraphState, Clause
import graph

def apply(state, patch):
    for k, v in patch.items():
        setattr(state, k, v)

CLAUSES = [
    "השוכר יפקיד סכום של 20,000 ₪ שיישאר בידי המשכיר ולא יוחזר בתום החוזה",          # → corrected
    "המשכיר רשאי לחלט את הפיקדון לפי שיקול דעתו הבלעדי ובכל עת וללא הודעה",           # → corrected
    "המשכיר רשאי להיכנס לנכס בכל עת ללא הודעה מראש",                                  # → unverified_concern
    "השוכר ישלם דמי שכירות בסך 5,000 ₪ ב-1 לכל חודש",                                # → ok
]

def run_clause(state):
    """analyze → correct/validate loop → advance, על הסעיף הנוכחי."""
    apply(state, graph.analyze_node(state))
    node = graph.route_after_analyze(state)
    while node in ("correct", "validate"):
        if node == "correct":
            apply(state, graph.correct_node(state)); node = "validate"   # edge סטטי
        else:
            apply(state, graph.validate_node(state)); node = graph.route_after_validate(state)
    apply(state, graph.advance_hub(state))

def main():
    clauses = [Clause(id=f"{i}", section_number=str(i + 1), text=t, index=i)
               for i, t in enumerate(CLAUSES)]
    state = GraphState(contractId="e", originalContract="\n".join(CLAUSES),
                       clauses=clauses, status="running")

    while state.currentClauseIndex < len(state.clauses):
        run_clause(state)

    apply(state, graph.coherence_node(state))     # פעם אחת, על כל המתוקנים
    apply(state, graph.report_node(state))

    print("=== clauseStatus ===")
    for c in clauses:
        print(f"  סעיף {c.section_number}: {state.clauseStatus[c.id]}")
    print("\n=== coherenceIssues ===")
    print(" contradictions:", state.coherenceIssues.contradictions)
    print(" severity      :", state.coherenceIssues.severity)
    print("\n=== status ===", state.status)
    print("\n=== REPORT (Markdown) ===\n")
    print(state.report_markdown)

if __name__ == "__main__":
    main()
