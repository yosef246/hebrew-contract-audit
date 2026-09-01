# diag_retrieval.py — retrieval diagnostic. קורא ל-retrieve_law ישירות עם כמה ניסוחים.
import rag_client as rc

QUERIES = [
    "כניסת המשכיר לדירה הודעה מראש",
    "זכות השוכר לפרטיות ושימוש שקט",
    "מסירת הודעה סבירה לפני כניסה",
    "חובת המשכיר לפני ביקור בדירה",
    "המשכיר רשאי להיכנס לנכס בכל עת ללא הודעה מראש",  # הסעיף המקורי המלא
]

for q in QUERIES:
    print(f"\n=== query: {q!r} ===")
    hits = rc._retrieve_law_http(q, k=4)
    for s in hits:
        print(f"  [{s.marker}] {s.label}   sim={s.similarity:.3f}")
