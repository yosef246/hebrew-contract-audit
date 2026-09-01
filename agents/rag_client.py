# rag_client.py — הגישה היחידה ל-RAG (black box ב-TS). stdlib + pydantic בלבד.
import json, os, urllib.request, urllib.error
from state import Source   # Source מוגדר פעם אחת ב-state.py (single source of truth)

RAG_URL   = os.getenv("RAG_URL", "http://localhost:3000/api/rag/retrieve")
RAG_TOKEN = os.environ["RAG_INTERNAL_TOKEN"]   # fail-fast — חייב להיות זהה ל-.env.local של Next
RAG_TIMEOUT = 20

def _request(payload: dict, token: str) -> list[dict]:
    """ה-primitive היחיד. מחזיר sources על 200; מרים urllib.error.HTTPError על 4xx/5xx.
       גם _retrieve_law_http וגם ה-smoke test עוברים דרכו — אותו מסלול, קלטים שונים."""
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(RAG_URL, data=body,
        headers={"Content-Type": "application/json", "X-RAG-Token": token})
    with urllib.request.urlopen(req, timeout=RAG_TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))["sources"]

def _retrieve_law_http(query: str, k: int = 4) -> list[Source]:
    """המסלול האמיתי שה-tool retrieve_law ישתמש בו."""
    rows = _request({"query": query, "k": k}, RAG_TOKEN)
    return [Source(**row) for row in rows]
