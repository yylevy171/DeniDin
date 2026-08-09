"""
Image Text Extractor (Feature 003 Phase 3.1 + Phase 4 Enhancement)
Extract text from images AND analyze documents using GPT-4o Vision API.

Phase 4 Enhancement: Single AI call returns text + document analysis.

CHK Requirements:
- CHK006: Hebrew text extraction required
- CHK007: Graceful degradation on extraction failures
- CHK008: Mixed Hebrew/English support
- CHK010: Layout/structure preservation
- CHK027: Specific prompt (not just example)
- CHK078: Empty document handling
"""
from typing import cast, Dict
from pathlib import Path
import json
import logging
import re
from src.models.media import Media
from src.handlers.extractors.base import MediaExtractor

logger = logging.getLogger(__name__)

# bugfix-028: the only three document classifications the vision step may return.
# `bank` and `agreement` are entirely different documents in both appearance and
# content, so the realistic worst case is a genuine one being read as UNKNOWN -
# never one being confidently mistaken for the other. UNKNOWN is a safe outcome
# precisely because it routes to asking the user, not to guessing.
DOC_TYPE_BANK = "bank"
DOC_TYPE_AGREEMENT = "agreement"
DOC_TYPE_UNKNOWN = "unknown"
_VALID_DOC_TYPES = {DOC_TYPE_BANK, DOC_TYPE_AGREEMENT, DOC_TYPE_UNKNOWN}

# Required per type - a document classified as this type but missing any of these
# is incomplete, and the caller must ASK rather than proceed on a guess.
REQUIRED_FIELDS = {
    # Three NUMBERS identify the account (user, 2026-08-09): bank number, branch,
    # account. Screenshots usually show the bank NAME as well - that is optional
    # extra, never a substitute for its number.
    DOC_TYPE_BANK: ("payer_name", "amount", "txn_date", "bank_number", "bank_branch", "bank_account"),
    DOC_TYPE_AGREEMENT: ("client_name", "components"),
    DOC_TYPE_UNKNOWN: (),
}

_JSON_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


def _parse_vision_json(raw: str) -> Dict:
    """Parse the vision call's structured response.

    The extractor extracts and classifies; it does NOT author anything the user
    reads. The reply is composed later from the extracted text plus whatever
    needs adding (a question, when the document is unknown or incomplete).

    Defensive by design: any failure to parse, or any doc_type outside the three
    permitted values, degrades to UNKNOWN - which routes to asking the user
    rather than to a guess.
    """
    empty = {
        "doc_type": DOC_TYPE_UNKNOWN,
        "extracted_text": "",
        "fields": {},
        "missing_required_fields": [],
    }
    if not raw or not raw.strip():
        return empty

    try:
        payload = json.loads(_JSON_FENCE.sub("", raw.strip()))
    except (json.JSONDecodeError, TypeError):
        logger.warning(
            "[ImageExtractor] Vision response was not valid JSON - classifying as "
            "UNKNOWN so the user is asked rather than guessed at. Raw: %r", raw[:300]
        )
        return empty
    if not isinstance(payload, dict):
        return empty

    doc_type = payload.get("doc_type")
    if doc_type not in _VALID_DOC_TYPES:
        logger.warning(
            "[ImageExtractor] Vision returned unrecognized doc_type %r - treating as UNKNOWN",
            doc_type,
        )
        doc_type = DOC_TYPE_UNKNOWN

    fields = payload.get("fields")
    fields = fields if isinstance(fields, dict) else {}

    # Recompute rather than trust: a field the model listed as present but left
    # empty is missing, whatever its own missing_required_fields said.
    declared = payload.get("missing_required_fields")
    declared = [str(f) for f in declared] if isinstance(declared, list) else []
    actually_missing = [f for f in REQUIRED_FIELDS[doc_type] if not fields.get(f)]
    missing = sorted(set(declared) | set(actually_missing))

    return {
        "doc_type": doc_type,
        "extracted_text": str(payload.get("extracted_text") or ""),
        "fields": fields,
        "missing_required_fields": missing,
    }


