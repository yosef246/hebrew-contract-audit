# Annotations — human ground truth

Labels for the eval harness. **No contract text or PII** — only judgments keyed by `clause_id`,
so these files are safe to commit and share. One JSON per contract + a matching schema.

> **These are HUMAN ground truth, not LLM output.** A person (Yosef / reviewer) fills them by hand.
> Never auto-fill `expected_status` with a model — the whole point is an independent yardstick to
> measure the pipeline against. The git commit that fills a file *is* the record of who/when.

**Exception — rental-01 baseline:** All 43 rows are LLM-drafted notes with
`expected_status: null` and `annotated_by: "gervis-draft"`. No `expected_status` was auto-filled
(all null), and no row is scored by the eval harness. The "never auto-fill" rule remains in force
for every future annotation.

## Files

- `annotations.schema.json` — JSON Schema shared by every annotation file.
- `rental-01.annotations.json` — rental-01: baseline-only fixture (all 43 clauses
  gervis-draft, no human-verified labels). Emits an unscored flag rate only — a clean
  LeaseLink template the system should ideally not flag. See Fixture roles below.
- `rental-02.annotations.json` — rental-02: skeleton, 37 analysis units, all labels
  `null`. Awaiting human per-clause annotation. See Fixture roles below.

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

1. Create `fixtures/annotations/rental-02.annotations.json` (skeleton file — `extract_clauses`
   output for rental-02, all statuses `null`). This is where human ground truth begins.

   Note: `rental-01.annotations.json` is closed as LLM-drafted baseline (see Provenance model
   below). Do not modify — future contracts start at rental-02.
2. For each `clause_id`, read the clause in the source PDF (local, git-ignored) and set
   `expected_status`, `notes`, `annotated_by`, `annotated_at`.
3. `git commit` — that commit is the provenance record.

## What the eval measures (later)

- precision / recall per `expected_status`.
- agreement rate on similar clauses (catches the Analyzer non-determinism — main README).
- whether `regex` vs `fallback` extraction path governs the outcome.

**Status:** `rental-01`: closed as gervis-draft baseline.
`rental-02`: awaiting human annotation (this is where ground truth begins).
`rental-03`: post-F (DOCX support pending).

## Provenance model

- `annotated_by: "yosef"` → human independently read the clause and decided. Only labels for
  eval ground truth.
- `annotated_by: "gervis-draft"` → LLM-drafted (from advisor sessions), rubber-stamped in batch,
  NOT independently adjudicated. `expected_status` is `null` — excluded from eval scoring.
- Eval harness filters: `expected_status != null AND annotated_by != "gervis-draft"`

## Fixture roles

### rental-01 (baseline)

- **Purpose:** Sanity check. Sends an unvetted public lease template through the pipeline; ideally
  the system does not flag any clause. No ground truth labels exist for this fixture.
- **Metric emitted:** `rental-01.flag_rate` — count of clauses the pipeline classified as
  `unverified_concern` or `corrected`. Unscored (no comparison to ground truth).
- **Upgrade path:** If a human independently annotates all 43 rows (setting
  `annotated_by: "yosef"` with real `expected_status`), the same filter converts this into a true
  false-positive rate — no code change required.
- **Do not call this a "false-positive rate."** That phrase assumes ground truth we don't have.

### rental-02 and rental-03

- **rental-02** (Hebrew lease template, hand-populated 2026-09-09): the first fixture to
  carry human-verified per-clause labels. Term, dates, rent and the late-vacate rate hold
  real values, so clauses are judged on their actual terms rather than on mechanism
  alone. Still a filled template, not a signed lease. Where an empty field (`____`)
  remains it counts as NULL — never a value, never a defect. All 37 units are
  annotatable.
- **rental-03** (DOCX): deferred to post-F.
