"""
Media Configuration for Media & Document Processing.

TASK-005: Media Config (CODE) - TDD Green Phase
Makes TASK-004 tests pass.

CHK References:
- CHK002: 10MB file size limit
- CHK011: 150 DPI for PDF conversion
- CHK023: UTF-8 encoding for Hebrew
- CHK039-041: Format support (JPG/JPEG/PNG/PDF/DOCX only)
- CHK042: Storage path (data/images/)
- CHK044-046: AI model consistency
- CHK048: 1 retry max
"""
from pathlib import Path
from typing import List


class MediaConfig:
    """
    Configuration constants for media and document processing.

    This class provides centralized configuration for:
    - Supported file formats (images and documents)
    - File size and page limits
    - AI model selection
    - Storage paths and encoding
    - Retry logic
    """

    # CHK039: Image formats - JPG, JPEG, PNG only (no GIF)
    SUPPORTED_IMAGE_FORMATS: List[str] = ['jpg', 'jpeg', 'png']

    # CHK040-041: Document formats - PDF, DOCX only (no TXT)
    SUPPORTED_DOCUMENT_FORMATS: List[str] = ['pdf', 'docx']

    # CHK002: File size limit - 10MB
    MAX_FILE_SIZE_MB: int = 10
    MAX_FILE_SIZE_BYTES: int = 10 * 1024 * 1024  # 10,485,760 bytes

    # CHK003-004: PDF page limit
    MAX_PDF_PAGES: int = 10

    # CHK011: PDF-to-image conversion DPI (for Hebrew quality)
    PDF_DPI: int = 150

    # CHK042: Storage base path
    STORAGE_BASE: Path = Path("data/images")

    # CHK044-046: AI model names (consistent naming)
    VISION_MODEL: str = "gpt-4o"  # For images and PDFs
    TEXT_MODEL: str = "gpt-4o-mini"  # For DOCX and document analysis

    # CHK048: Download retry logic - 1 retry (2 total attempts)
    MAX_DOWNLOAD_RETRIES: int = 1

    # CHK023: Text file encoding for Hebrew support
    RAWTEXT_ENCODING: str = "utf-8"

    # MIME type mappings for validation
    IMAGE_MIME_TYPES: List[str] = [
        'image/jpeg',  # JPG/JPEG
        'image/png',   # PNG
    ]

    DOCUMENT_MIME_TYPES: List[str] = [
        'application/pdf',  # PDF
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',  # DOCX
    ]
