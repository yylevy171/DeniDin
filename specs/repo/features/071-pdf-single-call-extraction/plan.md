# Implementation Plan: Single-Call PDF Extraction (Feature 071)

**Spec**: `spec.md` · **Scenarios**: `acceptance-scenarios.md` (approved, incl. three added assertions) · **Design approved 2026-10-09**.

## Technical context
`apps/denidin-app/src/handlers/extractors/` (`image_extractor.py`, `pdf_extractor.py`), `media_handler.py`, `capabilities/media_analysis/handler.py`, `constants/error_messages.py`. OpenAI Responses API with `ai_vision_model`. Shared media code (both pipelines).

## Constitution check
No mocking inside integration tests; the oversize test uses no model call. Third-party assumption (PDF input support, limits) must be verified with a real call first (research §1). No env vars, no flag (human decision), old code deleted.

## Design
1. **Gate 0 (before code)**: a small, billed, one-off real call with a fixture PDF to confirm `ai_vision_model` accepts `input_file` and to read real limits/errors for an oversized file. Needs the human's go-ahead. Recorded in `research.md`.
2. `PDFExtractor` becomes a subclass of `ImageExtractor`; the only override is the content part: `{"type": "input_file", "filename": ..., "file_data": "data:application/pdf;base64,..."}` instead of `input_image` (`detail: high`). Prompt, JSON parsing, classification, ledger step, wire logging are inherited.
3. Delete the per-page rasterize loop, aggregation helpers and their imports; drop PyMuPDF from `requirements.txt` only if no other module imports it (checked at implementation).
4. **Invariant** (bugfix-028): after parsing, a PDF's `doc_type` in {bank, bit, paybox, check} is forced to `unknown` (never a deposit).
5. **Oversize**: pre-check on size (limit from Gate 0) and mapping of the API's size/page rejection to a friendly Hebrew message in `error_messages.py`; no model call on the pre-check path; no fallback.
6. `capabilities/media_analysis/handler.py::build_media_stash_text`: PDF stashes as `source_medium="document"` (currently only DOCX does), so a PDF agreement flows through the same gate as image/DOCX agreements.

## Out of scope
Text-layer fast path, per-page fallback, PDF bank slips.

## Tests
Acceptance (approved): 71-1, 71-2 (existing `test_media_e2e.py` tests + new assertions), 71-3 integration (oversize, no model call). Unit: content-part shape, invariant, stash medium, error mapping. 71-9: obsolete `tests/unit/test_pdf_extractor.py` per-page tests replaced with sign-off.
