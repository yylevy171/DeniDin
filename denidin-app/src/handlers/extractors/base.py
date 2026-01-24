"""
Base interface for media extractors (Feature 003 Phase 4).

Defines the contract that all media extractors must implement.
Ensures consistent return format across all media types.
"""
from abc import ABC, abstractmethod
from typing import Dict, Optional
from src.models.media import Media


class MediaExtractor(ABC):
    """
    Base interface for all media extractors.
    
    All extractors must implement extract_text() which returns:
    - extracted_text: The raw text content
    - document_analysis: AI-generated analysis (type, summary, key_points)
    - extraction_quality: Quality assessment
    - warnings: List of issues encountered
    - model_used: Which model/library was used
    
    This interface ensures:
    1. Consistent return format across all media types
    2. Easy addition of new media types (audio, video, etc.)
    3. Clear contract for testing
    4. Flexibility for different extraction strategies
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
    def extract_text(self, media: Media, caption: str = "") -> Dict:
        """
        Extract text and analyze document.
        
        Must return consistent structure across all implementations.
        
        Args:
            media: Media object containing file data in memory
            caption: User's message/question sent with the file (optional)
            
        Returns:
            {
                "extracted_text": str | List[str],  # Text content (List for multi-page)
                "document_analysis": {              # AI-generated analysis
                    "document_type": str,           # e.g., "contract", "receipt", "generic"
                    "summary": str,                 # Natural language summary
                    "key_points": List[str]         # Bullet points of key info
                } | None,                           # None if analysis skipped (DOCX analyze=False)
                "extraction_quality": str | List[str],  # "high", "medium", "low", "failed"
                "warnings": List[str] | List[List[str]],  # Issues encountered
                "model_used": str                   # e.g., "gpt-4o", "python-docx"
            }
        """
        pass
    
    def supports_analysis(self) -> bool:
        """
        Whether this extractor includes document analysis.
        
        Override if extractor optionally supports analysis.
        Default: True (most extractors use AI which includes analysis).
        
        Returns:
            True if document_analysis is always/optionally included
        """
        return True
