# graph.py — LangGraph orchestration. Stage C: analyze_node + advance_hub + route_after_advance.
# correct/validate (D), coherence/report + build_graph (E) follow.
import functools, json, time, urllib.error
from langgraph.graph import StateGraph, START, END
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import ValidationError
from rag_client import Source, _retrieve_law_http   # ה-black box ל-RAG (נבדק בשלב B)
from state import (GraphState, Clause, AnalyzerVerdict, AnalysisResult,
                   Correction, ValidatorVerdict, Validation,
                   CoherenceResult, ReportOutput, NodeTelemetry)
from prompts import (ANALYZER_SYSTEM, CORRECTOR_SYSTEM, VALIDATOR_SYSTEM,
                     COHERENCE_SYSTEM, REPORT_SYSTEM)

CLAUDE_MODEL = "claude-sonnet-5"          # חייב להתאים ל-CLAUDE_MODEL ב-TS
LAW_K = 4
MAX_RETRIES = 3                           # correct↔validate פר-סעיף (שלב D)
MAX_RETRIEVAL_TRIES = 3                    # 3 כשלי שליפה → skip clause

def _model() -> ChatAnthropic:
    # thinking מושבת — מיישר קו עם issue-detection.ts (latency / 60s cap).
    # temperature הוסר: claude-sonnet-5 דוחה אותו (400 "deprecated for this model") — לא רק מתעלם.
    # thinking מועבר כ-param מפורש (langchain-anthropic 1.7 מזהיר על העברתו דרך model_kwargs).
    return ChatAnthropic(model=CLAUDE_MODEL, thinking={"type": "disabled"})

def _structured(schema, messages, retries: int = 2):
    """with_structured_output עמיד: Sonnet-5 משמיט לעתים שדה חובה בפלט המובנה (למשל is_problematic)
    → ValidationError. retry מתקן את ההשמטה החולפת. אחרי שכל הניסיונות נכשלו — מרים את השגיאה."""
    llm = _model().with_structured_output(schema)
    last = None
    for _ in range(retries + 1):
        try:
            return llm.invoke(messages)
        except ValidationError as e:
            last = e
    raise last

def _retrieve_with_retries(query: str, k: int = LAW_K):
    for attempt in range(MAX_RETRIEVAL_TRIES):
        try:
            return _retrieve_law_http(query, k), 0
        except urllib.error.HTTPError as e:          # חייב לפני URLError (תת-מחלקה)
            if e.code >= 500:
                time.sleep(0.5 * (attempt + 1)); continue   # 5xx → transient
            raise                                            # 4xx → באג auth/config
        except (urllib.error.URLError, TimeoutError):
            time.sleep(0.5 * (attempt + 1)); continue        # רשת/timeout → transient
    return None, MAX_RETRIEVAL_TRIES

def node(name: str):
    def deco(fn):
        @functools.wraps(fn)
        def wrapped(state: GraphState) -> dict:
            t0 = time.monotonic()
            patch = fn(state) or {}
            rec = NodeTelemetry(node=name, latency_ms=int((time.monotonic() - t0) * 1000),
                                tokens_used=0, input="", output="")   # TODO tokens (שלב F)
            patch["telemetry"] = state.telemetry + [rec]
            return patch
        return wrapped
    return deco

def _current(state: GraphState) -> Clause:
    return state.clauses[state.currentClauseIndex]

def _fmt_sources(sources: list[Source]) -> str:
    return "\n".join(f"[{s.marker}] {s.label}: {s.text}" for s in sources) or "(אין מקורות)"

