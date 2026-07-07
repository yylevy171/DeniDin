"""
Document models for Media & Document Processing feature.

TASK-003: Document Models (CODE) - TDD Green Phase
Makes TASK-002 tests pass.

CHK References:
- CHK001-004: File size and page count validation
- CHK012-018: Document types and metadata
- CHK075-077: Boundary conditions
- CHK111: Caption terminology
"""
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Optional


class DocumentType(Enum):
    """
    CHK012: Five document types for AI classification.

    - CONTRACT: Service agreements, employment contracts
    - RECEIPT: Purchase receipts, payment confirmations
    - INVOICE: Bills, invoices for services
    - COURT_RESOLUTION: Court decisions, legal resolutions
    - GENERIC: Fallback for unclassifiable or miscellaneous documents
    """
    CONTRACT = "contract"
    RECEIPT = "receipt"
    INVOICE = "invoice"
    COURT_RESOLUTION = "court_resolution"
    GENERIC = "generic"


@dataclass
class DocumentMetadata:
    """
    Document type and AI-extracted metadata.

    CHK016: Metadata structure varies by document type.
    CHK017: All metadata fields are optional (AI might not find them).
    CHK018: Confidence notes for ambiguous/poor quality documents.
    CHK114: Generic is both a valid type AND a fallback.

    Attributes:
        document_type: Classification from DocumentType enum
        summary: Natural language description of document (required)
        metadata_fields: Dict of extracted fields (client_name, amount, etc.)
        confidence_notes: Optional quality warnings (handwriting, poor scan, etc.)
    """
    document_type: DocumentType
    summary: str
    metadata_fields: Dict[str, str] = field(default_factory=dict)
    confidence_notes: Optional[str] = None


@dataclass
class MediaAttachment:
    """
    Media file metadata for WhatsApp messages.

    CHK111: Caption is WhatsApp message text, NOT file-embedded metadata.
    CHK001-004: File size and page count validation.
    CHK075-077: Boundary condition handling.

    Attributes:
        media_type: 'image', 'pdf', or 'docx'
        file_url: Green API download URL
        file_path: Local storage path (data/images/{date}/image-{timestamp}/file.ext)
        mime_type: MIME type from WhatsApp
        file_size: Size in bytes
        page_count: Number of pages (PDF only, optional)
        caption: WhatsApp message text (optional)
    """
    media_type: str
    file_url: str
    file_path: str
    mime_type: str
    file_size: int
    page_count: Optional[int] = None
    caption: Optional[str] = None

    def validate(self) -> None:
        """
        Validate file size and page count constraints.

        CHK001-002: 10MB file size limit (10,485,760 bytes)
        CHK075: Reject 0-byte files
        CHK076: Exactly 10MB should pass
        CHK003-004: PDF page count limit (10 pages max)
        CHK077: Boundary conditions (1 page, 10 pages OK; 11 pages fails)

        Raises:
            ValueError: If validation fails
        """
        # CHK075: Reject empty files
        if self.file_size == 0:
            raise ValueError("File is empty (0 bytes)")

        # CHK001-002, CHK076: File size validation (10MB max)
        max_size = 10 * 1024 * 1024  # 10,485,760 bytes
        if self.file_size > max_size:
            raise ValueError(
                f"File too large: {self.file_size} bytes (max {max_size})"
            )

        # CHK003-004, CHK077: PDF page count validation (only for PDFs)
        if self.media_type == 'pdf' and self.page_count is not None:
            if self.page_count > 10:
                raise ValueError(
                    f"PDF has {self.page_count} pages (max 10)"
                )
