# extract.py — ClauseExtractor דטרמיניסטי (קוד רגיל, רץ לפני הגרף).
# פורט של src/lib/chunking/contract-chunker.ts, עם שינוי מכוון אחד: trigger מפורש ל-fallback
# (לא רק "אפס סעיפים ממוספרים" כמו ב-TS) — < MIN_SECTIONS או avg length > MAX_AVG_CHARS.
import re
import statistics
from pydantic import BaseModel
from state import Clause

SECTION_RE = re.compile(r'^\s*(\d+[א-ת]?)\.?\s+')   # "1.", "1א.", "2 " — ספרה + סיומת-אות אופציונלית
WINDOW_SIZE = 500
WINDOW_OVERLAP = 50
MAX_SECTION_CHARS = 1500        # סעיף ממוספר ארוך מזה — מחלונים אותו (שומר על מספר הסעיף)

# --- טריגרים מפורשים ל-fallback (מעבר ל-TS) ---
MIN_SECTIONS = 3                # < 3 סעיפים ממוספרים → כנראה ה-split לא זיהה כותרות
MAX_AVG_CHARS = 1200            # סעיף ממוצע ענק → סימן שה-headers לא זוהו

class ExtractTelemetry(BaseModel):
    path: str                   # "regex" | "mixed" | "fallback" | "empty"
    n_clauses: int
    avg_len: float
    regex_sections: int         # כמה כותרות ממוספרות ה-regex תפס (לפני fallback)
    fallback_reason: str | None = None

def _normalize(raw: str) -> str:
    cleaned = re.sub(r'\r\n?', '\n', raw)
    cleaned = '\n'.join(line.rstrip(' \t') for line in cleaned.split('\n')).strip()
    # מציב כל מרקר ממוספר ("7. ", "13. ") בתחילת שורה, בין אם ה-extractor שמר שורות ובין אם השטיח.
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

def extract_clauses(raw_text: str, *, min_sections: int = MIN_SECTIONS,
                    max_avg_chars: int = MAX_AVG_CHARS) -> tuple[list[Clause], ExtractTelemetry]:
    text = _normalize(raw_text)
    if not text:
        tele = ExtractTelemetry(path="empty", n_clauses=0, avg_len=0.0,
                                regex_sections=0, fallback_reason="empty input")
        print(f"[extract] regex→N=0 | fallback triggered: reason=empty input", flush=True)
        return [], tele

    sections = _split_sections(text)
    numbered = [s for s in sections if s[0] is not None]
    regex_n = len(numbered)
    avg_numbered = statistics.mean(len(t) for _, t in numbered) if numbered else float("inf")

    # --- החלטת מסלול ---
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
            if len(body) <= MAX_SECTION_CHARS:
                push(num, body)
            else:
                windowed_any = True
                for w in _window(body):
                    push(num, w)          # שומר על מספר הסעיף גם בחלונות
        path = "mixed" if windowed_any else "regex"
        avg = statistics.mean(len(c.text) for c in chunks) if chunks else 0.0
        print(f"[extract] regex→N={regex_n} | path={path} | avg_len={avg:.0f}", flush=True)

    avg_len = statistics.mean(len(c.text) for c in chunks) if chunks else 0.0
    tele = ExtractTelemetry(path=path, n_clauses=len(chunks), avg_len=round(avg_len, 1),
                            regex_sections=regex_n, fallback_reason=fallback_reason)
    return chunks, tele
