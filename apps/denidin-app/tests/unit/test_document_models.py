"""
Unit tests for Media & Document Processing models.
Tests DocumentType enum, MediaAttachment, and DocumentMetadata.

TASK-002: Document Models (TEST) - TDD Red Phase
All tests should FAIL initially - models don't exist yet.

CHK References: CHK001-004 (validation), CHK012-018 (document types), 
                CHK076-077 (boundaries), CHK111 (caption terminology)
"""
import pytest
from src.models.document import DocumentType, DocumentMetadata, MediaAttachment


class TestDocumentType:
    """Test DocumentType enum definition."""
    
    def test_document_type_enum_has_all_five_types(self):
        """CHK012: Five document types defined - contract, receipt, invoice, court_resolution, generic."""
        assert DocumentType.CONTRACT.value == "contract"
        assert DocumentType.RECEIPT.value == "receipt"
        assert DocumentType.INVOICE.value == "invoice"
        assert DocumentType.COURT_RESOLUTION.value == "court_resolution"
        assert DocumentType.GENERIC.value == "generic"
    
    def test_document_type_is_enum(self):
        """DocumentType should be an Enum for type safety."""
        from enum import Enum
        assert issubclass(DocumentType, Enum)


class TestMediaAttachment:
    """Test MediaAttachment dataclass for file metadata and validation."""
    
    def test_create_media_attachment_with_required_fields(self):
        """Basic creation test - verify all required fields are stored."""
        attachment = MediaAttachment(
            media_type='image',
            file_url='https://example.com/file.jpg',
            file_path='/data/images/2026-01-22/image-123/file.jpg',
            mime_type='image/jpeg',
            file_size=1024
        )
        assert attachment.media_type == 'image'
        assert attachment.file_url == 'https://example.com/file.jpg'
        assert attachment.file_size == 1024
    
    def test_validate_file_size_under_limit(self):
        """CHK001-002: File size validation - files under 10MB should pass."""
        attachment = MediaAttachment(
            media_type='pdf',
            file_url='https://example.com/doc.pdf',
            file_path='/data/images/doc.pdf',
            mime_type='application/pdf',
            file_size=5 * 1024 * 1024  # 5MB
        )
        attachment.validate()  # Should not raise
    
    def test_validate_file_size_over_limit(self):
        """CHK001-002: Reject files > 10MB."""
        attachment = MediaAttachment(
            media_type='pdf',
            file_url='https://example.com/doc.pdf',
            file_path='/data/images/doc.pdf',
            mime_type='application/pdf',
            file_size=15 * 1024 * 1024  # 15MB
        )
        with pytest.raises(ValueError, match="File too large"):
            attachment.validate()
    
    def test_validate_file_size_exactly_10mb(self):
        """CHK076: Boundary condition - exactly 10MB (10,485,760 bytes) should pass."""
        attachment = MediaAttachment(
            media_type='pdf',
            file_url='https://example.com/doc.pdf',
            file_path='/data/images/doc.pdf',
            mime_type='application/pdf',
            file_size=10 * 1024 * 1024  # Exactly 10MB
        )
        attachment.validate()  # Should not raise
    
    def test_validate_zero_byte_file_rejected(self):
        """CHK075: Edge case - 0-byte files should be rejected."""
        attachment = MediaAttachment(
            media_type='image',
            file_url='https://example.com/empty.jpg',
            file_path='/data/images/empty.jpg',
            mime_type='image/jpeg',
            file_size=0
        )
        with pytest.raises(ValueError, match="File is empty"):
            attachment.validate()
    
    def test_validate_pdf_page_count_within_limit(self):
        """CHK003-004: PDF page count validation - 8 pages should pass."""
        attachment = MediaAttachment(
            media_type='pdf',
            file_url='https://example.com/doc.pdf',
            file_path='/data/images/doc.pdf',
            mime_type='application/pdf',
            file_size=1024,
            page_count=8
        )
        attachment.validate()  # Should not raise
    
    def test_validate_pdf_exactly_10_pages(self):
        """CHK077: Boundary - exactly 10 pages should pass."""
        attachment = MediaAttachment(
            media_type='pdf',
            file_url='https://example.com/doc.pdf',
            file_path='/data/images/doc.pdf',
            mime_type='application/pdf',
            file_size=1024,
            page_count=10
        )
        attachment.validate()  # Should not raise
    
    def test_validate_pdf_over_10_pages(self):
        """CHK004: Reject PDFs with more than 10 pages."""
        attachment = MediaAttachment(
            media_type='pdf',
            file_url='https://example.com/doc.pdf',
            file_path='/data/images/doc.pdf',
            mime_type='application/pdf',
            file_size=1024,
            page_count=11
        )
        with pytest.raises(ValueError, match="pages \\(max 10\\)"):
            attachment.validate()
    
    def test_validate_pdf_1_page_passes(self):
        """CHK077: Boundary - 1 page PDF should pass."""
        attachment = MediaAttachment(
            media_type='pdf',
            file_url='https://example.com/doc.pdf',
            file_path='/data/images/doc.pdf',
            mime_type='application/pdf',
            file_size=1024,
            page_count=1
        )
        attachment.validate()  # Should not raise
    
    def test_page_count_optional_for_non_pdf(self):
        """CHK003: Page count only applies to PDFs, not other formats."""
        attachment = MediaAttachment(
            media_type='image',
            file_url='https://example.com/img.jpg',
            file_path='/data/images/img.jpg',
            mime_type='image/jpeg',
            file_size=1024
            # page_count not provided - should be fine for images
        )
        attachment.validate()  # Should not raise
    
    def test_caption_field_is_whatsapp_message_text(self):
        """CHK111: Caption is WhatsApp message text, not file-embedded metadata."""
        attachment = MediaAttachment(
            media_type='image',
            file_url='https://example.com/img.jpg',
            file_path='/data/images/img.jpg',
            mime_type='image/jpeg',
            file_size=1024,
            caption="What's in this photo?"
        )
        assert attachment.caption == "What's in this photo?"
    
    def test_caption_is_optional(self):
        """Caption field should be optional (user can send file without message)."""
        attachment = MediaAttachment(
            media_type='image',
            file_url='https://example.com/img.jpg',
            file_path='/data/images/img.jpg',
            mime_type='image/jpeg',
            file_size=1024
            # No caption provided
        )
        assert attachment.caption is None