class ImageExtractor(MediaExtractor):
    """
    Extract text and analyze documents from images using GPT-4o Vision.
    
    Phase 4: Enhanced to return text + document analysis in single AI call.
    """
    
    def __init__(self, denidin_context):
        """
        Initialize with DeniDin global context.
        
        Args:
            denidin_context: DeniDin instance with ai_handler and config
        """
        super().__init__(denidin_context)
        self.ai_handler = denidin_context.ai_handler
        self.vision_model = self.config.ai_vision_model
    
    def analyze_media(self, media: Media, caption: str = "") -> Dict:
        """
        Analyze image using GPT-4o Vision (Phase 4 enhancement).
        
        Single AI call returns AI-generated analysis with:
        - Document summary (סיכום:)
        - Key points (נקודות חשובות:)
        - Document type and confidence
        - Full response formatted per prompt requirements
        
        CHK006-011: Hebrew text extraction with layout preservation.
        
        Args:
            media: Media object containing image data in memory
            caption: User's message/question sent with the image (optional)
            
        Returns:
            {
                "raw_response": str,  # Full unmodified AI response
                "extraction_quality": str,  # "high", "medium", "low", "failed"
                "warnings": List[str],
                "model_used": str,  # e.g. "gpt-4o"
                "ledger_events": List[Dict]  # Ledger Event Recognition captures, if any
                    # (2026-07-30: plural - a single document can genuinely warrant more
                    # than one, e.g. a multi-stage/conditional fee agreement)
            }
        """
        try:
            # Load prompt template from external file
            prompt_path = Path(__file__).parent.parent.parent.parent / "prompts" / "image_analysis.txt"
            prompt_template = prompt_path.read_text(encoding='utf-8')

            # CHK027: Enhanced prompt for document analysis
            # Include user's caption/question for context (only if provided)
            user_context = f"\n\nUser's question/message: {caption}" if caption else ""
            addressing_note = " addressing the user's question" if caption else ""
            focusing_note = ", focusing on what the user asked about" if caption else ""

            # Format the prompt with context
            prompt = prompt_template.format(
                user_context=user_context,
                addressing_note=addressing_note,
                focusing_note=focusing_note
            )

            logger.info(f"[ImageExtractor.analyze_media] Exact prompt being sent ({len(prompt)} chars):")
            logger.info(f"[ImageExtractor.analyze_media] {prompt}")

            # Call Vision API with in-memory media (constitution prepended in _vision_extract).
            # Pure extraction only - no tool attached (Feature 024's ledger classification
            # happens as a separate call below, see _classify_ledger_event).
            response_text = self._vision_extract(media, prompt)

            logger.info(f"[ImageExtractor.extract] Raw AI response ({len(response_text)} chars):")
            logger.info(f"[ImageExtractor.extract] {response_text}")

            # bugfix-028: the vision call now returns structured JSON, so the
            # document TYPE is decided where the evidence actually is - looking at
            # the image - instead of being re-inferred downstream from prose by a
            # model that never saw it. A real run (2026-08-09) had the vision step
            # read a bank confirmation perfectly and the text-only classifier then
            # decline to capture it, because the prose it was handed carried the
            # extractor's own "ביטחון: בינוני" hedge about a blurry name. Same
            # image, opposite outcomes within an hour.
            parsed = _parse_vision_json(response_text)
            # The extractor authors nothing the user reads - it returns the text it
            # read off the document, and the reply is composed downstream from that
            # plus anything worth adding (see MediaHandler). Falls back to the raw
            # output if the response wasn't parseable, so a format slip can never
            # leave the user with nothing (bugfix-028 B5).
            extracted_text = parsed["extracted_text"] or response_text

            # Ledger Event Recognition (runtime_constitution.md, Feature 024): a separate,
            # internal text-only classification call over the extracted text - NOT attached
            # to the vision call above. Confirmed empirically (real E2E run, 2026-07-28)
            # that attaching the tool directly to the vision call makes it one-action-per-
            # turn (gpt-4o and gpt-4o-mini both produced ZERO extraction text whenever they
            # called the tool), which broke the user-facing document summary. This call's
            # own text is never shown to the user - only whether it called the tool matters.
            # Plural (2026-07-30): a single document can genuinely warrant more than one
            # capture - see capture_ledger_events_from_text's docstring for the real bug
            # this replaced (silently dropping every component after the first).
            ledger_events = self.ai_handler.capture_ledger_events_from_text(extracted_text)

            return {
                # The text read off the document - NOT a message to the user.
                # MediaHandler composes what the user sees from this.
                "raw_response": extracted_text,
                "extraction_quality": "high",
                "warnings": [],
                "model_used": self.vision_model,
                "ledger_events": ledger_events,
                # bugfix-028: structured classification for downstream decisions.
                "doc_type": parsed["doc_type"],
                "fields": parsed["fields"],
                "missing_required_fields": parsed["missing_required_fields"],
                "extracted_text": parsed["extracted_text"],
            }

        except Exception as e:
            # CHK007: Fail gracefully
            return {
                "raw_response": "",
                "extraction_quality": "failed",
                "warnings": [f"Analysis failed: {str(e)}"],
                "model_used": self.vision_model,
                "ledger_events": [],
                "doc_type": DOC_TYPE_UNKNOWN,
                "fields": {},
                "missing_required_fields": [],
                "extracted_text": "",
            }

    def _vision_extract(self, media: Media, prompt: str) -> str:
        """
        Extract text from image using GPT-4o Vision with constitution context.

        Pure extraction only - no tool attached (see analyze_media for why Ledger
        Event Recognition happens as a separate call instead of here).

        Args:
            media: Media object containing image data
            prompt: Extraction prompt (will be prepended with constitution)

        Returns:
            The vision model's extracted text response.
        """
        # Load constitution for context
        constitution = self.ai_handler._load_constitution()

        # Prepend constitution to user prompt (NO system message!)
        full_prompt = f"{constitution}\n\n{prompt}" if constitution else prompt

        logger.debug(f"[ImageExtractor._vision_extract] Full prompt length: {len(full_prompt)} chars")
        logger.debug(f"[ImageExtractor._vision_extract] Constitution loaded: {bool(constitution)}")
        logger.debug(f"[ImageExtractor._vision_extract] Constitution preview: {constitution[:200] if constitution else 'NONE'}")

        # Get the data URL
        data_url = media.get_data_url()
        logger.info(f"[ImageExtractor._vision_extract] Media data URL length: {len(data_url)} chars")
        logger.info(f"[ImageExtractor._vision_extract] Media data URL preview: {data_url[:100]}...")
        logger.info(f"[ImageExtractor._vision_extract] Media file size: {media.size} bytes, MIME type: {media.mime_type}")

        # Call OpenAI Vision via the Responses API with in-memory data URL.
        # detail="high" (2026-07-30 finding): omitting this left the API defaulting to
        # "auto", which can downsample a dense-text document image more aggressively than
        # the content needs - a real, clean, high-resolution fee-agreement screenshot came
        # back with garbled text and a dropped fee tier. Forcing "high" processes the image
        # at full resolution (more tiles), matching what document/text-heavy images need.
        logger.info(f"[ImageExtractor._vision_extract] Sending request to OpenAI Vision API")
        response = self.ai_handler.client.responses.create(
            model=self.vision_model,
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": full_prompt},
                        {"type": "input_image", "image_url": data_url, "detail": "high"}
                    ]
                }
            ],
            max_output_tokens=self.config.ai_reply_max_tokens
        )

        raw_response = cast(str, response.output_text)
        logger.info(f"[ImageExtractor._vision_extract] Raw OpenAI response ({len(raw_response)} chars):")
        logger.info(f"[ImageExtractor._vision_extract] {raw_response}")

        return raw_response
