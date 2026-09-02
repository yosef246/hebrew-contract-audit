# extract.py — ClauseExtractor דטרמיניסטי (קוד רגיל, רץ לפני הגרף).
# פורט של contract-chunker.ts + שינויים מכוונים:
#   1. trigger מפורש ל-fallback (MIN_SECTIONS / MAX_AVG_CHARS / MAX_SINGLE_CHARS).
#   2. normalize_section_numbers — תיקון היפוך מספרי-סעיף ב-RTL (unpdf שם בקצה השורה).
#   3. defense-in-depth נגד סעיפי-שווא (שנים, פרמבל): size-threshold + preamble-boundary + monotonicity.
import re
import statistics
from pydantic import BaseModel, Field
from state import Clause

# section id תקין: כל רמה 1-2 ספרות, עד 3 רמות, סיומת-אות אופציונלית. "12.3"✓ "15.1.2"✓ "2019"✗ "100"✗
SECTION_RE = re.compile(r'^\s*(\d+(?:\.\d+)*[א-ת]?)\.?\s+')
_VALID_SEC = re.compile(r'^\d{1,2}(?:\.\d{1,2}){0,2}[א-ת]?$')     # מחסום 1: size threshold
WINDOW_SIZE = 500
WINDOW_OVERLAP = 50

# --- ספי החלטה (fallback / windowing) — מרוכזים כאן, מתועדים ב-README ---
MIN_SECTIONS     = 3
MAX_AVG_CHARS    = 2000
MAX_SINGLE_CHARS = 4000
MONO_GAP         = 3       # מחסום 3: פער מותר בין מספרי סעיף עוקבים (סעיף חסר לגיטימי)

class ExtractTelemetry(BaseModel):
    path: str                   # "regex" | "mixed" | "fallback" | "empty"
    n_clauses: int
    avg_len: float
    regex_sections: int
    fallback_reason: str | None = None
    preamble_text: str = ""                                       # מחסום 2: כל מה שלפני "1." האמיתי
    rejected_ids: list[dict] = Field(default_factory=list)        # מחסום 3: [{id, reason, context}]

def _valid_section(num: str) -> bool:
    """מחסום 1: section-id חוקי = כל רמה 1-2 ספרות. פוסל שנים (2019), מספרים גדולים (100), /,-."""
    return bool(_VALID_SEC.match(num))

# --- normalize: מזיז מספר-סעיף חוקי מקצה השורה לתחילתה (תיקון היפוך RTL) ---
_LEAD_MAIN = re.compile(r'^\.\s+(.*?)\s*(\d+)\s*$')             # A' (LeaseLink בפועל): ". <טקסט><ספרה>"
_TAIL_SUB  = re.compile(r'^(.*?\S)\s+(\d+\.\d+(?:\.\d+)?)\s*$') # B: "<טקסט> N.N / N.N.N"
_TAIL_MAIN = re.compile(r'^(.*?\S)\s+(\d+)\.\s*$')              # C: "<טקסט> N."
_TAIL_DOTN = re.compile(r'^(.*?\S)\s+\.(\d+)\s*$')             # A (המקורי מהספק): "<טקסט> .N"
_ONLY_SYMS = re.compile(r'^[\d.\-/()\s]*$')

def normalize_section_numbers(text: str) -> str:
    """מזיז מספרי-סעיף שהיפוך-RTL שם בקצה השורה חזרה לתחילתה. מזיז רק מספר חוקי (מחסום 1);
    skip: שורות קצרות של סמלים בלבד, וספרות באמצע שורה (מתאימים רק על גבול-שורה $)."""
    out: list[str] = []
    for line in text.split('\n'):
        s = line.rstrip()
        stripped = s.strip()
        if len(stripped) < 10 and _ONLY_SYMS.match(stripped):      # skip: מספר עמוד / כותרת קצרה
            out.append(line); continue
        moved = False
        for rx, fmt in ((_LEAD_MAIN, "{n}. {t}"), (_TAIL_SUB, "{n} {t}"),
                        (_TAIL_MAIN, "{n}. {t}"), (_TAIL_DOTN, "{n}. {t}")):
            m = rx.match(s)
            if m and _valid_section(m.group(2)):                   # מחסום 1: לא מזיזים שנה/מספר-ענק
                out.append(fmt.format(n=m.group(2), t=m.group(1).strip()))
                moved = True
                break
        if not moved:
            out.append(line)
    return '\n'.join(out)

def _normalize(raw: str) -> str:
    cleaned = re.sub(r'\r\n?', '\n', raw)
    cleaned = '\n'.join(line.rstrip(' \t') for line in cleaned.split('\n')).strip()
    return re.sub(r'[ \t]+(\d{1,2}[א-ת]?\.[ \t])', r'\n\1', cleaned)

