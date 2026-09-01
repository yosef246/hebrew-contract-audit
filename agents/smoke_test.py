# smoke_test.py — הרץ עם שרת Next חי (:3000) ו-RAG_INTERNAL_TOKEN מוגדר בסביבה.
import urllib.error
import rag_client as rc

def check_401():
    try:
        rc._request({"query": "בדיקה"}, token="wrong")
    except urllib.error.HTTPError as e:
        print(f"[401] status={e.code}  body={e.read().decode('utf-8')}")
        assert e.code == 401, f"expected 401, got {e.code}"
    else:
        print("[401] FAIL — לא הורם HTTPError")

def check_400():
    try:
        rc._request({}, token=rc.RAG_TOKEN)   # 'query' חסר
    except urllib.error.HTTPError as e:
        print(f"[400] status={e.code}  body={e.read().decode('utf-8')}")
        assert e.code == 400, f"expected 400, got {e.code}"
    else:
        print("[400] FAIL — לא הורם HTTPError")

def check_200():
    sources = rc._retrieve_law_http("סעיף העברה בשכירות")   # המסלול האמיתי
    print(f"[200] התקבלו {len(sources)} מקורות")
    assert sources, "ציפיתי ל-≥1 מקור"
    first = sources[0]
    print(f"      marker={first.marker!r}")
    print(f"      label ={first.label!r}")
    print(f"      similarity={first.similarity}  (type={type(first.similarity).__name__})")
    assert first.marker == "1", f"marker צריך '1', התקבל {first.marker!r}"
    assert "§" in first.label, "label חסר §"

if __name__ == "__main__":
    check_401(); check_400(); check_200()
    print("\n✓ smoke test done")
