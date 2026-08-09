"""
MediaHandler - Orchestrates complete media processing workflow.

Phase 5: Media Handler Orchestration
Coordinates: Download → Validate → Extract → Format summary → Return response

Since extractors (Phase 4) already return document_analysis, MediaHandler
formats the extractor's analysis into user-friendly summaries.
"""

from typing import Dict, Optional
from pathlib import Path
from datetime import datetime, timezone

from src.models.media import Media
from src.models.media_attachment import MediaAttachment
from src.handlers.extractors.image_extractor import ImageExtractor
from src.handlers.extractors.pdf_extractor import PDFExtractor
from src.handlers.extractors.docx_extractor import DOCXExtractor
from src.managers.media_file_manager import MediaFileManager
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MediaHandler:
    """
    Orchestrates complete media processing workflow.
    
    Workflow:
    1. Validate file size
    2. Download file to memory
    3. Validate format
    4. Create Media object (in-memory)
    5. Extract text + document analysis (extractors work with Media objects)
    6. Save file to storage (archival)
    7. Save raw text to storage
    8. Format summary from document_analysis
    9. Return MediaAttachment + summary
    
    Design: Extractors process in-memory Media objects, not file paths.
    Files are saved AFTER extraction for archival/audit purposes.
    """
    
    def __init__(self, denidin_context):
        """
        Initialize MediaHandler with DeniDin context.
        
        Args:
            denidin_context: Global DeniDin context with config, AI handler, etc.
        """
        self.denidin = denidin_context
        self.config = denidin_context.config
        # bugfix-017: media messages were never linked to the session at all
        # (spec 003's REQ-INT-001), reusing the same SessionManager the text
        # path (AIHandler._finalize_response) already stores through.
        self.session_manager = denidin_context.ai_handler.session_manager
        # Feature 033: same LedgerEventManager instance AIHandler uses for the text
        # path - single source of truth, no risk of the two paths diverging.
        self.ledger_event_manager = denidin_context.ai_handler.ledger_event_manager

        # Initialize components
        self.media_file_manager = MediaFileManager(denidin_context)
        self.image_extractor = ImageExtractor(denidin_context)
        self.pdf_extractor = PDFExtractor(denidin_context)
        self.docx_extractor = DOCXExtractor(denidin_context)
    
    def process_media_message(
        self,
        file_url: str,
        filename: str,
        mime_type: str,
        file_size: int,
        sender_phone: str,
        chat_id: str,
        caption: str = "",
        timestamp: Optional[int] = None,
        message_id: Optional[str] = None,
        sender_display_name: Optional[str] = None
    ) -> Dict:
        """
        Process media message through complete workflow.

        Args:
            file_url: Green API download URL
            filename: Original filename
            mime_type: MIME type string
            file_size: File size in bytes
            sender_phone: WhatsApp sender JID, straight from Green API's
                senderData.sender (e.g. "972501234567@c.us") - always carries the
                full JID suffix, same convention as Session.whatsapp_chat (verified
                by reading the real caller, WhatsAppHandler.handle_media_message;
                an earlier version of this docstring showed a bare-digits example,
                which never matched actual runtime behavior)
            chat_id: WhatsApp chat ID (bugfix-017: needed to link this turn to a
                session, same as the text path - group chats differ from sender_phone)
            caption: User's message text with file (optional)
            timestamp: Real Green API notification timestamp (Feature 024) - the
                constitution's "hard pointer" for any ledger event captured from this
                message. Falls back to processing time only if genuinely absent,
                same as WhatsAppMessage.from_webhook's own fallback.
            message_id: Real Green API notification message id (Feature 033) - the
                source-message pointer for any ledger event captured from this
                message (LedgerEvent.message_id).
            sender_display_name: Resolved human-readable sender name (Feature 039,
                WhatsAppMessage.sender_display_name) - used only for the persisted
                Message.sender/recipient values in _store_media_turn, never for
                filenames or LedgerEvent.sender (both keep using sender_phone, the
                raw JID, unchanged). Falls back to sender_phone if not given.

        Returns:
            {
                "success": bool,
                "summary": str,              # User-facing summary
                "media_attachment": MediaAttachment,
                "error_message": Optional[str]
            }
        """
        try:
            # Step 1: Download file first (CHK048: 1 retry max)
            # Note: Green API doesn't provide file_size in webhook, so we download first
            content, success = self.media_file_manager.download_file(file_url)
            if not success:
                return self._error_response(
                    "Unable to download this file. Please try sending it again."
                )
            
            # Step 2: Validate file size from downloaded content (CHK001-002, CHK075)
            actual_file_size = len(content)
            self.media_file_manager.validate_file_size(actual_file_size)
            
            # Step 3: Validate format and determine media type (CHK039-041)
            media_type = self.media_file_manager.validate_format(filename, mime_type)
            
            # Step 4: Create Media object for in-memory processing
            media = Media(data=content, mime_type=mime_type, filename=filename)
            
            # Step 5: Extract text + document analysis (Phase 4 extractors)
            # Analyzers work with in-memory Media objects, not file paths
            # Pass caption to provide user context for analysis
            analysis_result = self._extract_text(media_type, media, caption)
            
            # Step 6: Create storage folder (CHK019: UTC timestamps)
            storage_folder = self.media_file_manager.create_storage_path()
            
            # Step 7: Save file with DD-{sender_phone}-{uuid}.{ext} naming
            # File saved AFTER analysis for archival purposes
            file_path = self.media_file_manager.save_file(
                content, storage_folder, filename, sender_phone
            )
            
            # Step 8: Compose what the user actually reads, from the extractor's
            # extracted text plus anything worth adding.
            # bugfix-028: the extractor no longer authors this - it extracts and
            # classifies, and nothing more. What gets added here is the QUESTION,
            # when there is one: a document we couldn't classify, or a bank
            # confirmation missing details we need, is something to ask about
            # rather than to proceed on silently. "When it's not clear - ASK."
            summary = self._compose_user_message(analysis_result)
            
            # Verify we got a summary from the AI
            if not summary:
                return self._error_response(
                    "Unable to analyze this file. "
                    "The AI did not return a summary."
                )
            
            # Step 9: Create MediaAttachment model
            attachment = MediaAttachment(
                media_type=media_type,
                file_url=file_url,
                file_path=str(file_path),
                mime_type=mime_type,
                file_size=file_size,
                page_count=analysis_result.get("page_count"),
                caption=caption
            )

            # Step 10: Ledger Event Recognition (runtime_constitution.md) - the image
            # path can capture a fee-agreement/bank-deposit event the same way the
            # text path does. Feature 033: persisted via the same LedgerEventManager
            # as the text path (never SessionManager), and done BEFORE _store_media_turn
            # (Step 11 below) so the resulting event_id(s) can be threaded into the
            # stored message's ledger_event_ids at creation time, matching the text
            # path's ordering (AIHandler._finalize_response) instead of needing a
            # separate update-after-the-fact write.
            # message_timestamp uses the real notification timestamp (the constitution's
            # "hard pointer") - NOT processing time, which was a real bug: falling back
            # to datetime.now() here meant a captured event's timestamp reflected when
            # the vision/classification calls happened to finish, not when the user
            # actually sent the image (found 2026-07-28 while strengthening this
            # feature's E2E persistence assertions).
            # Plural (2026-07-30): a single document image can genuinely warrant
            # multiple components (e.g. a multi-stage/conditional fee agreement).
            # ledger_events is normally 0 or 1 calls (each call's own `components`
            # array now carries all of one agreement's components - REQ-DATA-004's
            # redesign, see LedgerEventManager.add_ledger_events_from_call, which owns
            # the flatten + batch-agreement_id + persist-each-component logic); this
            # loop just handles the now-rare case of multiple SEPARATE calls.
            ledger_event_ids = []
            ledger_events = analysis_result.get("ledger_events", [])
            if ledger_events:
                try:
                    if timestamp is not None:
                        event_timestamp = timestamp
                    else:
                        event_timestamp = int(datetime.now(timezone.utc).timestamp())
                    session = self.session_manager.get_session(chat_id)

                    for call_arguments in ledger_events:
                        new_event_ids = self.ledger_event_manager.add_ledger_events_from_call(
                            session_id=session.session_id,
                            whatsapp_chat=chat_id,
                            call_arguments=call_arguments,
                            message_id=message_id,
                            message_timestamp=event_timestamp,
                            sender=sender_phone,
                        )
                        ledger_event_ids.extend(new_event_ids)
                except Exception as e:
                    logger.error(f"Failed to persist ledger event(s) for media message: {e}", exc_info=True)

            # Step 11 (bugfix-017): link this turn to the session, mirroring
            # AIHandler._finalize_response's user+assistant storage for text turns -
            # media messages must not be invisible to conversation history/memory
            # transfer just because they went through a different pipeline.
            # bugfix-009 (reopened 2026-07-30): image_path is stored relative to
            # data_root (matching the original bugfix-009 convention), so it survives
            # data_root moving/being mounted at a different absolute path.
            try:
                relative_image_path = str(file_path.relative_to(Path(self.config.data_root)))
            except ValueError:
                relative_image_path = str(file_path)
            self._store_media_turn(
                chat_id, sender_display_name or sender_phone, media_type, caption, summary,
                ledger_event_ids, message_id, relative_image_path
            )

            return {
                "success": True,
                "summary": summary,
                "media_attachment": attachment,
                "error_message": None
            }
            
        except ValueError as e:
            # Validation errors (file size, format, page count)
            return self._error_response(str(e))
        except Exception as e:
            # Unexpected errors
            return self._error_response(
                "Unable to process this file. Please try again or use a different format."
            )

    def _store_media_turn(
        self, chat_id: str, sender_display: str, media_type: str, caption: str, summary: str,
        ledger_event_ids: Optional[list] = None, message_id: Optional[str] = None,
        image_path: Optional[str] = None
    ) -> None:
        """bugfix-017: store both sides of a media turn in the session, mirroring
        AIHandler._finalize_response's user+assistant storage for text turns.
        Never lets a storage failure fail the whole media-processing turn - the
        user still gets their summary reply even if this logging step errors.

        ledger_event_ids (Feature 033): id(s) of any LedgerEvent(s) captured from
        this message, threaded onto the user message only (never the assistant
        reply) - REQ-TRACE-003.

        message_id (Feature 033, confirmed design): the id decided once at
        message-arrival time (WhatsAppHandler.handle_media_message, via
        WhatsAppMessage.from_notification) - MUST be identical across the
        persisted message's filename, the session's message_ids entry, and
        LedgerEvent.message_id. Applied to the user message only; the assistant
        reply gets its own fresh id, same as always.

        image_path (bugfix-009, reopened 2026-07-30): relative to data_root,
        resolved by the caller - attached to the user message only, so the
        session can be traced back to the saved media file on disk. This
        parameter regressed to always-omitted when this method replaced
        bugfix-009's original call site; restored here alongside the Feature
        033 traceability fields it was merged with.

        sender_display (Feature 039): the resolved human-readable sender name
        (falls back to the raw phone if unavailable) - SessionManager.add_message
        itself now always overrides recipient=None for user messages and
        sender=None for assistant messages regardless of what's passed here, so
        this value only ever lands on the user message's sender and the
        assistant reply's recipient."""
        try:
            user_content = caption or f"[{media_type} sent]"
            self.session_manager.add_message(
                chat_id=chat_id, role="user", content=user_content,
                user_role="client", sender=sender_display,
                ledger_event_ids=ledger_event_ids, message_id=message_id,
                image_path=image_path,
            )
            self.session_manager.add_message(
                chat_id=chat_id, role="assistant", content=summary,
                user_role="client", recipient=sender_display,
            )
        except Exception as e:
            logger.error(f"Failed to store media turn in session: {e}", exc_info=True)

    def _extract_text(self, media_type: str, media: Media, caption: str = "") -> Dict:
        """
        Route to appropriate analyzer based on media type.
        
        Args:
            media_type: 'image', 'pdf', or 'docx'
            media: In-memory Media object with file data
            caption: User's message/question sent with the file (optional)
        
        Returns:
            Analysis result with raw_response, extraction_quality, etc.
        """
        if media_type == 'image':
            return self.image_extractor.analyze_media(media, caption=caption)
        elif media_type == 'pdf':
            return self.pdf_extractor.analyze_media(media, caption=caption)
        elif media_type == 'docx':
            return self.docx_extractor.analyze_media(media, caption=caption)
        else:
            raise ValueError(f"Unknown media type: {media_type}")
    
    # bugfix-028: Hebrew labels for the fields a bank confirmation must carry,
    # used to ask for them by name rather than by their internal keys.
    _FIELD_LABELS_HE = {
        "payer_name": "שם המעביר",
        "amount": "הסכום",
        "txn_date": "תאריך ההעברה",
        "bank_number": "מספר הבנק",
        "bank_branch": "מספר הסניף",
        "bank_account": "מספר החשבון",
        "client_name": "שם הלקוח",
        "components": "פירוט שכר הטרחה",
    }

    def _compose_user_message(self, analysis_result: Dict) -> str:
        """Build the reply the user reads: the extracted text, plus a question
        when the document couldn't be classified or is missing details.

        bugfix-028 (user, 2026-08-09): "WHEN NOT CLEAR - ASK". A document we
        can't classify, or a bank confirmation we can't read every required
        field off, is not something to quietly guess at - the user is right
        there and can answer in one line. This is the point where that happens,
        because it is the first point that knows both what was read and what
        was missing.
        """
        extracted = (analysis_result.get("raw_response") or "").strip()
        doc_type = analysis_result.get("doc_type")
        missing = analysis_result.get("missing_required_fields") or []

        if doc_type == "unknown":
            question = (
                "לא הצלחתי לזהות בוודאות איזה סוג מסמך זה - האם מדובר באישור "
                "העברה/הפקדה בנקאית, בהסכם שכר טרחה, או במשהו אחר? מה תרצה שאעשה איתו?"
            )
        elif missing:
            labels = [self._FIELD_LABELS_HE.get(f, f) for f in missing]
            question = (
                f"חסרים לי הפרטים הבאים כדי להמשיך: {', '.join(labels)}. "
                f"תוכל להשלים אותם?"
            )
        else:
            question = ""

        return f"{extracted}\n\n{question}".strip() if question else extracted

    def _error_response(self, message: str) -> Dict:
        """
        Standard error response format.
        
        Args:
            message: User-friendly error message
        
        Returns:
            Error response dict
        """
        return {
            "success": False,
            "summary": "",
            "media_attachment": None,
            "error_message": message
        }
