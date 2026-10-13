# User Stories: Single-Call PDF Extraction (Feature 071)

## Story 1 - Fee-agreement PDF reaches the ledger (P1)
**Given** the admin sends a fee-agreement PDF **When** the bot reads it **Then** the whole file is read in one model call, the admin gets the usual summary, and after client resolution a fee-agreement event is recorded in the ledger as for the same agreement sent as an image or DOCX.

## Story 2 - Other PDFs are only summarised (P1)
**Given** the admin sends a PDF that is not a fee agreement **When** the bot reads it **Then** it is summarised, nothing is recorded in the ledger, and it is never treated as a bank slip.

## Story 3 - Oversized PDF (P2)
**Given** a PDF beyond the model's limits **When** the admin sends it **Then** the bot asks politely for a smaller file and makes no model call.

## Acceptance scenarios (APPROVED 2026-10-09 - see `acceptance-scenarios.md`)
71-1 (expensive; existing `test_e2e_hebrew_pdf_from_you` + ledger assertion) · 71-2 (expensive; existing `test_e2e_pdf_multipage_no_caption` + no-ledger / not-bank assertions) · 71-3 (integration; oversized refusal) · existing caption-question test kept · 71-9 tracking list of obsolete per-page tests. Assertion additions approved 2026-10-09.
