# state.py — shared domain models + LangGraph state. pydantic only (no heavy deps).
from typing import Literal, Optional
from pydantic import BaseModel, Field

class Source(BaseModel):            # מקור RAG יחיד — WE ממספרים marker, המודל מצטט רק אותו
    marker: str
    label: str
    section_number: str
    text: str
    similarity: float

class Clause(BaseModel):            # תוצר ClauseExtractor (קוד רגיל, מחוץ לגרף)
    id: str
    section_number: Optional[str]
    text: str
    index: int
    # granularity: יחידת הניתוח היא תת-סעיף. כותרת ראשית = קונטקסט בלבד (analyze=False),
    # אלא אם אין תחתיה תת-סעיפים (אז היא עצמאית). ה-parent_heading מוזרק ל-analyze כ-metadata.
    kind: Literal["preamble", "main_heading", "sub_clause"] = "sub_clause"
    analyze: bool = True
    parent_heading: Optional[str] = None

# מה שה-LLM ממלא בניתוח. הוא מחזיר MARKER references (used_markers), לעולם לא Source מלאים —
# אנחנו מצמידים את המקורות האמיתיים. מראה את דפוס האנטי-הזיה של issue-detection.ts (law_marker
# נפתר בקוד) כך שהמודל לא יכול להמציא ציטוט/סעיף שלא קיבל.
class AnalyzerVerdict(BaseModel):
    analysis: str
    is_problematic: bool
    severity: int = Field(ge=1, le=5)
    reason: str
    used_markers: list[str] = Field(default_factory=list)   # למשל ["1","2"] — אינדקסים לתוך המקורות שסופקו
    # המודל מדליק כשזיהה חריגה מנורמות סטנדרטיות אך אין מקור ממוספר תומך. הקוד מסיק מכך
    # 'unverified_concern' (used_markers==[] AND norm_deviation_without_source). מחליף פרסינג-פרוזה שביר.
    norm_deviation_without_source: bool = False
    missing_info: list[str] = Field(default_factory=list)

class AnalysisResult(AnalyzerVerdict):
    sources: list[Source] = Field(default_factory=list)     # המקורות האמיתיים שנשלפו, מוצמדים בקוד

class Correction(BaseModel):
    corrected_text: str
    changes: list[str]
    legal_basis: str

class ValidatorVerdict(BaseModel):      # מה שה-LLM ממלא — בלי retrieved_sources (אותו דפוס אנטי-הזיה כמו AnalyzerVerdict)
    valid: bool                         # True רק אם score>=85 ∧ issues=[] ∧ legal_basis תקף ∧ ציטוט מ-RAG
    score: int = Field(ge=0, le=100)
    issues: list[str]
    reason: str

class Validation(ValidatorVerdict):
    retrieved_sources: list[Source] = Field(default_factory=list)   # audit trail — מה ש-Validator שלף עצמאית, מוצמד בקוד

class CoherenceResult(BaseModel):
    contradictions: list[str]
    severity: int = Field(ge=1, le=5)

class ReportOutput(BaseModel):
    markdown: str

class NodeTelemetry(BaseModel):
    node: str
    latency_ms: int
    tokens_used: int
    input: str
    output: str

ClauseStatus = Literal["ok", "unverified_concern", "problematic", "corrected", "requires_human_review", "retrieval_failed", "context"]

class GraphState(BaseModel):
    contractId: str
    originalContract: str
    clauses: list[Clause] = Field(default_factory=list)
    currentClauseIndex: int = 0
    analysisResults: dict[str, AnalysisResult] = Field(default_factory=dict)
    proposedCorrections: dict[str, Correction] = Field(default_factory=dict)
    validationResults: dict[str, list[Validation]] = Field(default_factory=dict)   # היסטוריית ניסיונות פר-סעיף
    clauseStatus: dict[str, ClauseStatus] = Field(default_factory=dict)
    coherenceIssues: Optional[CoherenceResult] = None
    attempts: dict[str, int] = Field(default_factory=dict)
    report_markdown: str = ""
    status: Literal["pending", "running", "requires_human_review", "done"] = "pending"
    telemetry: list[NodeTelemetry] = Field(default_factory=list)
