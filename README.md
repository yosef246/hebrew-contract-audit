# Hebrew Contract Audit

Multi-agent auditor for Israeli residential lease contracts. A LangGraph pipeline replaces a
single-shot analysis with **Agent → Validator → Retry**, grounded in a Hebrew legal RAG corpus.
Every conclusion carries a citation from the corpus; the system says *"בהתאם למקורות במאגר"* and
never *"legal, 100%"*. Ungrounded-but-suspicious clauses are surfaced, not buried.

## Architecture

```
ClauseExtractor (deterministic, pre-graph)
      │  state.clauses[]
      ▼
┌──────────────── LangGraph (checkpointed, thread = contractId) ─────────────────┐
│ analyze ──(problematic?)──▶ correct ─▶ validate ──(valid? / retry<3?)──▶ advance │
│    │ else                                                     ▲          │       │
│    └──────────────────────────────────────────────────────────┘          │      │
│ advance ──(more clauses? → analyze / done → coherence) ─▶ coherence ─▶ report    │
└────────────────────────────────────────────────────────────────────────────────┘
```

- **Separation of concerns:** Corrector and Validator are separate LLMs. The Validator retrieves
  law **independently** (by the original clause) and never sees the Corrector's sources — the
  "creator does not judge itself" guarantee.
- **RAG is a black box** (TypeScript, in `web/`): the agents reach it only via `retrieve_law` →
  the `/api/rag/retrieve` HTTP endpoint. The Python side never embeds or touches Postgres.

## Layout

| Path | What |
|---|---|
| `agents/` | All Python: `state.py`, `rag_client.py`, `prompts.py`, `graph.py`, `extract.py`, tests |
| `web/` | TypeScript: PDF extractor (`unpdf` + bidi), RAG endpoint, future UI |
| `fixtures/` | Real contracts + ground-truth annotations |
| `data/` | Sqlite checkpoints + `telemetry.jsonl` (git-ignored) |

## Running (dev)

```bash
# 1. web RAG endpoint must be up (provides retrieve_law)
#    → serves POST /api/rag/retrieve on :3000
# 2. env: RAG_INTERNAL_TOKEN (matches web), ANTHROPIC_API_KEY
export RAG_INTERNAL_TOKEN=... ANTHROPIC_API_KEY=...
cd agents
python test_f_graph.py     # end-to-end graph + Sqlite persistence + resume
python test_extract.py     # ClauseExtractor edge cases
```

## Extractor thresholds (`agents/extract.py`)

Fallback (whole-doc windowing) triggers when the numbered-section split looks unreliable:

| Constant | Value | Meaning |
|---|---|---|
| `MIN_SECTIONS` | 3 | Fewer numbered sections than this → split failed → fallback |
| `MAX_AVG_CHARS` | 2000 | Average section longer than this → headers not detected → fallback |
| `MAX_SINGLE_CHARS` | 4000 | A single section this large → split failed on it → window it |

## Known issues (tracked; feed the eval)

1. **`AnalyzerVerdict.norm_deviation_without_source` is non-deterministic on Sonnet-5** — same
   clause flips ok ⇄ unverified_concern across runs. Mitigation: self-consistency (N-vote) **in the
   eval harness only**, not production, until a labelled fixture exists to measure it.
2. **Coherence LLM-path unexercised** — runs so far had <2 `corrected` clauses, so `coherence_node`
   short-circuits. A dedicated case (2 contradicting corrected clauses) must live in the ground-truth
   fixture, not a standalone prompt-coupled test.
3. **Structured-output field omission** — Sonnet-5 occasionally drops a required field
   (e.g. `is_problematic`). Guarded by `_structured()` retry (2×).
4. **Extractor granularity** — sub-sections (`1.א`, `1.1`) are absorbed into the parent numbered
   clause; letter-only numbering (`א.`, `ב.`) falls back (structure lost). Decide desired
   granularity when building the fixture.

## Production readiness (deploy prep — NOT now)

- [ ] **Postgres checkpointer** — dev uses `SqliteSaver`; swap to `PostgresSaver` (one line in
      `build_graph`). Needs the Supabase Postgres DSN (Dashboard → Database → Connection string).
- [ ] **msgpack serde** — register custom Pydantic types (Clause, AnalysisResult, …) via
      `allowed_msgpack_modules` before relying on Postgres persistence.
- [ ] Telemetry: `NodeTelemetry.tokens_used` currently stubbed (in-state); the append-only
      `data/telemetry.jsonl` carries the real per-call metrics.
