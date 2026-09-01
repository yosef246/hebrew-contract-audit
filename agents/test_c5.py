# test_c5.py — מאמת את הסטטוס השלישי (unverified_concern) על 3 סעיפים.
from state import GraphState, Clause
import graph

CASES = [
    ("entry",   "0:e", "המשכיר רשאי להיכנס לנכס בכל עת ללא הודעה מראש"),
    ("deposit", "0:d", "השוכר יפקיד סכום של 20,000 ₪ שיישאר בידי המשכיר ולא יוחזר בתום החוזה"),
    ("clean",   "0:c", "השוכר ישלם דמי שכירות בסך 5,000 ₪ ב-1 לכל חודש"),
]

def run_one(name, cid, text):
    clause = Clause(id=cid, section_number=None, text=text, index=0)
    state = GraphState(contractId=f"c5-{name}", originalContract=text,
                       clauses=[clause], status="running")
    for k, v in graph.analyze_node(state).items():
        setattr(state, k, v)
    ar = state.analysisResults[cid]
    route = graph.route_after_analyze(state)
    for k, v in graph.advance_hub(state).items():
        setattr(state, k, v)
    print(f"\n=== [{name}] {text} ===")
    print(f"  is_problematic               : {ar.is_problematic}")
    print(f"  used_markers                 : {ar.used_markers}")
    print(f"  norm_deviation_without_source: {ar.norm_deviation_without_source}")
    print(f"  missing_info (count)         : {len(ar.missing_info)}")
    print(f"  route_after_analyze          : {route}")
    print(f"  -> final clauseStatus        : {state.clauseStatus[cid]}")

if __name__ == "__main__":
    for c in CASES:
        run_one(*c)
    print("\nEXPECTED:  entry -> unverified_concern  |  deposit -> problematic  |  clean -> ok")
