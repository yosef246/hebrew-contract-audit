# Annotations — ground-truth schema

Human labels for the eval harness. **No contract text or PII** — only judgments keyed by
`section_id`, so these files are safe to commit and share.

One JSON per contract: `fixtures/annotations/<contract>.json` (e.g. `rental-01.json`).

## Schema

```json
{
  "contract": "rental-01",
  "extractor": { "path": "regex", "n_clauses": 14 },
  "clauses": [
    { "section_id": "1", "expected_status": "problematic",
      "expected_law": "חוק השכירות §25י", "note": "חילוט גורף" },
    { "section_id": "2", "expected_status": "ok" },
    { "section_id": "7", "expected_status": "unverified_concern" }
  ]
}
```

- `section_id` — the clause's `section_number` from the extractor (or its `id` for un-numbered).
- `expected_status` — one of: `ok` · `unverified_concern` · `problematic` · `corrected` ·
  `requires_human_review` · `retrieval_failed` (matches `state.ClauseStatus`).
- `expected_law` *(optional)* — the grounding source a correct analysis should cite.
- `note` *(optional)* — short rationale. Keep it generic; **never paste clause text**.

## What the eval measures (later)

- precision / recall per `expected_status`.
- agreement rate on similar clauses (catches the Analyzer non-determinism — see main README
  Known issues #1).
- whether the corpus governs the outcome via `regex` vs `fallback` extraction path.

**Not yet populated** — annotation waits for approval on which contracts to label.