@node("analyze")
def analyze_node(state: GraphState) -> dict:
    clause = _current(state)
    sources, _fails = _retrieve_with_retries(clause.text)        # retrieve_law (grounding דטרמיניסטי)
    if sources is None:                                          # 3 כשלי שליפה → דלג
        state.clauseStatus[clause.id] = "retrieval_failed"
        state.analysisResults[clause.id] = AnalysisResult(
            analysis="שליפת מקורות נכשלה", is_problematic=False, severity=1,
            reason="retrieval_failed", used_markers=[], sources=[],
            missing_info=["לא נשלפו מקורות חוק"])
        return {"analysisResults": state.analysisResults, "clauseStatus": state.clauseStatus}
    user = (f'סעיף {clause.section_number or "ללא מספר"}:\n"""\n{clause.text}\n"""\n\n'
            f"מקורות חוק ממוספרים:\n{_fmt_sources(sources)}")
    verdict: AnalyzerVerdict = _structured(
        AnalyzerVerdict, [SystemMessage(content=ANALYZER_SYSTEM), HumanMessage(content=user)])
    result = AnalysisResult(**verdict.model_dump(), sources=sources)   # מצמידים את המקורות האמיתיים
    state.analysisResults[clause.id] = result
    # C.5: analyze קובע את הסטטוס לסעיפים לא-בעייתיים. חריגה-מנורמות-ללא-מקור → unverified_concern
    # (לא נקבר כ-ok). סעיף בעייתי → הסטטוס נקבע בהמשך (advance / לולאת correct-validate בשלב D).
    if not result.is_problematic:
        if result.norm_deviation_without_source and not result.used_markers:
            state.clauseStatus[clause.id] = "unverified_concern"
        else:
            state.clauseStatus[clause.id] = "ok"
    return {"analysisResults": state.analysisResults, "clauseStatus": state.clauseStatus}

def route_after_analyze(state: GraphState) -> str:
    a = state.analysisResults[_current(state).id]
    if a.is_problematic:
        return "correct"                       # יש מקור תומך → לתיקון
    # ok / unverified_concern / retrieval_failed → אין מה לתקן בלי בסיס משפטי → advance
    return "advance"

@node("advance")
def advance_hub(state: GraphState) -> dict:
    clause = _current(state)
    vlist = state.validationResults.get(clause.id, [])
    st = state.clauseStatus.get(clause.id)
    # analyze כבר קבע ok / unverified_concern / retrieval_failed — לא לדרוס. כאן נסגר רק המסלול הבעייתי.
    if st not in ("ok", "unverified_concern", "retrieval_failed"):
        if vlist and vlist[-1].valid:                               # שלב D: תיקון שאושר
            state.clauseStatus[clause.id] = "corrected"
        elif state.attempts.get(clause.id, 0) >= MAX_RETRIES:       # שלב D: מוצו retries
            state.clauseStatus[clause.id] = "requires_human_review"
        else:
            state.clauseStatus[clause.id] = "problematic"          # placeholder עד שלולאת correct/validate תחובר (שלב D)
    return {"clauseStatus": state.clauseStatus,
            "currentClauseIndex": state.currentClauseIndex + 1}

def route_after_advance(state: GraphState) -> str:
    return "analyze" if state.currentClauseIndex < len(state.clauses) else "coherence"

@node("correct")
def correct_node(state: GraphState) -> dict:
    clause = _current(state)
    analysis = state.analysisResults[clause.id]
    state.attempts[clause.id] = state.attempts.get(clause.id, 0) + 1     # נמנה ב-correct, לפני validate
    user = (f"סעיף מקורי:\n{clause.text}\n\nמקורות חוק (השתמש רק בהם):\n"
            f"{_fmt_sources(analysis.sources)}\n\nהבעיה שזוהתה: {analysis.reason}")
    out: Correction = _structured(
        Correction, [SystemMessage(content=CORRECTOR_SYSTEM), HumanMessage(content=user)])
    state.proposedCorrections[clause.id] = out
    return {"proposedCorrections": state.proposedCorrections, "attempts": state.attempts}

@node("validate")
def validate_node(state: GraphState) -> dict:
    clause = _current(state)
    correction = state.proposedCorrections[clause.id]
    others = [c.text for c in state.clauses if c.id != clause.id][:8]     # הקשר; TODO: קיצוץ לפי טוקנים
    # שליפה עצמאית לפי הסעיף המקורי — לא רואה את sources של Corrector ולא את התיקון (אנטי-הטיה)
    v_sources, _fails = _retrieve_with_retries(clause.text)
    v_sources = v_sources or []
    user = (f"סעיף מקורי:\n{clause.text}\n\nהתיקון המוצע:\n{correction.corrected_text}\n\n"
            f"מקורות חוק (שלפת עצמאית):\n{_fmt_sources(v_sources)}\n\n"
            f"סעיפים אחרים בחוזה (הקשר):\n" + ("\n---\n".join(others) or "(אין)"))
    verdict: ValidatorVerdict = _structured(
        ValidatorVerdict, [SystemMessage(content=VALIDATOR_SYSTEM), HumanMessage(content=user)])
    result = Validation(**verdict.model_dump(), retrieved_sources=v_sources)   # מצמידים audit trail
    state.validationResults.setdefault(clause.id, []).append(result)           # היסטוריית ניסיונות!
    return {"validationResults": state.validationResults}

