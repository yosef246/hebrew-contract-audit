# CLAUDE.md — project notes

Hebrew multi-agent lease-contract auditor. Python (LangGraph) over a TypeScript RAG black box.
See `README.md` for architecture. This file holds durable lessons + gotchas for future work.

## Lessons Learned

### Real fixtures reveal what synthetic hides
Stage E was validated on a synthetic sample with clean LTR-style numbering (`1.`, `1.1`). Real
Hebrew PDFs from unpdf produce RTL glyph-ordering issues where digits stay at line-end (`.1` or
`<hebrew> 1.1`). This broke extraction on the first real contract. Fix: a preprocessing normalize
step in `extract.py`. Test: **always validate extract on at least one real fixture before
considering the pipeline stable.**

### Defense in depth for extraction
Real contracts also smuggle non-section digits (years like `2019`, party-detail lines, dates) into
the preamble. One rule isn't enough — `extract.py` layers three barriers: size threshold
(section-id = 1–2 digits/level), preamble boundary (strip everything before the real `1.`), and a
monotonicity validator (main IDs must ascend). Each catches what the others miss.

### Advisor drafts are not ground truth

The rental-01 annotation cycle burned three review rounds because a plausible LLM-drafted judgment
("15.2 is borderline") was rubber-stamped into the fixture as if a human had verified it.
gervis-reviewer caught this three times before the file matched reality. Rule going forward:
`annotated_by: "yosef"` is a declaration that a human read the clause text and independently
decided. It cannot be inferred from advisor context or batch approval. If in doubt, use
`gervis-draft` + null status.

### Single source of truth for fixture metadata

Four consecutive REVISE rounds on rental-01 caught the same fact duplicated in README (3 places)
and JSON (1 place). Duplicated provenance text drifts under edits.

**Rule going forward:** The JSON provenance block is the single source of truth (SSOT) for
fixture metadata. README prose about fixture properties (purpose, metric name, provenance,
ground truth status) is permitted only if guarded by automated invariant checks that fail CI
when README and JSON disagree.

#### Post-F refactor options (choose one when F.6 harness lands)

**Option A — Named invariants (recommended):** Add explicit literal checks to the eval harness
that fail if any of these break:

Requires first adding `provenance.metrics` and per-fixture `purpose` / `metric_emitted` keys to
each annotations JSON; these do not exist yet.

- Invariant 1: The string `false-positive rate` appears in README only in the two sanctioned
  lines within the `### rental-01 (baseline)` subsection (upgrade-path and do-not-call-it lines).
- Invariant 2: The metric name in README's rental-01 subsection (currently `rental-01.flag_rate`)
  matches a metric key in the JSON `provenance.metrics` field.
- Invariant 3: Each fixture's `Purpose` and `Metric emitted` bullets in README must have
  corresponding non-empty fields in the fixture's JSON provenance block.

Add invariants as new claims accrue. Each is a literal test, not semantic comparison.

**Option B — Delete redundancy:**
Strip fixture metadata prose from README entirely. Point readers to the JSON provenance block as
the authoritative source. Trade: less skimmable README, but zero drift risk.

Both are cheap. A is more forgiving; B is more disciplined.

### Empty form fields are NULL, not content

The fixtures are unsigned templates: names, dates and amounts are `____` runs. Yosef's ruling is
that this is fine, because the audit judges the legal clauses, not the values filled into them.

**The rule is semantic, not textual.** The `____` stays in the clause text exactly as extracted —
it is already the clearest marker of an unfilled field. Stripping it was tried and reverted: the
deletion produced broken Hebrew (`תקופת השכירות הנה למשך חודשים בלבד, החל מיום וכלה ביום`), which
reads to a model as a malformed sentence rather than as a form with an empty slot. What the rule
forbids is *interpreting* a blank: never treat it as a value, never flag it as a defect.

Consequence for annotation: a clause is judged on its **mechanism**, not its numbers. `12.2` in
rental-02 is annotatable on "agreed daily compensation with no proof of damage required" even
though the rate is blank. Do not mark a clause `null` merely because a value was left empty.

**Enforced in `ANALYZER_SYSTEM` rule 9** (`agents/prompts.py`). Without it, rule 5 routes a blank
into `missing_info` and rule 8 can set `norm_deviation_without_source`, which `graph.py` converts
straight to `unverified_concern` — so blanks would inflate the flag rate on their own. Rule 9 is
deliberately narrow: it forbids flagging a clause *because* a field is empty, not flagging the
clause. `12.2` must still be judgeable on "agreed daily compensation, no proof of damage".

Not yet measured live: no analyzer run has confirmed the behaviour either way (`ANTHROPIC_API_KEY`
and `RAG_INTERNAL_TOKEN` are not set in the dev shell). Eight units carry blanks — rental-01 3.1,
4.1, 4.2-א, 13.1 and rental-02 2, 6.1, 12.2, 16.1 — and `agents/diag_placeholder.py` is the probe
over them (never executed; see its docstring).

## Known Issues

- **DOCX support** — `python-docx` returns paragraph text **without list numbers** (Word
  auto-numbering lives in `numbering.xml`, not the text). So numbered DOCX contracts extract to
  0 sections → fallback. Full resolution (reconstruct numbering from `numId`/`ilvl`) is planned for
  **post-F / deploy-prep**. Until then, DOCX fixtures do **not** enter the eval.
- **Analyzer non-determinism** — `norm_deviation_without_source` flips run-to-run on Sonnet-5.
  Mitigate with self-consistency **in the eval harness only**, never production.
- **Coherence LLM-path** — unexercised live (runs so far had <2 corrected clauses). Needs a
  dedicated ground-truth case, not a prompt-coupled test.

## Conventions

- Extractor thresholds live at the top of `extract.py` (`MIN_SECTIONS`, `MAX_AVG_CHARS`,
  `MAX_SINGLE_CHARS`, `MONO_GAP`) — never hard-code them mid-file.
- Fixtures privacy: real contracts + extracted text are git-ignored; only `sample-00.txt` and
  `fixtures/annotations/*.json` (judgments, no text) are committed. See README § Fixtures & Privacy.
- Annotations are **human** ground truth — never auto-fill with an LLM.
