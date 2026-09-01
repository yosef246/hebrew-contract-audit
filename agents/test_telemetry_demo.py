# test_telemetry_demo.py — מייצר דוגמת data/telemetry.jsonl: extract על החוזה האמיתי + analyze
# על 2 הסעיפים הראשונים (2 קריאות LLM → 2 שורות telemetry). extract עצמו הוא deterministic (בלי LLM).
import os
from extract import extract_clauses
from state import GraphState
import graph

if os.path.exists(graph.TELEMETRY_PATH):
    os.remove(graph.TELEMETRY_PATH)          # התחלה נקייה לדוגמה

raw = open(os.path.join(os.path.dirname(__file__), "..", "fixtures", "rental-01.txt"),
           encoding="utf-8").read()
clauses, t = extract_clauses(raw)
print("extract telemetry:", t.model_dump())

state = GraphState(contractId="rental-01", originalContract=raw, clauses=clauses, status="running")
for i in range(2):                            # analyze על 2 הסעיפים הראשונים
    state.currentClauseIndex = i
    for k, v in graph.analyze_node(state).items():
        setattr(state, k, v)
    print(f"  analyzed clause {clauses[i].id} → {state.clauseStatus.get(clauses[i].id)}")

print("\n--- data/telemetry.jsonl ---")
print(open(graph.TELEMETRY_PATH, encoding="utf-8").read().rstrip())
