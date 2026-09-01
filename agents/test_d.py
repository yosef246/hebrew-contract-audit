# test_d.py — Stage D: analyze → correct/validate loop → advance, על סעיף פיקדון.
from state import GraphState, Clause
import graph

def apply(state, patch):
    for k, v in patch.items():
        setattr(state, k, v)

CLAUSE_TEXT = "השוכר יפקיד סכום של 20,000 ₪ שיישאר בידי המשכיר ולא יוחזר בתום החוזה"

def main():
    clause = Clause(id="0:d", section_number=None, text=CLAUSE_TEXT, index=0)
    state = GraphState(contractId="d", originalContract=CLAUSE_TEXT,
                       clauses=[clause], status="running")

    # analyze → routing מחזיר "correct" (סעיף בעייתי)
    apply(state, graph.analyze_node(state))
    node = graph.route_after_analyze(state)
    print(f"route_after_analyze: {node}")

    # לולאת correct/validate לפי ה-routing האמיתי, עד advance
    while node in ("correct", "validate"):
        if node == "correct":
            apply(state, graph.correct_node(state))
            node = "validate"                         # edge סטטי correct→validate
        else:
            apply(state, graph.validate_node(state))
            node = graph.route_after_validate(state)
            print(f"route_after_validate: {node}  (attempts={state.attempts[clause.id]})")
    apply(state, graph.advance_hub(state))

    cid = clause.id
    corr = state.proposedCorrections[cid]
    print("\n=== Correction (Corrector) ===")
    print("corrected_text:", corr.corrected_text)
    print("changes       :", corr.changes)
    print("legal_basis   :", corr.legal_basis)

    print("\n=== Validation history (Validator) ===")
    for i, v in enumerate(state.validationResults[cid], 1):
        print(f"  ניסיון {i}: valid={v.valid} score={v.score} issues={v.issues}")
        print(f"    retrieved_sources (של Validator, עצמאית): "
              f"{[s.label for s in v.retrieved_sources]}")

    print("\n=== Outcome ===")
    print("attempts         :", state.attempts[cid])
    print("final clauseStatus:", state.clauseStatus[cid])

if __name__ == "__main__":
    main()
