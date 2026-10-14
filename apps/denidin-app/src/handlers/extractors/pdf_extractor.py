"""
PDF extractor (Feature 071): the whole PDF is read in ONE model call.

Replaces the per-page rasterize -> vision loop (Feature 003 / Phase 4) with
OpenAI's native PDF input: the file goes to the vision model as a single
`input_file` content part. Everything else - the prompt, the structured JSON
parsing, the classification, the ledger step, the wire logging and the result
contract - is inherited unchanged from ImageExtractor; only the content part
and the PDF-specific rules below differ.

Rules specific to a PDF:
- A PDF is always a fee agreement (`agreement`) or unknown, never a deposit of
  any kind (bugfix-028; Feature 066 widens "bank" to bank/bit/paybox/check).
- The app-wide 10 MB media limit applies (the user gets a friendly reply); there is no
  per-page fallback.
"""
import logging
from typing import Dict, Optional

from src.handlers.extractors.image_extractor import (
    DEPOSIT_DOC_TYPES,
    DOC_TYPE_UNKNOWN,
    ImageExtractor,
)
from src.models.media import Media

logger = logging.getLogger(__name__)


class PDFExtractor(ImageExtractor):
    """Extract text and analyze a PDF with a single call to the vision model."""

    def _media_content_part(self, media: Media) -> Dict:
        return {
            "type": "input_file",
            "filename": media.filename or "document.pdf",
            "file_data": media.get_data_url(),
        }

    def analyze_media(self, media: Media, caption: str = "", today_timestamp: Optional[int] = None) -> Dict:
        result = super().analyze_media(media, caption=caption, today_timestamp=today_timestamp)
        if result.get("doc_type") in DEPOSIT_DOC_TYPES:
            logger.warning("[PDFExtractor] model classified a PDF as %r - a PDF is never a deposit; using %r",
                           result["doc_type"], DOC_TYPE_UNKNOWN)
            result["doc_type"] = DOC_TYPE_UNKNOWN
            result["fields"] = {}
            result["missing_required_fields"] = []
            result["ledger_events"] = []
        return result
