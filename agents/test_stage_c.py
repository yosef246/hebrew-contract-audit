# test_stage_c.py — Stage C end-to-end: סעיף בעייתי אחד דרך analyze → advance.
from state import GraphState, Clause
import graph

def apply(state: GraphState, patch: dict) -> None:
    """מדמה את מיזוג ה-dict-patch של LangGraph לתוך ה-state."""
    for k, v in patch.items():
        setattr(state, k, v)

CLAUSE_TEXT = "המשכיר רשאי להיכנס לנכס בכל עת ללא הודעה מראש"

def main():
    clause = Clause(id="0:43", section_number="43", text=CLAUSE_TEXT, index=0)
    state = GraphState(contractId="smoke-C", originalContract=CLAUSE_TEXT,
                       clauses=[clause], status="running")

    apply(state, graph.analyze_node(state))
    ar = state.analysisResults[clause.id]
    print("=== AnalysisResult ===")
    print("is_problematic:", ar.is_problematic)
    print("severity      :", ar.severity)
    print("analysis      :", ar.analysis)
    print("reason        :", ar.reason)
    print("used_markers  :", ar.used_markers)
    print("missing_info  :", ar.missing_info)
    print("sources (attached, real):")
    for s in ar.sources:
        print(f"   [{s.marker}] {s.label}   sim={s.similarity:.3f}")

    apply(state, graph.advance_hub(state))
    print("\n=== after advance_hub ===")
    print("currentClauseIndex :", state.currentClauseIndex)
    print("clauseStatus       :", state.clauseStatus)
    print("route_after_advance:", graph.route_after_advance(state))
    print("telemetry          :", [(t.node, f"{t.latency_ms}ms") for t in state.telemetry])

if __name__ == "__main__":
    main()
