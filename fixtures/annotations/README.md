# Annotations — human ground truth

Labels for the eval harness. **No contract text or PII** — only judgments keyed by `clause_id`,
so these files are safe to commit and share. One JSON per contract + a matching schema.

> **These are HUMAN ground truth, not LLM output.** A person (Yosef / reviewer) fills them by hand.
> Never auto-fill `expected_status` with a model — the whole point is an independent yardstick to
> measure the pipeline against. The git commit that fills a file *is* the record of who/when.

## Files

- `rental-01.annotations.schema.json` — JSON Schema for the annotation file.
- `rental-01.annotations.json` — skeleton: 43 analysis-unit IDs (the sub-clauses), all `null`.

## Entry format

```json
{
  "clause_id": "4.2-א",
  "expected_status": null,     // ← fill by hand
  "notes": null,               // short rationale, NO clause text (e.g. "חילוט מוגזם")
  "annotated_by": null,        // "yosef"
  "annotated_at": null         // ISO date, e.g. "2026-09-10"
}
```

`clause_id` = the sub-clause `section_number` from the extractor (analysis units only — main
headings are context, not annotated).

## When to use each status

Match `state.ClauseStatus`. For annotation, use these four:

| `expected_status` | Use when the clause… |
|---|---|
| `ok` | is fine — nothing to fix, no concern. |
| `corrected` | is problematic **and** the law corpus supports flagging it → a grounded fix is expected. |
| `unverified_concern` | reads as deviating from norms **but** no corpus source grounds it → surface, don't assert. |
| `requires_human_review` | genuinely needs a lawyer's eye (ambiguous, out of the corpus's reach). |

Leave `null` until decided. `notes`: one short phrase, **never** paste the clause text.

## How to fill

1. Open `rental-01.annotations.json`.
2. For each `clause_id`, read the clause in the source PDF (local, git-ignored) and set
   `expected_status`, `notes`, `annotated_by`, `annotated_at`.
3. `git commit` — that commit is the provenance record.

## What the eval measures (later)

- precision / recall per `expected_status`.
- agreement rate on similar clauses (catches the Analyzer non-determinism — main README).
- whether `regex` vs `fallback` extraction path governs the outcome.

**Status:** `rental-01` skeleton generated (43 IDs, all `null`). Awaiting human annotation.
