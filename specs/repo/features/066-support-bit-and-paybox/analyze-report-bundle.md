# Analyze report - bundle 064 / 066 / 071 / 099 (2026-10-09)

Cross-artifact consistency check (spec <-> plan <-> tasks <-> code <-> tests). Findings and what was done.

| # | Finding | Resolution |
|---|---|---|
| 1 | 071 plan/acceptance said a PDF over a "size/page limit" gets a refusal; the app already rejects any media over 10 MB first, so the 32 MB PDF cap was unreachable. | Human chose option B (2026-10-09): one app-wide 10 MB limit, friendly reply for any oversize file. PDF-specific cap removed; `FileTooLargeError` + `FILE_TOO_LARGE_REFUSAL`; 71-3 updated. |
| 2 | 066 scenarios require checking cheque number and Bit/PayBox "in Morning via get_invoice_details", but that JSON did not expose them. | Added `app_type` and `cheque_number` to the payment object (additive, morning-mcp-app) + unit test. |
| 3 | 069 manifests classify every roster field; the new `check_number` field made all 13 manifests incomplete, and 4 deposit manifests asserted the old shape. | Manifests updated (needs human sign-off, listed in impacted-tests-66-9.md). |
| 4 | 066-C scenarios need Bit / PayBox / cheque images. | Human supplied `bit1.jpeg`, `paybox1.jpeg`, `cheque1.jpeg`. |
| 5 | Webapp frontend still offered `בנק` as an event type. | Removed (backend still reads legacy events until the migration script is applied). |
| 6 | Pre-existing: ledger dedup never matches when a transaction date exists (stored DD/MM/YYYY vs incoming ISO). | NOT fixed (out of scope); reported to the human. |
| 7 | Pre-existing: 3 morning unit failures (`test_tools_document_creation.py`), 1 webapp backend failure (`test_preview_092_migration.py`), 1 mypy error (`src/core/ai_manager.py:142`). | Not touched; confirmed unrelated (fail without this work). |

Open: schema version bump to 3 was approved ("v3") and has its history entry; the 066 migration script exists but has NOT been run against any real data directory (human decision when to apply).
