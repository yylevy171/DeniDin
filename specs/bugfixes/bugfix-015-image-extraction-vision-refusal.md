# Bugfix Spec: Vision Model Refuses to Extract the `test_e2e_image_no_caption` Fixture Image

## Bug ID
bugfix-015-image-extraction-vision-refusal

## Title
`ImageExtractor` gets a content-policy refusal from the vision model ("אני לא יכול לעזור עם זה" / "I can't help with that") on an image that was previously extracted successfully, with no code or fixture change to explain the regression

## Status
Open - root cause not yet confirmed

## Date Opened
2026-07-23

## Reported By
yaronlev171 (found while running the full `tests/expensive/` suite from a fresh dev-env rebuild)

## Affected Area
- `apps/denidin-app/src/handlers/extractors/image_extractor.py` (`ImageExtractor._vision_extract`)
- `apps/denidin-app/tests/expensive/test_media_e2e.py::TestWhatsAppE2E::test_e2e_image_no_caption`
- Possibly: `apps/denidin-app/handlers/ai_handler.py` memory-recall path, if recalled ChromaDB
  memory context is being injected into the vision extraction prompt (under
  investigation — see Root Cause Analysis)

## Description
`test_e2e_image_no_caption` sends `tests/fixtures/media/WhatsApp Image
2025-11-18 at 21.51.25.jpeg` (a legitimate screenshot of a lawyer's
fee-demand/collection email, mentioning a bank account request and legal
proceedings language) through the real image extraction pipeline
(`ImageExtractor` → OpenAI vision API, model configured as `gpt-4o` in
`config.test.json`). The model refused twice in a row, on two separate
billed runs in the same session:

- Run 1 (before a config/dev-env rebuild unrelated to this test):
  `אני מצטער, אבל אני לא יכול לעזור בזה.` ("I'm sorry, but I can't help with
  that.")
- Run 2 (after rebuilding `denidin-app-dev` to pick up unrelated
  `ai_model`/`ai_vision_model` config changes — `ai_vision_model` was
  `gpt-4o` in both runs, unchanged):
  `אני לא יכול לעזור עם זה.` ("I can't help with that.")

Per the user (yaronlev171): **this test passed before multiple coders
(parallel dev clones) started working against this repo** — i.e. this is a
regression introduced sometime around the 2026-07-23 multi-clone lock
changes, not a pre-existing flaky test.

## Root Cause Analysis (in progress)
Not yet confirmed. Leading hypothesis, not yet verified:

The 2026-07-23 multi-clone changes (`feature/multi-clone-dev-lock`, merged
as PR #122) made `dev`'s session/memory data (`apps/denidin-app/dev_data`,
which backs both `SessionManager`'s JSON store and `MemoryManager`'s
ChromaDB collections) a **singleton shared across every clone on the
machine** via each clone's `.env.local` (`DENIDIN_DEV_DATA_DIR` all
resolving to the same root-clone path) — see CLAUDE.md's "dev/prod data is
also a singleton across clones" section. Before this change, each
coder/clone likely had its own isolated `dev_data`.

If `AIHandler`'s memory-recall step (ChromaDB semantic search,
`enable_memory_system`) also runs for the image-extraction/document-analysis
path — not just plain chat turns — and now recalls memories seeded by a
*different* coder's concurrent/prior testing (Ruth's session, or another
coder's), that recalled content gets appended into the same prompt sent to
the vision model. Unrelated or edge-case content injected this way could be
enough to tip the model into a refusal on a borderline-sensitive image
(the fixture already contains legal-threat-adjacent language — "אם ינוהל
הליך..." / "if proceedings are conducted...") that it previously extracted
without issue when the prompt was "clean."

This needs to be confirmed or ruled out by:
1. Capturing the exact `instructions`/prompt sent to the vision API on a
   failing run (already partially visible in `logs/test_logs/` — the full
   constitution text plus recalled-memory block is visible in the captured
   debug log for this test) and checking whether recalled-memory content is
   present and unusual.
2. Checking whether `test_e2e_image_no_caption` and other coders'
   concurrent/recent dev-session activity share the same `data_root` (yes,
   per `.env.local` — needs runtime confirmation this actually applies to
   the *test* run, which uses `config.test.json`'s own `test_data/` root,
   not `dev_data/` — **if `tests/` runs are fully isolated from `dev_data/`
   via `config.test.json`, this hypothesis is likely wrong** and the cause
   is elsewhere, e.g. non-deterministic model sampling on borderline
   content, independent of any multi-clone change).
3. If (2) rules out shared memory, re-check whether anything else changed
   in the same window (OpenAI model behavior itself is not pinned/versioned
   here — `gpt-4o` responses can drift over time without any local change).

## Steps to Reproduce
1. Ensure `denidin-app-dev`'s `ai_vision_model` config is `gpt-4o` (already
   the case).
