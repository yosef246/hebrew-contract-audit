# extract.py — ClauseExtractor דטרמיניסטי (קוד רגיל, רץ לפני הגרף).
# פורט של contract-chunker.ts + שני שינויים מכוונים:
#   1. trigger מפורש ל-fallback (MIN_SECTIONS / MAX_AVG_CHARS / MAX_SINGLE_CHARS).
#   2. normalize_section_numbers — מתקן היפוך מספרי-סעיף ב-RTL (unpdf שם אותם בקצה השורה)
#      לפני ה-split. מבוסס על חקירת rental-01 (תבנית LeaseLink): כותרת ראשית יוצאת כ-
#      ". <טקסט><ספרה>" (נקודה יתומה בתחילה, ספרה חשופה בסוף); תת-סעיף יוצא כ-"<טקסט> N.N".
import re
import statistics
from pydantic import BaseModel
from state import Clause

# section id היררכי: "1", "1.1", "6.1.2", "1א" (וגם דיסמביגואציה כמו "4.2-א" עוברת ב-split הבא)
SECTION_RE = re.compile(r'^\s*(\d+(?:\.\d+)*[א-ת]?)\.?\s+')
WINDOW_SIZE = 500
WINDOW_OVERLAP = 50

# --- ספי החלטה (fallback / windowing) — מרוכזים כאן, מתועדים ב-README ---
MIN_SECTIONS     = 3      # < 3 סעיפים ממוספרים → split כנראה נכשל → fallback
MAX_AVG_CHARS    = 2000   # סעיף ממוצע ארוך מזה → headers לא זוהו → fallback (עברית משפטית ארוכה)
MAX_SINGLE_CHARS = 4000   # סעיף בודד ענק מזה → split נכשל עליו → מחלונים אותו (שומר מספר סעיף)

class ExtractTelemetry(BaseModel):
    path: str                   # "regex" | "mixed" | "fallback" | "empty"
    n_clauses: int
    avg_len: float
    regex_sections: int         # כמה כותרות ממוספרות ה-regex תפס (אחרי normalize, לפני fallback)
    fallback_reason: str | None = None

# --- normalize: מזיז מספר-סעיף מקצה השורה לתחילתה (תיקון היפוך RTL) ---
_LEAD_MAIN = re.compile(r'^\.\s+(.*?)\s*(\d+)\s*$')             # A' (LeaseLink בפועל): ". <טקסט><ספרה>"
_TAIL_SUB  = re.compile(r'^(.*?\S)\s+(\d+\.\d+(?:\.\d+)?)\s*$') # B: "<טקסט> N.N / N.N.N"
_TAIL_MAIN = re.compile(r'^(.*?\S)\s+(\d+)\.\s*$')              # C: "<טקסט> N."
_TAIL_DOTN = re.compile(r'^(.*?\S)\s+\.(\d+)\s*$')             # A (המקורי מהספק): "<טקסט> .N"
_ONLY_SYMS = re.compile(r'^[\d.\-/()\s]*$')

def _has_sep(tok: str) -> bool:
    return '/' in tok or '-' in tok      # skip 1: מזהה תקנתי (38/1, 1968-), לא section

def normalize_section_numbers(text: str) -> str:
    """מזיז מספרי-סעיף שהיפוך-RTL שם בקצה השורה חזרה לתחילתה. skip: מזהים עם /,- ;
    שורות קצרות של סמלים בלבד ; ספרות באמצע שורה (מתאימים רק על גבול-שורה $)."""
    out: list[str] = []
    for line in text.split('\n'):
        s = line.rstrip()
        stripped = s.strip()
        if len(stripped) < 10 and _ONLY_SYMS.match(stripped):      # skip 3: מספר עמוד / כותרת קצרה
            out.append(line); continue
        m = _LEAD_MAIN.match(s)
        if m and not _has_sep(m.group(2)):
            out.append(f"{m.group(2)}. {m.group(1).strip()}"); continue
        m = _TAIL_SUB.match(s)
        if m and not _has_sep(m.group(2)):
            out.append(f"{m.group(2)} {m.group(1).strip()}"); continue
        m = _TAIL_MAIN.match(s)
        if m and not _has_sep(m.group(2)):
            out.append(f"{m.group(2)}. {m.group(1).strip()}"); continue
        m = _TAIL_DOTN.match(s)
        if m and not _has_sep(m.group(2)):
            out.append(f"{m.group(2)}. {m.group(1).strip()}"); continue
        out.append(line)
    return '\n'.join(out)

def _normalize(raw: str) -> str:
    cleaned = re.sub(r'\r\n?', '\n', raw)
    cleaned = '\n'.join(line.rstrip(' \t') for line in cleaned.split('\n')).strip()
    # מציב מרקר ממוספר mid-line ("7. ") בתחילת שורה (למקרה שה-extractor השטיח שורות).
    return re.sub(r'[ \t]+(\d{1,2}[א-ת]?\.[ \t])', r'\n\1', cleaned)

def _window(text: str, size: int = WINDOW_SIZE, overlap: int = WINDOW_OVERLAP) -> list[str]:
    clean = text.strip()
    if len(clean) <= size:
        return [clean] if clean else []
    out, step, start = [], size - overlap, 0
    while start < len(clean):
        out.append(clean[start:start + size].strip())
        if start + size >= len(clean):
            break
        start += step
    return [w for w in out if w]

