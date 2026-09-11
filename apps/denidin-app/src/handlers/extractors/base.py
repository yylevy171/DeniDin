"""
Base interface for media analyzers (Feature 003 Phase 4).

Defines the contract that all media analyzers must implement.
Ensures consistent return format across all media types.
"""
from abc import ABC, abstractmethod
from typing import Dict, Optional
from src.models.media import Media


class MediaExtractor(ABC):
    """
    Base interface for all media analyzers.
    
    All analyzers must implement analyze_media() which returns:
    - raw_response: The full unmodified AI response
    - extraction_quality: Quality assessment
    - warnings: List of issues encountered
    - model_used: Which model/library was used
    
    This interface ensures:
    1. Consistent return format across all media types
    2. Easy addition of new media types (audio, video, etc.)
    3. Clear contract for testing
    4. Flexibility for different analysis strategies
    """
    
    def __init__(self, denidin_context):
        """
        Initialize with DeniDin global context.
        
        Args:
            denidin_context: DeniDin instance with ai_handler and config
        """
        self.context = denidin_context
        self.config = denidin_context.config
        self.ai_handler = denidin_context.ai_handler
    
    @abstractmethod
    def analyze_media(self, media: Media, caption: str = "", today_timestamp: Optional[int] = None) -> Dict:
        """
        Analyze media and return AI response.

        Must return consistent structure across all implementations.

        Args:
            media: Media object containing file data in memory
            caption: User's message/question sent with the file (optional)
            today_timestamp: (Feature 043) Unix epoch int - the source
                message's real historical timestamp, threaded down from
                MediaHandler.process_media_message's own `timestamp` param.
                Only ImageExtractor (directly, and PDFExtractor via its
                per-page delegation to ImageExtractor) does anything with
                this - it overrides wall-clock "today" in the ledger-event
                classification call's date resolution (see
                AIHandler._build_instructions/capture_ledger_events_from_text).
                DOCXExtractor accepts but ignores it. `None` (the default)
                preserves current wall-clock behavior everywhere.

                Feature 069 (Phase 10): ledger capture from media is now a
                POST-TURN recognition step - the extractors no longer persist
                LedgerEvents. ImageExtractor still runs its field-structuring
                pass (populating `ledger_events`), and DOCXExtractor surfaces a
                deterministic `document_analysis.document_type` ("הסכם"/"generic",
                no OpenAI call); MediaHandler turns either signal into a synthetic
                conversational turn via build_ledger_stash_text.

        Returns:
            {
                "raw_response": str,                # Full unmodified AI response
                "extraction_quality": str | List[str],  # "high", "medium", "low", "failed"
                "warnings": List[str] | List[List[str]],  # Issues encountered
                "model_used": str                   # e.g., "gpt-4o", "python-docx"
            }
        """
        pass
    
    def supports_analysis(self) -> bool:
        """
        Whether this analyzer includes AI analysis.
        
        Override if analyzer optionally supports analysis.
        Default: True (most analyzers use AI).
        
        Returns:
            True if AI analysis is always/optionally included
        """
        return True
