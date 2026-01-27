"""MediaFileManager - File download, storage, and validation.

Handles:
- Downloading files from Green API
- File size and format validation
- Storage in flat directory structure
- Saving files and extracted text with DD-{sender_phone}-{uuid}.{ext} naming
"""

import uuid
import requests
from pathlib import Path
from typing import Tuple


class MediaFileManager:
    """Handles file download, storage, and validation."""
    
    # Configuration constants (CHK decisions)
    SUPPORTED_IMAGE_FORMATS = ['jpg', 'jpeg', 'png']
    SUPPORTED_DOCUMENT_FORMATS = ['pdf', 'docx']
    MAX_FILE_SIZE_MB = 10
    MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
    MAX_DOWNLOAD_RETRIES = 1  # CHK048: 1 retry max
    
    def __init__(self, denidin_context):
        """
        Initialize MediaFileManager.
        
        Args:
            denidin_context: Global DeniDin context with config
        """
        self.denidin = denidin_context
        self.config = denidin_context.config
        
        # Storage base path from config
        data_root = Path(self.config.data_root)
        self.storage_base = data_root / "media"
    
    def download_file(self, file_url: str) -> Tuple[bytes, bool]:
        """
        Download file from Green API or local file:// URL with retry logic.
        
        CHK048: Max 1 retry (2 total attempts)
        
        Args:
            file_url: Green API download URL or file:// URL for testing
        
        Returns:
            (file_content, success) - Empty bytes and False if failed
        """
        # Handle file:// URLs for testing
        if file_url.startswith('file://'):
            try:
                filepath = file_url[7:]  # Remove 'file://' prefix
                with open(filepath, 'rb') as f:
                    return (f.read(), True)
            except (FileNotFoundError, IOError):
                return (b"", False)
        
        # Handle HTTP/HTTPS URLs
        for attempt in range(self.MAX_DOWNLOAD_RETRIES + 1):
            try:
                response = requests.get(file_url, timeout=30)
                response.raise_for_status()
                return (response.content, True)
            except requests.RequestException:
                if attempt == self.MAX_DOWNLOAD_RETRIES:
                    return (b"", False)
                continue
        return (b"", False)
    
    def validate_file_size(self, file_size: int) -> None:
        """
        Validate file size meets requirements.
        
        CHK001-002: Max 10MB
        CHK075: Zero-byte files rejected
        CHK076: Boundary testing
        
        Args:
            file_size: File size in bytes
        
        Raises:
            ValueError: If file is empty or exceeds size limit
        """
        if file_size == 0:
            raise ValueError("File is empty (0 bytes)")
        
        if file_size > self.MAX_FILE_SIZE_BYTES:
            raise ValueError(
                f"File too large: {file_size} bytes "
                f"(max {self.MAX_FILE_SIZE_BYTES})"
            )
    
    def validate_format(self, filename: str, mime_type: str) -> str:
        """
        Validate file format is supported.
        
        CHK039-041: Supported formats
        
        Args:
            filename: Original filename
            mime_type: MIME type string
        
        Returns:
            media_type: 'image', 'pdf', or 'docx'
        
        Raises:
            ValueError: If format is unsupported
        """
        ext = Path(filename).suffix.lower().lstrip('.')
        
        if ext in self.SUPPORTED_IMAGE_FORMATS:
            return 'image'
        elif ext == 'pdf':
            return 'pdf'
        elif ext == 'docx':
            return 'docx'
        else:
            raise ValueError(
                f"Unsupported format: {ext}. "
                f"Supported: JPG, PNG, PDF, DOCX"
            )
    
    def create_storage_path(self) -> Path:
        """
        Create storage folder.
        
        REQ-MEDIA-004: Flat structure in {data_root}/media/
        No date subdirectories - files stored directly in media folder
        
        Returns:
            Path to storage folder
        """
        # Flat structure - just use storage_base
        self.storage_base.mkdir(parents=True, exist_ok=True)
        return self.storage_base
    
    def save_file(self, content: bytes, folder: Path, original_filename: str, sender_phone: str) -> Path:
        """
        Save file to storage folder with DD-{sender_phone}-{uuid}.{ext} naming.
        
        REQ-MEDIA-005: File naming includes sender identification and UUID
        
        Args:
            content: File content bytes
            folder: Storage folder path
            original_filename: Original filename (for extension)
            sender_phone: WhatsApp phone number (e.g., "972501234567")
        
        Returns:
            Path to saved file
        """
        # Generate UUID for collision prevention
        file_uuid = uuid.uuid4()
        
        # Extract extension from original filename
        ext = Path(original_filename).suffix.lower().lstrip('.')
        
        # Format: DD-{sender_phone}-{uuid}.{ext}
        filename = f"DD-{sender_phone}-{file_uuid}.{ext}"
        file_path = folder / filename
        
        with open(file_path, 'wb') as f:
            f.write(content)
        return file_path
