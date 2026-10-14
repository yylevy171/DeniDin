# Feature 071 - Acceptance scenarios (DRAFT, approved 2026-10-09 by the human operator)

Tier: `expensive` = sends a PDF to the model (own fresh approval per run). Fixtures already exist in `apps/denidin-app/tests/fixtures/media/`; the PDF tests below already exist in `tests/expensive/test_media_e2e.py` and are reused (adding assertions to an approved test needs human sign-off).

| # | Tier | Scenario |
|---|---|---|
| 71-1 | expensive (existing: `test_e2e_hebrew_pdf_from_you`, fixture `רועי שדה הצעת שכט.pdf`) | The admin sends the fee-proposal PDF. One model call reads the whole file. The bot replies with the summary; the extracted text is persisted (both already asserted today). **New assertion:** after client resolution, a fee-agreement event is recorded in the ledger, same as the equivalent image / DOCX agreement tests. |
| 71-2 | expensive (existing: `test_e2e_pdf_multipage_no_caption`, fixture `מודול 4.pdf`) | The admin sends a PDF that is not a fee agreement. The bot summarises it (already asserted today). **New assertions:** nothing is recorded in the ledger, and it is never classified as a bank slip. |
| 71-3 | integration (no model call), new | A PDF over the app-wide 10 MB limit gets the friendly "send a smaller file" reply and no model call is made. (Decided 2026-10-09, option B: the existing 10 MB media limit is the only limit; there is no separate PDF limit.) |

Also existing and in the same file: `test_e2e_pdf_with_caption_user_question` (PDF + caption question) - kept as a regression, unchanged.

## 71-9 (tracking only): existing tests that assert the OLD per-page behaviour
`tests/unit/test_pdf_extractor.py` (every test mocks the per-page `ImageExtractor` and checks per-page aggregation - obsolete once the per-page code is deleted), plus PDF mentions in `test_media_handler.py`, `test_capability_media_analysis.py`, `test_backbone_media_turn.py`, `test_media_manager.py`, `test_whatsapp_handler_media.py`. Each change needs human sign-off.

Note: the existing PDF E2E tests drive the legacy `handle_document_message` entry; at planning, confirm they exercise the Backbone media path (071 is shared media code, 064/066 are Backbone-only).

Removed at approval: the multi-page text-layer test and the separate scanned-PDF test (fixtures already exist; no new PDFs needed).
