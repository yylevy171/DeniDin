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
        timestamp: Optional[int] = None
    ) -> Dict:
        """
        Process media message through complete workflow.

        Args:
            file_url: Green API download URL
            filename: Original filename
            mime_type: MIME type string
            file_size: File size in bytes
            sender_phone: WhatsApp phone number (e.g., "972501234567")
            chat_id: WhatsApp chat ID (bugfix-017: needed to link this turn to a
                session, same as the text path - group chats differ from sender_phone)
            caption: User's message text with file (optional)
            timestamp: Real Green API notification timestamp (Feature 024) - the
                constitution's "hard pointer" for any ledger event captured from this
                message. Falls back to processing time only if genuinely absent,
                same as WhatsAppMessage.from_webhook's own fallback.

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
            
            # Step 8: Get the raw AI response as summary (uses only prompts from txt files)
            # The prompt file defines the format, AI returns it, we pass it as-is
            summary = analysis_result.get("raw_response", "")
            
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

            # Step 10 (bugfix-017): link this turn to the session, mirroring
            # AIHandler._finalize_response's user+assistant storage for text turns -
            # media messages must not be invisible to conversation history/memory
            # transfer just because they went through a different pipeline.
            self._store_media_turn(chat_id, sender_phone, media_type, caption, summary)

            # Ledger Event Recognition (runtime_constitution.md): the image path can
            # capture a fee-agreement/bank-deposit event the same way the text path
            # does - this is the single point where that capture actually gets stored,
            # now that chat_id/sender are in scope via the session-linkage fix above.
            # message_timestamp uses the real notification timestamp (the constitution's
            # "hard pointer") - NOT processing time, which was a real bug: falling back
            # to datetime.now() here meant a captured event's timestamp reflected when
            # the vision/classification calls happened to finish, not when the user
            # actually sent the image (found 2026-07-28 while strengthening this
            # feature's E2E persistence assertions).
            ledger_event = analysis_result.get("ledger_event")
            if ledger_event is not None:
                try:
                    if timestamp is not None:
                        event_timestamp = timestamp
                    else:
                        event_timestamp = int(datetime.now(timezone.utc).timestamp())
                    self.session_manager.add_pending_ledger_event(
                        chat_id=chat_id,
                        event=ledger_event,
                        message_timestamp=event_timestamp,
                        sender=sender_phone,
                    )
                except Exception as e:
                    logger.error(f"Failed to store pending ledger event for media message: {e}", exc_info=True)

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
        self, chat_id: str, sender_phone: str, media_type: str, caption: str, summary: str
    ) -> None:
        """bugfix-017: store both sides of a media turn in the session, mirroring
        AIHandler._finalize_response's user+assistant storage for text turns.
        Never lets a storage failure fail the whole media-processing turn - the
        user still gets their summary reply even if this logging step errors."""
        try:
            user_content = caption or f"[{media_type} sent]"
            self.session_manager.add_message(
                chat_id=chat_id, role="user", content=user_content,
                user_role="client", sender=sender_phone, recipient="AI",
            )
            self.session_manager.add_message(
                chat_id=chat_id, role="assistant", content=summary,
                user_role="client", sender="AI", recipient=sender_phone,
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
