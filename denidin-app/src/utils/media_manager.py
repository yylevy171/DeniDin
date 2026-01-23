"""
Media Manager for file download, validation, and storage.

TASK-007: MediaManager Implementation (CODE) - TDD Green Phase
Makes TASK-006 tests pass.

CHK References:
- CHK001-005: File size validation and format support
- CHK006-010, CHK023: Hebrew/UTF-8 text support
- CHK019-024: Storage paths with UTC timestamps
- CHK039-041: Format validation (JPG/PNG/PDF/DOCX supported, GIF/TXT rejected)
- CHK048: Retry logic (1 retry = 2 total attempts)
- CHK064: File download
- CHK075-076: Boundary conditions (0 bytes, exactly 10MB)
"""
from pathlib import Path
from datetime import datetime, timezone
from typing import Tuple, Optional
import requests
from src.utils.logger import get_logger

logger = get_logger(__name__)


class MediaManager:
    """
    Manages media file operations: download, validation, and storage.
    
    Responsibilities:
    - Download files from URLs with retry logic
    - Validate file size and format
    - Generate storage paths with UTC timestamps
    - Save extracted text with UTF-8 encoding
    """
    
    # CHK001-002: 10MB file size limit
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10,485,760 bytes
    
    # CHK039-041: Supported and unsupported formats
    SUPPORTED_FORMATS = {
        'jpg': 'image',
        'jpeg': 'image',
        'png': 'image',
        'pdf': 'pdf',
        'docx': 'docx'
    }
    
    UNSUPPORTED_FORMATS = ['gif', 'txt', 'xls', 'xlsx', 'ppt', 'pptx', 'zip']
    
    def __init__(self, storage_base: str = "data/images"):
        """
        Initialize MediaManager.
        
        Args:
            storage_base: Base directory for media storage (default: data/images)
        """
        self.storage_base = Path(storage_base)
    
    def download_file(self, url: str) -> Tuple[Optional[bytes], bool]:
        """
        Download file from URL with retry logic.
        
        CHK048: Retry once on failure (2 total attempts).
        CHK064: Return file content and success flag.
        
        Args:
            url: File download URL
            
        Returns:
            Tuple of (file_content, success):
                - file_content: bytes if successful, None if failed
                - success: True if download succeeded, False otherwise
        """
        max_attempts = 2  # Original + 1 retry
        
        for attempt in range(1, max_attempts + 1):
            try:
                logger.debug(f"Downloading file from {url} (attempt {attempt}/{max_attempts})")
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                
                logger.info(f"Successfully downloaded file from {url} ({len(response.content)} bytes)")
                return response.content, True
                
            except Exception as e:
                logger.warning(f"Download attempt {attempt}/{max_attempts} failed: {e}")
                
                if attempt == max_attempts:
                    logger.error(f"Failed to download file after {max_attempts} attempts: {url}")
                    return None, False
        
        return None, False
    
    def validate_file_size(self, size_bytes: int) -> None:
        """
        Validate file size is within limits.
        
        CHK001-002: Maximum 10MB (10,485,760 bytes).
        CHK075: Reject 0-byte files.
        CHK076: Exactly 10MB should pass.
        
        Args:
            size_bytes: File size in bytes
            
        Raises:
            ValueError: If file is empty or exceeds size limit
        """
        # CHK075: Reject empty files
        if size_bytes == 0:
            raise ValueError("File is empty (0 bytes)")
        
        # CHK001-002, CHK076: Check max size
        if size_bytes > self.MAX_FILE_SIZE:
            raise ValueError(
                f"File too large: {size_bytes} bytes (max {self.MAX_FILE_SIZE})"
            )
        
        logger.debug(f"File size validation passed: {size_bytes} bytes")
    
    def validate_format(self, filename: str, mime_type: str) -> str:
        """
        Validate file format and return media type.
        
        CHK039: Supported formats - JPG, JPEG, PNG, PDF, DOCX.
        CHK040-041: Unsupported formats - GIF, TXT, etc.
        
        Args:
            filename: Original filename
            mime_type: MIME type from WhatsApp
            
        Returns:
            Media type: 'image', 'pdf', or 'docx'
            
        Raises:
            ValueError: If format is not supported
        """
        # Extract extension (case-insensitive)
        extension = Path(filename).suffix.lstrip('.').lower()
        
        # CHK040-041: Check if explicitly unsupported
        if extension in self.UNSUPPORTED_FORMATS:
            raise ValueError(f"Unsupported format: {extension}")
        
        # CHK039: Check if supported
        if extension not in self.SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported format: {extension}")
        
        media_type = self.SUPPORTED_FORMATS[extension]
        logger.debug(f"Format validation passed: {extension} -> {media_type}")
        
        return media_type
    
    def create_storage_path(self) -> Path:
        """
        Create storage directory path with UTC timestamp.
        
        CHK019: UTC timestamp with microsecond precision.
        CHK020: Create directory with parents.
        
        Path format: data/images/YYYY-MM-DD/image-timestamp.microseconds/
        
        Returns:
            Path object for storage directory
        """
        # CHK019: UTC timestamp with microseconds
        now = datetime.now(timezone.utc)
        date_str = now.strftime("%Y-%m-%d")
        timestamp = now.timestamp()
        
        # Path structure: data/images/YYYY-MM-DD/image-timestamp/
        storage_path = self.storage_base / date_str / f"image-{timestamp}"
        
        # CHK020: Create directory with parents
        storage_path.mkdir(parents=True, exist_ok=True)
        
        logger.debug(f"Created storage path: {storage_path}")
        return storage_path
    
    def save_rawtext(self, text: str, folder: Path, original_filename: str) -> Path:
        """
        Save extracted text to .rawtext file with UTF-8 encoding.
        
        CHK023: UTF-8 encoding for .rawtext files.
        CHK006-010: Support Hebrew text without corruption.
        
        Args:
            text: Extracted text content
            folder: Directory to save file in
            original_filename: Original file name (e.g., "contract.pdf")
            
        Returns:
            Path to created .rawtext file
        """
        rawtext_path = folder / f"{original_filename}.rawtext"
        
        # CHK023, CHK006-010: UTF-8 encoding for Hebrew support
        with open(rawtext_path, 'w', encoding='utf-8') as f:
            f.write(text)
        
        logger.debug(f"Saved raw text to {rawtext_path} ({len(text)} characters)")
        return rawtext_path
