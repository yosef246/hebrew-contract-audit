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
