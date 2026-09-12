# Feature Spec: Single-Call PDF Extraction

**Feature ID**: 071-pdf-single-call-extraction
**Priority**: TBD
**Status**: Draft (definition-only — no `speckit.clarify`/`plan`/`user-stories`/`tasks` yet)
**Created**: 2026-08-31

---

## Origin

Split out of **Feature 069** (`specs/in-progress/069-mandatory-client-resolution-before-ledger-event/`)
on 2026-08-31, user direction:

> "can we extract pdf in one go instead of by pages?" … "New spec 71 for pdf single
> extraction. Remove from 69 scope and continue 69 with images and docx"

Feature 069 brings **image** (`בנק` deposit slips, photographed `הסכם` agreements) and
**DOCX** fee agreements into the mandatory-client-resolution-before-ledger-event gate. PDF
fee agreements were deliberately left out of 069 because the fix PDF really needs is a
different, larger change to how `PDFExtractor` works — captured here.

## Problem Statement

`src/handlers/extractors/pdf_extractor.py`'s `PDFExtractor.analyze_media` processes a PDF
**page by page**:

1. `page.get_pixmap()` rasterizes each page to a PNG.
2. Each page PNG is handed to `self.image_extractor.analyze_media(page_media, ...)` — a
   full vision call per page.
3. The per-page results are aggregated (`pdf_extractor.py:140-150`):
   `raw_response` / `extracted_text` / `extraction_quality` / `warnings` / `doc_type` /
   `fields` are combined; **`page_result["ledger_events"]` is discarded** — so a PDF fee
   agreement is recognized per-page by `capture_ledger_events_from_text` (inside
   `ImageExtractor`) but the recognition is thrown away and no `LedgerEvent` is ever
   persisted from a PDF. (`MediaHandler` Step 10 no-ops because `analysis_result` has no
   `ledger_events` key.)

Consequences:

- **Cost / latency**: an N-page PDF = N sequential vision calls, even for a text-layer PDF
  where no vision is needed at all.
- **Fragmentation**: a fee agreement whose components span a page boundary is analyzed in
  disconnected pieces; the aggregation is lossy.
- **No ledger capture from PDF**: the one place per-page recognition *is* run, its result
  is dropped — so PDF fee agreements silently never reach the ledger (the exact hole
  Feature 069 closes for images and DOCX, still open for PDF after 069 ships).

## Proposed Direction (for `speckit.clarify` / `plan`)

Replace the per-page rasterize→vision loop with a **single whole-document extraction**:

- One OpenAI Responses API call passing the whole PDF as an `input_file` (base64), within
  the API's document limits (~100 pages / 32 MB) — the model reads the entire document in
  one pass, no per-page PNG rasterization.
- Optional fast-path: for a PDF that already has a real text layer, `page.get_text()`
  (PyMuPDF) to pull text directly and skip the model call for extraction, using the model
  only for analysis/recognition on the assembled text.
- Produce the **same extractor contract** every other extractor returns
  (`extracted_text`, `document_analysis`, `extraction_quality`, `warnings`, `model_used`)
  **plus `ledger_events`** — so a PDF fee agreement flows through `MediaHandler` Step 10
  and (once Feature 069 has landed) through `AIHandler.process_media_ledger_capture`, i.e.
  the same client-resolution-before-capture gate images and DOCX get in 069.
- `bugfix-028` invariant preserved: PDF (like DOCX) is **always** `הסכם` or unknown —
  never `בנק`.

## Scope Notes

- This affects **all** PDF handling — document summaries for any shared PDF, not only fee
  agreements. The extractor rewrite is the core; ledger routing is a downstream beneficiary.
- Depends on / follows **Feature 069**: 069 builds `process_media_ledger_capture` +
  `build_ledger_stash_text` (source-medium-aware) and the `MediaHandler` routing; once
  `PDFExtractor` populates `ledger_events`, PDF fee agreements route through that existing
  machinery with no further 069-side work. If 071 lands first, the routing hookup moves here.
- Feature 069's US8 (DOCX `הסכם` → resolve → capture) is the template for the PDF
  acceptance scenario this feature should add.

## Open Questions (for `speckit.clarify`)

- Single `input_file` call vs. text-layer fast-path vs. both (detect and branch)?
- Page/size ceiling behavior — what happens for a PDF beyond the API's `input_file`
  limits? Fall back to the current per-page loop, or refuse with a friendly message?
- Does the single-pass call reuse `ImageExtractor`'s prompt/constitution-prepend approach,
  or does PDF get its own prompt?
- Acceptance tier: a single whole-PDF model call is still a real OpenAI call — `billed`
  if the fast-path keeps it text-only, `expensive` if it's a vision/document call. Decide
  per the final mechanism.

---

## References

- Feature 069 — `specs/in-progress/069-mandatory-client-resolution-before-ledger-event/`
  (images + DOCX; PDF explicitly deferred here)
- `src/handlers/extractors/pdf_extractor.py`, `image_extractor.py`
- `bugfix-028` — PDF/DOCX are always `הסכם` or unknown, never `בנק`
