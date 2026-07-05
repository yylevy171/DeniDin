"""
Media Model - Represents media files (images, documents) in memory
Feature 003: Media & Document Processing
"""
import base64
from dataclasses import dataclass
from typing import Optional


# Maximum media size: 10MB
MAX_MEDIA_SIZE = 10 * 1024 * 1024


@dataclass
class Media:
    """
    In-memory representation of downloaded media.
    Max size: 10MB.
    """
    data: bytes
    mime_type: str
    filename: Optional[str] = None
    
    def __post_init__(self):
        """Validate media size."""
        if len(self.data) > MAX_MEDIA_SIZE:
            raise ValueError(
                f"Media size {len(self.data)} bytes exceeds maximum {MAX_MEDIA_SIZE} bytes"
            )
    
    def to_base64(self) -> str:
        """
        Encode media data to base64 string.
        
        Returns:
            Base64-encoded string
        """
        return base64.b64encode(self.data).decode('utf-8')
    
    def get_data_url(self) -> str:
        """
        Get data URL for use in API calls.
        
        Returns:
            Data URL with format: data:{mime_type};base64,{data}
        """
        return f"data:{self.mime_type};base64,{self.to_base64()}"
    
    @property
    def size(self) -> int:
        """Get media size in bytes."""
        return len(self.data)
    
    @classmethod
    def from_bytes(cls, data: bytes, mime_type: str, filename: Optional[str] = None) -> 'Media':
        """
        Create Media instance from bytes.
        
        Args:
            data: Raw media bytes
            mime_type: MIME type (e.g., 'image/jpeg', 'application/pdf')
            filename: Optional filename
            
        Returns:
            Media instance
            
        Raises:
            ValueError: If data exceeds 10MB
        """
        return cls(data=data, mime_type=mime_type, filename=filename)