# correct → validate הוא edge סטטי (add_edge) — אין תנאי, אין צורך ב-router.
def route_after_validate(state: GraphState) -> str:
    clause = _current(state)
    last = state.validationResults[clause.id][-1]
    if last.valid:
        return "advance"                                       # תוקן בהצלחה
    if state.attempts.get(clause.id, 0) < MAX_RETRIES:
        return "correct"                                       # retry
    return "advance"                                           # מוצו retries → advance יסמן requires_human_review

@node("coherence")
def coherence_node(state: GraphState) -> dict:
    corrected = [(c, state.proposedCorrections[c.id]) for c in state.clauses
                 if state.clauseStatus.get(c.id) == "corrected"]
    if len(corrected) < 2:      # פחות משניים — אין מה לסתור; חוסך קריאת LLM מיותרת
        state.coherenceIssues = CoherenceResult(contradictions=[], severity=1)
        return {"coherenceIssues": state.coherenceIssues}
    listing = "\n\n".join(
        f"סעיף {c.section_number or c.id}: {corr.corrected_text}" for c, corr in corrected)
    out: CoherenceResult = _structured(
        CoherenceResult, [SystemMessage(content=COHERENCE_SYSTEM), HumanMessage(content=listing)])
    state.coherenceIssues = out
    return {"coherenceIssues": state.coherenceIssues}

def _report_payload(state: GraphState) -> dict:
    """דוחס את ה-state לשדות שהדוח צריך — כולל resolve של used_markers → תוויות מקור לציטוט."""
    clauses = []
    for c in state.clauses:
        a = state.analysisResults.get(c.id)
        corr = state.proposedCorrections.get(c.id)
        vlist = state.validationResults.get(c.id, [])
        v = vlist[-1] if vlist else None
        cited = []
        if a:
            by_marker = {s.marker: s.label for s in a.sources}
            cited = [by_marker.get(m, m) for m in a.used_markers]   # מותאם מהמקורות שנשלפו בפועל
        clauses.append({
            "section": c.section_number or c.id,
            "text": c.text,
            "status": state.clauseStatus.get(c.id),
            "severity": a.severity if a else None,
            "reason": a.reason if a else None,
            "missing_info": a.missing_info if a else [],
            "legal_sources": cited,
            "corrected_text": corr.corrected_text if corr else None,
            "legal_basis": corr.legal_basis if corr else None,
            "validation": {"valid": v.valid, "score": v.score} if v else None,
        })
    coh = state.coherenceIssues.model_dump() if state.coherenceIssues else None
    return {"clauses": clauses, "coherence": coh}

@node("report")
def report_node(state: GraphState) -> dict:
    payload = _report_payload(state)
    out: ReportOutput = _structured(
        ReportOutput, [SystemMessage(content=REPORT_SYSTEM),
                       HumanMessage(content=json.dumps(payload, ensure_ascii=False))])
    any_hr = any(s == "requires_human_review" for s in state.clauseStatus.values())
    return {"report_markdown": out.markdown,
            "status": "requires_human_review" if any_hr else "done"}

def build_graph(checkpointer, interrupt_before=None):
    """מחווט את ה-StateGraph המלא. checkpointer מוזרק (backend-agnostic): SqliteSaver לפיתוח,
    PostgresSaver בפרודקשן — החלפת שורה אחת, אותה סמנטיקת המשך-מהיכן-שנעצר."""
    g = StateGraph(GraphState)
    for name, fn in [("analyze", analyze_node), ("correct", correct_node),
                     ("validate", validate_node), ("advance", advance_hub),
                     ("coherence", coherence_node), ("report", report_node)]:
        g.add_node(name, fn)
    g.add_edge(START, "analyze")
    g.add_conditional_edges("analyze", route_after_analyze,
                            {"correct": "correct", "advance": "advance"})
    g.add_edge("correct", "validate")                              # edge סטטי
    g.add_conditional_edges("validate", route_after_validate,
                            {"correct": "correct", "advance": "advance"})
    g.add_conditional_edges("advance", route_after_advance,
                            {"analyze": "analyze", "coherence": "coherence"})
    g.add_edge("coherence", "report")
    g.add_edge("report", END)
    return g.compile(checkpointer=checkpointer, interrupt_before=interrupt_before or [])

# TODO שלב F (המשך): telemetry tokens (usage_metadata), extract_clauses מלא (פורט מ-contract-chunker.ts)