2. Run (billed, requires fresh explicit approval per CLAUDE.md):
   ```
   python3 -m pytest tests/expensive/test_media_e2e.py::TestWhatsAppE2E::test_e2e_image_no_caption -v -m expensive
   ```
3. Observe: the vision model returns a short Hebrew refusal instead of the
   expected document-analysis extraction; the test's content assertions
   fail.

## Expected Behavior
The vision model returns a real extraction (names/dates/amounts/summary per
`ImageExtractor`'s contract) for this fixture, as it reportedly did before
the multi-clone lock changes landed.

## Impact
- One expensive E2E test (`test_e2e_image_no_caption`) is currently failing,
  blocking a clean full-suite run.
- If the root cause is prompt contamination from another clone's shared
  memory data (still unconfirmed), this would be a live production-shaped
  risk for real users too, since `dev`'s memory store is now genuinely
  shared state across concurrent testers — not just a test-fixture problem.

## Acceptance Criteria
- [ ] Confirm whether `tests/expensive/` runs read `config.test.json`'s own
      isolated `test_data/` root, or somehow reach `dev_data/` (should be
      the former, given 019-env-separation decoupled test data from dev
      data — but this needs re-verification given the new multi-clone
      singleton behavior).
- [ ] Capture and inspect the exact prompt sent to the vision model on a
      failing run for any unexpected/unrelated injected content.
- [ ] Identify actual root cause (shared-memory contamination vs. model
      non-determinism vs. something else).
- [ ] Apply a minimal fix once root cause is confirmed (e.g. exclude
      memory-recall from the image-extraction prompt path if it's present
      there and shouldn't be, or determine this is inherent model
      non-determinism and close as `not_reproducible` instead).
- [ ] Test passes after the fix (single fresh explicit-approval run).
- [ ] No regression in the rest of `test_media_e2e.py` (already re-verified
      passing on the same dev-env rebuild: docx, hebrew_pdf, pdf_with_caption,
      unsupported_audio, pdf_multipage — all green both before and after the
      config/rebuild that triggered this investigation).

## References
- `.github/METHODOLOGY.md` §VII (Bug-Driven Development)
- `CLAUDE.md` "Multi-clone lock (2026-07-23)" and "dev/prod data is also a
  singleton across clones (2026-07-23)" sections
- `apps/denidin-app/tests/fixtures/media/WhatsApp Image 2025-11-18 at
  21.51.25.jpeg`
- `apps/denidin-app/tests/expensive/test_media_e2e.py`
- `apps/denidin-app/src/handlers/extractors/image_extractor.py`
- Related, separately-observed failure in the same test session (NOT part of
  this bug, tracked here only for context): `test_denidin_morning_mcp_e2e.py
  ::test_godfather_marks_invoice_paid_via_whatsapp` failed with
  `list_invoices` finding zero results for a client name from an invoice
  that `create_invoice` had just successfully seeded moments earlier in the
  same test — looks like Morning sandbox write/read eventual-consistency
  lag, not the same root cause as this bug.

## Cost/Approval Note
Verifying this bug (and any fix) requires running a real, billed OpenAI
vision API call via `tests/expensive/test_media_e2e.py`. Per CLAUDE.md
§Expensive-test-rules: explicit human approval is required before every
single run, one test at a time, never a batch. Two billed runs have already
confirmed the failure is reproducible (not a one-off fluke); do not re-run
again without fresh approval.
