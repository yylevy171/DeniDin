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
    def analyze_media(self, media: Media, caption: str = "") -> Dict:
        """
        Analyze media and return AI response.
        
        Must return consistent structure across all implementations.
        
        Args:
            media: Media object containing file data in memory
            caption: User's message/question sent with the file (optional)
            
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
