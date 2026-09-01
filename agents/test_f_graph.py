# test_f_graph.py — Stage F: build_graph רץ end-to-end דרך LangGraph + persistence + resume.
# משתמש ב-SqliteSaver (durable file) — אותה סמנטיקה כמו PostgresSaver, בלי סוד. סעיף תקין אחד
# כדי למזער קריאות LLM (analyze + report). flush=True כדי לראות התקדמות בזמן אמת.
import os
from langgraph.checkpoint.sqlite import SqliteSaver
from state import GraphState, Clause
import graph

def log(*a): print(*a, flush=True)

DB = "checkpoints.sqlite"
if os.path.exists(DB):
    os.remove(DB)                       # התחלה נקייה

CLAUSE = Clause(id="0", section_number="1",
                text="השוכר ישלם דמי שכירות בסך 5,000 ₪ ב-1 לכל חודש", index=0)

def fresh_state(cid):
    return GraphState(contractId=cid, originalContract=CLAUSE.text,
                      clauses=[CLAUSE], status="running")

# ── חלק 1: ריצה מלאה עד END, עם checkpoints ל-sqlite file ──────────────────────
log(">> PART 1: full run to completion (thread=f-done)")
CFG1 = {"configurable": {"thread_id": "f-done"}}
with SqliteSaver.from_conn_string(DB) as saver:
    app = graph.build_graph(saver)
    final = app.invoke(fresh_state("f-done"), CFG1)
    log("   final status      :", final["status"])
    log("   final clauseStatus:", final["clauseStatus"])
    log("   report chars      :", len(final["report_markdown"]))

# ── חלק 2: instance חדש לגמרי על אותו file — מוכיח persistence (בלי ריצה מחדש) ──
log("\n>> PART 2: NEW saver+graph on same file → read persisted state (no re-run)")
with SqliteSaver.from_conn_string(DB) as saver2:
    app2 = graph.build_graph(saver2)
    snap = app2.get_state(CFG1)
    log("   persisted status         :", snap.values["status"])
    log("   persisted currentClauseIdx:", snap.values["currentClauseIndex"])
    log("   persisted clauseStatus   :", snap.values["clauseStatus"])
    log("   next (empty=()=finished) :", snap.next)

# ── חלק 3: interrupt לפני report → pause → instance חדש resume → complete ───────
log("\n>> PART 3: interrupt before report → pause → resume in a FRESH instance (thread=f-resume)")
CFG2 = {"configurable": {"thread_id": "f-resume"}}
with SqliteSaver.from_conn_string(DB) as s:
    appi = graph.build_graph(s, interrupt_before=["report"])
    appi.invoke(fresh_state("f-resume"), CFG2)
    snap_p = appi.get_state(CFG2)
    log("   PAUSED next        :", snap_p.next, "(should be ('report',))")
    log("   PAUSED status      :", snap_p.values["status"], "| report empty?",
        snap_p.values["report_markdown"] == "")

with SqliteSaver.from_conn_string(DB) as s2:     # תהליך/instance 'חדש'
    appr = graph.build_graph(s2)                  # בלי interrupt
    appr.invoke(None, CFG2)                       # resume מהצ'קפוינט
    snap_r = appr.get_state(CFG2)
    log("   RESUMED next       :", snap_r.next, "(empty=finished)")
    log("   RESUMED status     :", snap_r.values["status"], "| report chars:",
        len(snap_r.values["report_markdown"]))

log("\n[OK] build_graph runs end-to-end via LangGraph with durable persistence + resume.")
