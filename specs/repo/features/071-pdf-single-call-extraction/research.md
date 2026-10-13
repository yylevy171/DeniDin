# Research: Feature 071
1. **Unverified until Gate 0**: OpenAI Responses API `input_file` for PDFs with `ai_vision_model`; documented ~100 pages / 32 MB limits; behaviour on Hebrew and scanned PDFs; exact error for oversize. Rule: CONSTITUTION "no unverified third-party assumptions". Result to be recorded here.
2. **Code facts (read)**: `ImageExtractor._vision_extract` builds the Responses request with an `input_image` part; its wire logging redacts the media. `PDFExtractor` today rasterizes with PyMuPDF and calls `ImageExtractor` per page, discarding per-page `ledger_events` (the reason PDF agreements never reached the ledger). `build_media_stash_text` already routes `doc_type == "agreement"` through `build_ledger_stash_text`, but marks every non-DOCX source as image.
3. **Decision**: subclass instead of a second implementation - one prompt/contract (human-approved).

## Gate 0 result (2026-10-09)
One real call through `PDFExtractor` with the `input_file` data-URL part, model `gpt-5.6-luna`, fixture `contract_peter_adam.pdf`: accepted, Hebrew text extracted correctly. Size limit left at 32 MB (not probed, per human). PyMuPDF removed from requirements.txt and mypy.ini.