def _find_body_start(lines: list[str]) -> int:
    """מחסום 2: אינדקס תחילת גוף החוזה = השורה הראשונה '1. <טקסט>'. strict: טקסט ≥10 תווים;
    fallback: '1' עם תוכן כלשהו. מה שלפני = preamble."""
    for i, ln in enumerate(lines):                                # strict
        m = SECTION_RE.match(ln)
        if m and m.group(1) == "1" and len(ln[m.end():].strip()) >= 10:
            return i
    for i, ln in enumerate(lines):                                # fallback: "1" עם תוכן כלשהו
        m = SECTION_RE.match(ln)
        if m and m.group(1) == "1" and ln[m.end():].strip():
            return i
    return 0                                                      # אין "1" ברור → בלי preamble

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
        if m and _valid_section(m.group(1)):        # מחסום 1: רק section-id חוקי פותח סעיף
            flush()
            cur_num, cur_txt = m.group(1), line
        else:
            cur_txt = f"{cur_txt}\n{line}" if cur_txt else line
    flush()
    return sections

def _main_of(sid: str) -> str:
    return sid.split(".")[0].split("-")[0]

def _monotonic_filter(sections):
    """מחסום 3: מספרי סעיף ראשיים חייבים לעלות (עם פער ≤ MONO_GAP לסעיף חסר לגיטימי);
    תת-סעיפים חייבים לעלות בתוך אותו הורה. חריגים → rejected (התוכן נמזג לסעיף הקודם)."""
    rejected: list[dict] = []
    def _reject(kept, num, text, reason):
        rejected.append({"id": num, "reason": reason, "context": text[:60].replace("\n", " ")})
        if kept:                                    # לא לאבד טקסט — מזג להורה/קודם
            pn, pt = kept[-1]; kept[-1] = (pn, f"{pt}\n{text}")

    kept: list[tuple[str | None, str]] = []
    expected = 1
    for num, text in sections:
        if num is None or "." in num:               # preamble / sub — נבדק בפאס הבא
            kept.append((num, text)); continue
        try:
            n = int(_main_of(num))
        except ValueError:
            kept.append((num, text)); continue
        if n == expected:
            kept.append((num, text)); expected += 1
        elif expected < n <= expected + MONO_GAP:   # פער קטן = סעיף חסר לגיטימי
            kept.append((num, text)); expected = n + 1
        else:                                        # drop / big jump (שנה, שווא)
            _reject(kept, num, text, "monotonicity")
            print(f'[extract] rejected non-monotonic id "{num}" (expected ~{expected})', flush=True)

    final: list[tuple[str | None, str]] = []
    last_sub: dict[str, int] = {}
    for num, text in kept:
        if num and "." in num:
            try:
                m = int(num.split("-")[0].split(".")[1])
            except (IndexError, ValueError):
                final.append((num, text)); continue
            parent = _main_of(num)
            if m >= last_sub.get(parent, 0):        # עולה (dup מטופל ב-_disambiguate)
                last_sub[parent] = m; final.append((num, text))
            else:
                _reject(final, num, text, "sub-monotonicity")
                print(f'[extract] rejected non-monotonic sub-id "{num}"', flush=True)
        else:
            final.append((num, text))
    return final, rejected

def _disambiguate(sections: list[tuple[str | None, str]]) -> list[tuple[str | None, str]]:
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

def _classify(chunks: list[Clause]) -> list[Clause]:
    heading_text = {c.section_number: c.text for c in chunks
                    if c.section_number and "." not in c.section_number}
    mains_with_subs = {_main_of(c.section_number) for c in chunks
                       if c.section_number and "." in c.section_number}
    for c in chunks:
        sid = c.section_number
        if sid is None:
            c.kind, c.analyze, c.parent_heading = "preamble", False, None
        elif "." not in sid:
            c.kind = "main_heading"
            c.analyze = sid not in mains_with_subs
            c.parent_heading = None
        else:
            c.kind, c.analyze = "sub_clause", True
            c.parent_heading = heading_text.get(_main_of(sid))
    return chunks

def extract_clauses(raw_text: str, *, min_sections: int = MIN_SECTIONS,
                    max_avg_chars: int = MAX_AVG_CHARS,
                    max_single_chars: int = MAX_SINGLE_CHARS) -> tuple[list[Clause], ExtractTelemetry]:
    text = normalize_section_numbers(_normalize(raw_text))     # RTL fix (מזיז רק מספר חוקי)
    if not text:
        print("[extract] regex→N=0 | fallback triggered: reason=empty input", flush=True)
        return [], ExtractTelemetry(path="empty", n_clauses=0, avg_len=0.0,
                                    regex_sections=0, fallback_reason="empty input")

    lines = text.split('\n')
    body_start = _find_body_start(lines)                       # מחסום 2: גבול פרמבל
    preamble_text = '\n'.join(lines[:body_start]).strip()
    body_text = '\n'.join(lines[body_start:])

    sections, rejected = _monotonic_filter(_split_sections(body_text))   # מחסומים 1(ב-split)+3
    sections = _disambiguate(sections)
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
        for w in _window(body_text or text):
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
                    push(num, w)
        path = "mixed" if windowed_any else "regex"
        avg = statistics.mean(len(c.text) for c in chunks) if chunks else 0.0
        print(f"[extract] regex→N={regex_n} | path={path} | avg_len={avg:.0f}", flush=True)

    _classify(chunks)
    avg_len = statistics.mean(len(c.text) for c in chunks) if chunks else 0.0
    return chunks, ExtractTelemetry(path=path, n_clauses=len(chunks), avg_len=round(avg_len, 1),
                                    regex_sections=regex_n, fallback_reason=fallback_reason,
                                    preamble_text=preamble_text, rejected_ids=rejected)
