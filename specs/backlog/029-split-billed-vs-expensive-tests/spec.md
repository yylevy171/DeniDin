# Feature Spec: Split `expensive` Marker into `billed` and `expensive`

**Feature ID**: 029-split-billed-vs-expensive-tests
**Priority**: P2
**Status**: Draft
**Created**: July 30, 2026

---

## Problem Statement

`apps/denidin-app/pytest.ini` currently has one marker, `expensive`, covering
every test under `tests/expensive/` that hits a real OpenAI API — text-only
calls (`test_simple_text_e2e.py`, `test_ai_handler_real_api.py`,
`test_ledger_event_capture_e2e.py`, `test_session_transfer.py`) and
vision/document calls (`test_media_e2e.py`'s image/PDF/DOCX extraction via
`ImageExtractor`/`PDFExtractor`, `test_denidin_morning_document_creation_e2e.py`)
are all gated identically: excluded by default (`addopts = -m "not expensive"`),
require explicit approval per CLAUDE.md's "Expensive test rules", run one at a
time.

Text-only chat completions are cheap (small prompt, `gpt-4o-mini`). Image/PDF
extraction calls a vision model per page/image and can involve multiple
sequential OpenAI calls per test (`PDFExtractor` delegates to `ImageExtractor`
per page, max 10 pages) — meaningfully more expensive per run. Today both look
identical in `pytest --collect-only -m expensive` output and in the approval
conversation ("run an expensive test" doesn't tell the approver which kind).
Splitting the marker would let cost-sensitive decisions (which to approve,
which to prioritize investigating via existing logs before re-running) be made
with the actual cost tier visible, without changing the approval-required
policy itself for either tier.

## Open Questions (not yet clarified)

- **Exact split of existing tests.** First pass, needs confirmation against
  each file's actual OpenAI calls: `billed` → `test_simple_text_e2e.py`,
  `test_ai_handler_real_api.py`, `test_session_transfer.py`,
  `test_ledger_event_capture_e2e.py`, `test_denidin_morning_mcp_e2e.py`
  (text-only MCP tool-call turns); `expensive` → `test_media_e2e.py`,
  `test_denidin_morning_document_creation_e2e.py` (any test that extracts an
  image/PDF/DOCX). Some files may need per-test (not per-file) marking if they
  mix both kinds.
- **Does `expensive` become a strict superset requirement, or two independent
  markers?** i.e. should `-m expensive` still catch everything (billed +
  media), or should `billed` and `expensive` be fully separate marks with no
  overlap, requiring `-m "billed or expensive"` to run both? Affects
  `pytest.ini`'s `addopts` default-skip expression and CI-adjacent tooling
  that references `-m expensive` today.
- **Do the "Expensive test rules" in CLAUDE.md (one-at-a-time, approval every
  time, no speculative re-runs) apply identically to both tiers, or does
  `billed` get a lighter-weight version** (e.g. still needs approval, but
  multiple `billed` tests could run in one approved batch since each is
  individually cheap)? Needs an explicit decision — this spec should not
  silently loosen the existing discipline.
- **Rename or add?** Keep `expensive` meaning "media/document, real vision
  calls" and add `billed` as the new, narrower text-only marker (no rename of
  existing test files' marks needed for the media ones) vs. introduce both as
  new names and retire the current overloaded `expensive` meaning. The former
  is a smaller diff.

## References

- `apps/denidin-app/pytest.ini` — `markers`/`addopts` definitions to be extended.
- `apps/denidin-app/tests/expensive/` — the test files needing (re)classification.
- CLAUDE.md's "Expensive test rules (strict)" section — governs today's single-tier policy; this spec must state explicitly which rules carry over per tier rather than leaving it ambiguous.
