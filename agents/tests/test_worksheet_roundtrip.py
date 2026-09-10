# -*- coding: utf-8 -*-
"""tests/test_worksheet_roundtrip.py — regenerating the worksheet and parsing it back
must NOT re-stamp annotated_at on rows that did not change.

Exists because the seeding fix caused exactly that: make_worksheet seeds STATUS/NOTES
from the JSON, so every committed row comes back "filled", and apply() re-stamped the
date unconditionally — silently replacing real decision dates with the re-run date on
the very workflow the README recommends.
"""
import io, json, os, shutil, sys, tempfile, importlib.util, collections

HERE = os.path.dirname(os.path.abspath(__file__))
AGENTS = os.path.dirname(HERE)
os.chdir(os.path.dirname(AGENTS))
spec = importlib.util.spec_from_file_location("pw", os.path.join(AGENTS, "parse_worksheet.py"))
pw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pw)

SRC = "data/rental-02.worksheet.md"

def _decode(path):
    b = open(path, "rb").read()
    for e in ("utf-8-sig", "utf-16", "utf-8"):
        try:
            return b.decode(e).lstrip("\ufeff").replace("\r\n", "\n")
        except UnicodeDecodeError:
            continue
    raise ValueError(path)

def test_unchanged_rows_keep_their_date():
    if not os.path.exists(SRC):
        print(f"SKIP  {SRC} not present (gitignored worksheet)")
        return
    labelled = {r["clause_id"]: r for r in
                json.load(io.open(pw.J, encoding="utf-8"))["annotations"]
                if r["expected_status"]}
    if not labelled:
        print("SKIP  no labelled rows to round-trip yet")
        return

    # a seeded worksheet: every committed label comes back as a filled STATUS line
    txt = _decode(SRC)
    blocks = txt.split("## ")
    out = [blocks[0]]
    for b in blocks[1:]:
        sid = b.split("\n", 1)[0].split("סעיף ", 1)[-1].strip()
        r = labelled.get(sid)
        if r:
            b = b.replace("STATUS: \n", f"STATUS: {r['expected_status']}\n", 1)
            b = b.replace("NOTES: \n", f"NOTES: {r['notes']}\n", 1)
        out.append(b)
    seeded = os.path.join(tempfile.gettempdir(), "seeded_worksheet.md")
    io.open(seeded, "w", encoding="utf-8", newline="\n").write("## ".join(out))

    parsed = pw.parse(seeded)
    d, filled = pw.apply(parsed, dry=True, today="2099-01-01")
    rows = {r["clause_id"]: r for r in d["annotations"]}
    drifted = [c for c, r in labelled.items() if rows[c]["annotated_at"] != r["annotated_at"]]
    assert not drifted, (
        f"annotated_at was overwritten on {drifted} — a re-run must not restamp "
        f"rows whose status and notes are unchanged")
    print(f"PASS  test_unchanged_rows_keep_their_date ({len(labelled)} rows kept their date)")

if __name__ == "__main__":
    try:
        test_unchanged_rows_keep_their_date()
        print("\nALL PASS")
    except AssertionError as e:
        print(f"FAIL  {e}\n\n1 FAILED"); sys.exit(1)
