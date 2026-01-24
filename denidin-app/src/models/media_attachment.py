"""
Media attachment model for WhatsApp media messages.

This model represents media files (images, PDFs, DOCX) sent via WhatsApp,
including extracted text and document analysis metadata.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class MediaAttachment:
    """
    Media file metadata for WhatsApp messages.
    
    Attributes:
        media_type: File category - 'image', 'pdf', 'docx'
        file_url: Green API download URL
        file_path: Local storage path
        raw_text_path: Path to extracted .rawtext file
        mime_type: MIME type string (e.g., 'image/jpeg')
        file_size: File size in bytes
        page_count: Number of pages (PDFs only)
        caption: WhatsApp message text sent with file (user's question/comment)
    """
    
    media_type: str
    file_url: str
    file_path: str
    raw_text_path: str
    mime_type: str
    file_size: int
    page_count: Optional[int] = None
    caption: str = ""
    
    def validate(self) -> None:
        """
        Validate attachment meets requirements.
        
        Raises:
            ValueError: If file size exceeds 10MB or PDF has >10 pages
        """
        # CHK001-002: File size validation
        max_size = 10 * 1024 * 1024  # 10MB
        if self.file_size > max_size:
            raise ValueError(
                f"File too large: {self.file_size} bytes (max {max_size})"
            )
        
        # CHK003-004: Page count validation for PDFs
        if self.media_type == 'pdf' and self.page_count and self.page_count > 10:
            raise ValueError(f"PDF has {self.page_count} pages (max 10)")