class TestDocumentMetadata:
    """Test DocumentMetadata dataclass for AI-extracted document information."""
    
    def test_create_contract_metadata(self):
        """CHK016: Contract metadata structure with required fields."""
        metadata = DocumentMetadata(
            document_type=DocumentType.CONTRACT,
            summary="Service agreement with client",
            metadata_fields={
                "client_name": "David Cohen",
                "contract_type": "Service Agreement",
                "amount": "₪50,000"
            }
        )
        assert metadata.document_type == DocumentType.CONTRACT
        assert "David Cohen" in metadata.metadata_fields["client_name"]
        assert metadata.summary == "Service agreement with client"
    
    def test_create_receipt_metadata(self):
        """CHK016: Receipt metadata structure."""
        metadata = DocumentMetadata(
            document_type=DocumentType.RECEIPT,
            summary="Restaurant receipt",
            metadata_fields={
                "merchant": "Café Mizrahi",
                "amount": "₪120",
                "date": "2026-01-22"
            }
        )
        assert metadata.document_type == DocumentType.RECEIPT
        assert "Café Mizrahi" in metadata.metadata_fields["merchant"]
    
    def test_create_invoice_metadata(self):
        """CHK016: Invoice metadata structure."""
        metadata = DocumentMetadata(
            document_type=DocumentType.INVOICE,
            summary="Legal services invoice",
            metadata_fields={
                "invoice_number": "INV-2026-001",
                "amount": "₪15,000",
                "due_date": "2026-02-15"
            }
        )
        assert metadata.document_type == DocumentType.INVOICE
    
    def test_create_court_resolution_metadata(self):
        """CHK016, CHK043: Court resolution metadata (consistent naming)."""
        metadata = DocumentMetadata(
            document_type=DocumentType.COURT_RESOLUTION,
            summary="Custody hearing decision",
            metadata_fields={
                "case_number": "12345/2025",
                "court": "Tel Aviv Family Court",
                "decision_date": "2026-01-15"
            }
        )
        assert metadata.document_type == DocumentType.COURT_RESOLUTION
        assert "court_resolution" in metadata.document_type.value
    
    def test_create_generic_metadata_as_fallback(self):
        """CHK013, CHK114: Generic type as fallback when AI can't determine type."""
        metadata = DocumentMetadata(
            document_type=DocumentType.GENERIC,
            summary="Miscellaneous document",
            metadata_fields={}
        )
        assert metadata.document_type == DocumentType.GENERIC
    
    def test_generic_is_valid_classification_not_just_fallback(self):
        """CHK114: Generic can be a valid classification, not just error fallback."""
        metadata = DocumentMetadata(
            document_type=DocumentType.GENERIC,
            summary="Personal notes",
            metadata_fields={"notes": "Planning document"}
        )
        assert metadata.document_type == DocumentType.GENERIC
        assert len(metadata.metadata_fields) > 0  # Can have metadata
    
    def test_metadata_fields_are_optional(self):
        """CHK017: All metadata fields are optional (AI might not find them)."""
        metadata = DocumentMetadata(
            document_type=DocumentType.RECEIPT,
            summary="Receipt with minimal info",
            metadata_fields={}  # Empty - all fields optional
        )
        assert metadata.metadata_fields == {}
    
    def test_summary_is_required(self):
        """Summary field should always be present (natural language description)."""
        metadata = DocumentMetadata(
            document_type=DocumentType.GENERIC,
            summary="Brief document description",
            metadata_fields={}
        )
        assert len(metadata.summary) > 0
    
    def test_confidence_notes_for_ambiguous_documents(self):
        """CHK018: Quality warnings for ambiguous documents."""
        metadata = DocumentMetadata(
            document_type=DocumentType.GENERIC,
            summary="Partially readable document",
            metadata_fields={},
            confidence_notes="Handwritten text, poor quality"
        )
        assert "Handwritten" in metadata.confidence_notes
    
    def test_confidence_notes_optional(self):
        """Confidence notes only needed when there are quality issues."""
        metadata = DocumentMetadata(
            document_type=DocumentType.CONTRACT,
            summary="Clear, high-quality contract",
            metadata_fields={"client_name": "ABC Corp"}
            # No confidence_notes - document is clear
        )
        assert metadata.confidence_notes is None


class TestMediaAttachmentIntegration:
    """Integration tests combining MediaAttachment with DocumentMetadata."""
    
    def test_attachment_with_extracted_metadata(self):
        """Complete flow: attachment + AI-extracted metadata."""
        attachment = MediaAttachment(
            media_type='pdf',
            file_url='https://example.com/contract.pdf',
            file_path='/data/images/2026-01-22/image-123/contract.pdf',
            mime_type='application/pdf',
            file_size=2 * 1024 * 1024,
            page_count=5,
            caption="Please review this contract"
        )
        
        metadata = DocumentMetadata(
            document_type=DocumentType.CONTRACT,
            summary="Employment contract for new hire",
            metadata_fields={
                "employee": "Sarah Levi",
                "start_date": "2026-02-01",
                "salary": "₪25,000/month"
            }
        )
        
        # Simulate storing together
        attachment.validate()
        assert attachment.media_type == 'pdf'
        assert metadata.document_type == DocumentType.CONTRACT
