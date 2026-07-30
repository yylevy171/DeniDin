# Feature Spec: Split `expensive` Marker into `billed` and `expensive`

**Feature ID**: 029-split-billed-vs-expensive-tests
**Priority**: P2
**Status**: Clarified
**Created**: July 30, 2026
**Clarified**: July 30, 2026

---

## Scope Correction (2026-07-30, post-implementation)

This spec's initial draft scoped itself to `apps/denidin-app` only (see
References below) — that scoping was never actually requested or agreed;
it was an unstated assumption. **Both apps in this monorepo have their own,
fully independent `tests/expensive/` tier** (`apps/denidin-app/pytest.ini`
and `apps/morning-mcp-app/pytest.ini` each register the marker separately),
and the same billed/expensive logic applies to both. Applying the same
per-test inspection to `apps/morning-mcp-app/tests/expensive/test_openai_invokes_mcp_e2e.py`
(its only expensive-marked file, 2 tests) found both tests are real,
text-only OpenAI Responses API calls (driving MCP tool invocation over a
real ngrok tunnel) with zero vision/image content — so both move to
`billed`, leaving `apps/morning-mcp-app`'s `expensive` tier at zero tests
(marker/folder infrastructure kept registered for if/when this app ever
adds a genuinely vision-based tool). This feature's implementation now
covers both apps identically.

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

## Resolved Decisions (from clarification, 2026-07-30)

- **Exact split of existing tests — verified against actual OpenAI/vision
  calls in each file (not assumed):**
  - `billed` (text-only, no vision/media calls):
    `test_simple_text_e2e.py`, `test_ai_handler_real_api.py`,
    `test_session_transfer.py`, `test_denidin_morning_mcp_e2e.py`,
    `test_denidin_morning_document_creation_e2e.py` — **contrary to this
    spec's original first-pass guess**, this last file was verified (grep for
    image/pdf/docx/vision/extract) to contain zero media calls: despite its
    name, "document creation" refers to Morning document *types* (invoice,
    receipt, credit note, transaction account) created via text-only WhatsApp
    turns and MCP tool calls, not image/PDF/DOCX extraction. It belongs in
    `billed`, not `expensive`.
  - `expensive` (real vision/image/PDF/DOCX extraction calls):
    `test_media_e2e.py` (5 of 6 tests — `test_e2e_unsupported_audio_file` is
    rejected before any extraction and makes zero OpenAI calls; per the
    clarification decision below, its mismark is explicitly left unfixed by
    this feature), `test_ledger_event_capture_e2e.py` (only its 3
    image-flow tests: `test_given_real_agreement_image_...`,
    `test_given_real_bank_deposit_screenshot_...`,
    `test_given_non_agreement_image_...`).
  - `test_ledger_event_capture_e2e.py` mixes both kinds and must be split at
    the file level (see "Physical Folder Separation" below): its 2 text-flow
    tests (`test_given_clear_fee_agreement_text_...`,
    `test_given_ordinary_chatter_...`) move to a new `billed` file; its 3
    image-flow tests plus their shared fixtures/helpers stay in `expensive`.

- **`billed` and `expensive` are fully independent markers**, not a
  superset/subset relationship. `pytest.ini`'s `addopts` becomes
  `-m "not billed and not expensive"`. Running both tiers requires
  `-m "billed or expensive"`; `-m expensive` alone now only selects real
  vision/media calls, not text-only ones.

- **`billed` tests do NOT require the strict approval discipline that
  `expensive` keeps.** Per explicit user decision: billed (text-only) tests'
  per-run cost is negligible, so they can run freely — no per-run approval
  gate, no one-at-a-time restriction, no "read logs before re-running"
  requirement. This is a real policy loosening (not just a labeling change)
  and is scoped ONLY to the new `billed` tier. `expensive` (real vision/media
  calls) keeps 100% of today's strict rules unchanged: approval every single
  run, one at a time, read `logs/test_logs/` first, never re-run a billed
  [sic — expensive] test that already reached OpenAI without fresh approval.

- **Naming: add, not rename.** `expensive` keeps its narrowed meaning
  (media/vision only); `billed` is the new marker. Existing test files that
  are actually text-only get their `@pytest.mark.expensive` decorators
  changed to `@pytest.mark.billed` (a real change per file, since the split
  moves specific tests between tiers) but no third marker name is
  introduced.

- **Physical folder separation (added scope, not in the original draft):**
  in addition to marker changes, this feature creates `tests/billed/` as a
  new sibling to `tests/expensive/`, and physically moves/splits files so
  each folder holds only tests of its own tier:
  - `tests/billed/`: `test_simple_text_e2e.py`, `test_ai_handler_real_api.py`,
    `test_session_transfer.py`, `test_denidin_morning_mcp_e2e.py` (+ its
    `denidin_mcp_e2e_helpers.py`), `test_denidin_morning_document_creation_e2e.py`,
    and a new `test_ledger_event_capture_billed.py` (extracted text-flow
    tests + duplicated shared fixtures/helpers, matching this codebase's
    existing per-file-self-contained-fixtures convention rather than
    introducing a new shared abstraction for two methods).
  - `tests/expensive/`: `test_media_e2e.py` (unchanged), and
    `test_ledger_event_capture_e2e.py` narrowed to just its 3 image-flow
    tests and their fixtures.
  - `tests/e2e_helpers.py` (shared `create_real_notification`/`get_response`/
    etc.) moves up one level, out of `tests/expensive/`, since it's now
    imported by files in both `tests/billed/` and `tests/expensive/`.
  - `test_e2e_unsupported_audio_file`'s marker mismark (zero real API calls,
    still marked `expensive`) is explicitly left untouched — out of scope for
    this feature per explicit user decision, to keep this change scoped to
    the billed/expensive split.

- **Docs to update accordingly** (not just `pytest.ini`): CLAUDE.md's
  "Expensive test rules" section (split into a `billed` subsection with the
  lighter rules and an unchanged `expensive` subsection), `.github/CONSTITUTION.md`
  §VII, `.github/quick-ref-constitution.md`, `.github/ARCHITECTURE.md`'s test-count
  line, and the two docstring path references in
  `tests/unit/test_ai_handler_ledger_events.py` and
  `tests/integration/test_bot_exception_handling.py` that point at specific
  file paths under `tests/expensive/`.

## References

- `apps/denidin-app/pytest.ini` and `apps/morning-mcp-app/pytest.ini` — each app's own `markers`/`addopts` definitions, extended identically.
- `apps/denidin-app/tests/expensive/` and `apps/morning-mcp-app/tests/expensive/` — the test files needing (re)classification in each app.
- CLAUDE.md's "Expensive test rules (strict)" section and `.github/CONSTITUTION.md` §VII — governed today's single-tier policy; both updated to state explicitly which rules carry over per tier.
- `.github/METHODOLOGY.md` §VI (TDD) — updated to require test-tier classification (unit/integration/billed/expensive) be stated during the EXPLAIN Test Plan step, not just for this feature but as a standing rule.
