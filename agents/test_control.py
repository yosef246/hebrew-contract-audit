# test_control.py — positive-path control: סעיף פיקדון קלאסי (§25י נשלף היטב).
from state import GraphState, Clause
import graph

CLAUSE_TEXT = "השוכר יפקיד סכום של 20,000 ₪ שיישאר בידי המשכיר ולא יוחזר בתום החוזה"

def main():
    clause = Clause(id="0:dep", section_number=None, text=CLAUSE_TEXT, index=0)
    state = GraphState(contractId="ctrl", originalContract=CLAUSE_TEXT,
                       clauses=[clause], status="running")
    for k, v in graph.analyze_node(state).items():
        setattr(state, k, v)
    ar = state.analysisResults[clause.id]
    print("=== AnalysisResult (deposit control) ===")
    print("is_problematic:", ar.is_problematic)
    print("severity      :", ar.severity)
    print("analysis      :", ar.analysis)
    print("reason        :", ar.reason)
    print("used_markers  :", ar.used_markers)
    print("missing_info  :", ar.missing_info)
    print("sources (attached, real):")
    for s in ar.sources:
        print(f"   [{s.marker}] {s.label}   sim={s.similarity:.3f}")

if __name__ == "__main__":
    main()
