# Tasks: Feature 071
Order in bundle: 3rd.
- T071-G0 Gate 0: billed real call confirming PDF `input_file` support/limits/oversize error - BLOCKED on human go-ahead; result into `research.md`.
- T071-A1 Unit tests: PDF request carries one `input_file` part, one model call for any page count; invariant (deposit types -> unknown); stash medium for PDF agreements; oversize pre-check and API-rejection mapping to the friendly message (no call on pre-check).
- T071-A2 Integration test 71-3: oversize PDF through the real media entry point gets the friendly refusal and no model call.
- T071-B1 `PDFExtractor` subclass of `ImageExtractor`; delete per-page code; `requirements.txt` check for PyMuPDF.
- T071-B2 `error_messages.py` message; `build_media_stash_text` PDF medium.
- T071-B3 71-9: replace obsolete per-page tests in `tests/unit/test_pdf_extractor.py` (human sign-off for removal/replacement).
- T071-C Acceptance: add the approved assertions to `test_e2e_hebrew_pdf_from_you` (ledger event after client resolution) and `test_e2e_pdf_multipage_no_caption` (no ledger event, not bank) - run later, expensive, one at a time with approval.