def _split_sections(text: str) -> list[tuple[str | None, str]]:
    sections: list[tuple[str | None, str]] = []
    cur_num: str | None = None
    cur_txt = ""
    def flush():
        if cur_txt.strip():
            sections.append((cur_num, cur_txt.strip()))
    for line in text.split('\n'):
        m = SECTION_RE.match(line)
        if m:
            flush()
            cur_num, cur_txt = m.group(1), line
        else:
            cur_txt = f"{cur_txt}\n{line}" if cur_txt else line
    flush()
    return sections

def _disambiguate(sections: list[tuple[str | None, str]]) -> list[tuple[str | None, str]]:
    """section_id כפול (למשל 4.2 = אפשרות א/ב) → סיומת מבחינה + לוג warning."""
    counts: dict[str, int] = {}
    for num, _ in sections:
        if num is not None:
            counts[num] = counts.get(num, 0) + 1
    seen: dict[str, int] = {}
    out: list[tuple[str | None, str]] = []
    for num, txt in sections:
        if num is None or counts[num] == 1:
            out.append((num, txt)); continue
        seen[num] = seen.get(num, 0) + 1
        if 'אפשרות א' in txt:
            new = f"{num}-א"
        elif 'אפשרות ב' in txt:
            new = f"{num}-ב"
        else:
            new = f"{num}-{seen[num]}"
        print(f"[extract] duplicate section {num} disambiguated → {new}", flush=True)
        out.append((new, txt))
    return out

def _main_of(sid: str) -> str:
    """המספר הראשי מתוך section_id: '6.1.2'→'6', '4.2-א'→'4', '2'→'2'."""
    return sid.split(".")[0].split("-")[0]

def _classify(chunks: list[Clause]) -> list[Clause]:
    """granularity: כותרת ראשית = קונטקסט (analyze=False) אם יש תחתיה תת-סעיפים; אחרת עצמאית.
    תת-סעיף = יחידת ניתוח (analyze=True) עם parent_heading מוזרק. preamble = לא מנותח."""
    heading_text = {c.section_number: c.text for c in chunks
                    if c.section_number and "." not in c.section_number}
    mains_with_subs = {_main_of(c.section_number) for c in chunks
                       if c.section_number and "." in c.section_number}
    for c in chunks:
        sid = c.section_number
        if sid is None:
            c.kind, c.analyze, c.parent_heading = "preamble", False, None
        elif "." not in sid:                              # כותרת ראשית
            c.kind = "main_heading"
            c.analyze = sid not in mains_with_subs        # עצמאית רק אם אין תת-סעיפים
            c.parent_heading = None
        else:                                             # תת-סעיף
            c.kind, c.analyze = "sub_clause", True
            c.parent_heading = heading_text.get(_main_of(sid))
    return chunks

def extract_clauses(raw_text: str, *, min_sections: int = MIN_SECTIONS,
                    max_avg_chars: int = MAX_AVG_CHARS,
                    max_single_chars: int = MAX_SINGLE_CHARS) -> tuple[list[Clause], ExtractTelemetry]:
    text = normalize_section_numbers(_normalize(raw_text))   # תיקון היפוך RTL לפני ה-split
    if not text:
        tele = ExtractTelemetry(path="empty", n_clauses=0, avg_len=0.0,
                                regex_sections=0, fallback_reason="empty input")
        print("[extract] regex→N=0 | fallback triggered: reason=empty input", flush=True)
        return [], tele

    sections = _disambiguate(_split_sections(text))
    numbered = [s for s in sections if s[0] is not None]
    regex_n = len(numbered)
    avg_numbered = statistics.mean(len(t) for _, t in numbered) if numbered else float("inf")

    fallback_reason = None
    if regex_n < min_sections:
        fallback_reason = f"only {regex_n} numbered sections (< {min_sections})"
    elif avg_numbered > max_avg_chars:
        fallback_reason = f"avg section length {avg_numbered:.0f} > {max_avg_chars}"

    chunks: list[Clause] = []
    idx = 0
    def push(section_number, body):
        nonlocal idx
        t = body.strip()
        if t:
            chunks.append(Clause(id=f"{idx}:{section_number or ''}",
                                 section_number=section_number, text=t, index=idx))
            idx += 1

    if fallback_reason:
        for w in _window(text):
            push(None, w)
        path = "fallback"
        print(f"[extract] regex→N={regex_n} | fallback triggered: reason={fallback_reason}", flush=True)
    else:
        windowed_any = False
        for num, body in sections:
            if len(body) <= max_single_chars:
                push(num, body)
            else:
                windowed_any = True
                for w in _window(body):
                    push(num, w)          # שומר על מספר הסעיף גם בחלונות
        path = "mixed" if windowed_any else "regex"
        avg = statistics.mean(len(c.text) for c in chunks) if chunks else 0.0
        print(f"[extract] regex→N={regex_n} | path={path} | avg_len={avg:.0f}", flush=True)

    _classify(chunks)     # granularity: main_heading vs sub_clause + analyze flag + parent_heading
    avg_len = statistics.mean(len(c.text) for c in chunks) if chunks else 0.0
    tele = ExtractTelemetry(path=path, n_clauses=len(chunks), avg_len=round(avg_len, 1),
                            regex_sections=regex_n, fallback_reason=fallback_reason)
    return chunks, tele
