"""
Unit tests for MediaHandler (Phase 5).

MediaHandler orchestrates the complete media processing workflow:
- Download → Validate → Extract → Format summary → Return response

Since extractors already return document_analysis from Phase 4,
MediaHandler formats the extractor's analysis into user-friendly summaries.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path
from src.handlers.media_handler import MediaHandler
from src.models.media_attachment import MediaAttachment


class TestMediaHandlerHappyPaths:
    """Happy path tests - successful processing flows."""
    
    def test_process_image_message_complete_flow(self):
        """
        Test complete image processing workflow.
        
        Flow: Download → Validate → Extract (with document_analysis) → Format summary → Return
        Maps to: File handling, Image processing
        """
        # Mock dependencies
        mock_denidin = Mock()
        mock_denidin.config.data_root = "/tmp/test_data"
        
        # Mock ImageExtractor returns actual result format with raw_response
        mock_image_result = {
            "raw_response": "Contract between parties... Service agreement for web development. Client: David Cohen, Amount: ₪50,000, Duration: 1 year",
            "extraction_quality": "high",
            "warnings": [],
            "model_used": "gpt-4o"
        }
        
        handler = MediaHandler(mock_denidin)
        
        # Mock extractors
        handler.image_extractor = Mock()
        handler.image_extractor.analyze_media = Mock(return_value=mock_image_result)
        
        # Mock MediaFileManager
        handler.media_file_manager = Mock()
        handler.media_file_manager.download_file = Mock(return_value=(b"fake_image_data", True))
        handler.media_file_manager.validate_file_size = Mock(return_value=None)
        handler.media_file_manager.validate_format = Mock(return_value="image")
        handler.media_file_manager.create_storage_path = Mock(return_value=Path("/tmp/test_data/media"))
        handler.media_file_manager.save_file = Mock(return_value=Path("/tmp/test_data/media/DD-972501234567-uuid.jpg"))
        handler.media_file_manager.save_rawtext = Mock(return_value=Path("/tmp/test_data/media/DD-972501234567-uuid.jpg.rawtext"))
        
        # Process image with sender_phone
        result = handler.process_media_message(
            file_url="https://example.com/image.jpg",
            filename="contract.jpg",
            mime_type="image/jpeg",
            file_size=500000,
            sender_phone="972501234567",
            caption="Can you summarize this?"
        )
        
        # Assertions
        assert result["success"] is True
        assert "Service agreement" in result["summary"]
        assert "David Cohen" in result["summary"]
        assert "₪50,000" in result["summary"]
        assert result["media_attachment"] is not None
        assert result["media_attachment"].media_type == "image"
        assert result["media_attachment"].caption == "Can you summarize this?"
        assert result["error_message"] is None
        
        # Verify extractor was called
        handler.image_extractor.analyze_media.assert_called_once()
        
        # Verify save_file was called with sender_phone
        handler.media_file_manager.save_file.assert_called_once()
        call_args = handler.media_file_manager.save_file.call_args
        assert call_args[0][3] == "972501234567"  # sender_phone is 4th positional arg
    
    def test_process_pdf_message_complete_flow(self):
        """
        Test complete PDF processing workflow.
        
        PDFExtractor returns multi-page result with aggregated document_analysis.
        Maps to: PDF processing, page aggregation
        """
        mock_denidin = Mock()
        mock_denidin.config.data_root = "/tmp/test_data"
        
        # Mock PDFExtractor returns multi-page result
        mock_pdf_result = {
            "raw_response": "Page 1 text\n---\nPage 2 text\n---\nPage 3 text",
            "extraction_quality": ["high", "high", "high"],
            "warnings": [[], [], []],
            "model_used": "gpt-4o"
        }
        
        handler = MediaHandler(mock_denidin)
        handler.pdf_extractor = Mock()
        handler.pdf_extractor.analyze_media = Mock(return_value=mock_pdf_result)
        
        # Mock MediaManager
        handler.media_file_manager = Mock()
        handler.media_file_manager.download_file = Mock(return_value=(b"fake_pdf_data", True))
        handler.media_file_manager.validate_file_size = Mock(return_value=None)
        handler.media_file_manager.validate_format = Mock(return_value="pdf")
        handler.media_file_manager.create_storage_path = Mock(return_value=Path("/tmp/test_data/media"))
        handler.media_file_manager.save_file = Mock(return_value=Path("/tmp/test_data/media/DD-972509876543-uuid.pdf"))
        handler.media_file_manager.save_rawtext = Mock(return_value=Path("/tmp/test_data/media/DD-972509876543-uuid.pdf.rawtext"))
        
        result = handler.process_media_message(
            file_url="https://example.com/invoice.pdf",
            filename="invoice.pdf",
            mime_type="application/pdf",
            file_size=800000,
            sender_phone="972509876543"
        )
        
        assert result["success"] is True
        assert "Page" in result["summary"]
        handler.pdf_extractor.analyze_media.assert_called_once()
    
    def test_process_docx_message_complete_flow(self):
        """
        Test complete DOCX processing workflow.
        
        DOCXExtractor returns result with optional analysis.
        Maps to: DOCX processing
        """
        mock_denidin = Mock()
        mock_denidin.config.data_root = "/tmp/test_data"
        
        mock_docx_result = {
            "raw_response": "Document content in Hebrew and English...",
            "extraction_quality": "high",
            "warnings": [],
            "model_used": "python-docx"
        }
        
        handler = MediaHandler(mock_denidin)
        handler.docx_extractor = Mock()
        handler.docx_extractor.analyze_media = Mock(return_value=mock_docx_result)
        
        handler.media_file_manager = Mock()
        handler.media_file_manager.download_file = Mock(return_value=(b"fake_docx_data", True))
        handler.media_file_manager.validate_file_size = Mock(return_value=None)
        handler.media_file_manager.validate_format = Mock(return_value="docx")
        handler.media_file_manager.create_storage_path = Mock(return_value=Path("/tmp/test_data/media"))
        handler.media_file_manager.save_file = Mock(return_value=Path("/tmp/test_data/media/DD-972501234567-uuid.docx"))
        handler.media_file_manager.save_rawtext = Mock(return_value=Path("/tmp/test_data/media/DD-972501234567-uuid.docx.rawtext"))
        
        result = handler.process_media_message(
            file_url="https://example.com/doc.docx",
            filename="document.docx",
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            file_size=300000,
            sender_phone="972501234567"
        )
        
        assert result["success"] is True
        assert "Document" in result["summary"]
        handler.docx_extractor.analyze_media.assert_called_once()
    
    def test_format_summary_with_metadata_bullets(self):
        """
        Test that AI response with bullet points is preserved.
        
        AI formats the summary with bullet points in its response.
        MediaHandler passes through the raw AI response as-is.
        Maps to: CHK036 (bullet formatting), CHK037 (currency symbols)
        """
        mock_denidin = Mock()
        mock_denidin.config.data_root = "/tmp/test_data"
        handler = MediaHandler(mock_denidin)
        
        # Mock extractors
        handler.image_extractor = Mock()
        handler.pdf_extractor = Mock()
        handler.docx_extractor = Mock()
        handler.media_file_manager = Mock()
        
        # AI response with bullet points - this is what the AI returns
        ai_response_with_bullets = """Receipt from Super-Pharm for personal care items

• Merchant: Super-Pharm Tel Aviv
• Date: 2026-01-22
• Total: ₪287.50
• Payment: Credit Card"""
        
        # Mock the extractor to return this formatted response
        handler.pdf_extractor.analyze_media = Mock(return_value={
            "raw_response": ai_response_with_bullets,
            "extraction_quality": "high",
            "page_count": 1
        })
        
        handler.media_file_manager.download_file = Mock(return_value=(b"fake_pdf_data", True))
        handler.media_file_manager.validate_file_size = Mock(return_value=None)
        handler.media_file_manager.validate_format = Mock(return_value="pdf")
        handler.media_file_manager.create_storage_path = Mock(return_value=Path("/tmp/media"))
        handler.media_file_manager.save_file = Mock(return_value=Path("/tmp/media/DD-972501234567-uuid.pdf"))
        handler.media_file_manager.save_rawtext = Mock(return_value=Path("/tmp/media/DD-972501234567-uuid.pdf.rawtext"))
        
        result = handler.process_media_message(
            file_url="https://example.com/receipt.pdf",
            filename="receipt.pdf",
            mime_type="application/pdf",
            file_size=50000,
            sender_phone="972501234567"
        )
        
        # Verify the AI's formatted response is preserved
        assert result["success"] is True
        summary = result["summary"]
        
        # Verify summary paragraph
        assert "Receipt from Super-Pharm" in summary
        
        # Verify bullet points are preserved (CHK036)
        assert "• Merchant: Super-Pharm Tel Aviv" in summary
        assert "• Total: ₪287.50" in summary  # CHK037: Currency symbol preserved
        assert "• Date: 2026-01-22" in summary
        assert "• Payment: Credit Card" in summary
    
    def test_message_with_caption_context(self):
        """
        Test caption is passed to extractor and included in MediaAttachment.
        
        Caption: "Can you summarize this contract?"
        Maps to: CHK111 (caption = user message)
        """
        mock_denidin = Mock()
        mock_denidin.config.data_root = "/tmp/test_data"
        
        handler = MediaHandler(mock_denidin)
        
        mock_result = {
            "raw_response": "Contract text",
            "document_analysis": {
                "document_type": "contract",
                "summary": "Service contract",
                "key_points": ["Client: John Doe"]
            },
            "extraction_quality": "high",
            "warnings": [],
            "model_used": "gpt-4o"
        }
        
        handler.image_extractor = Mock()
        handler.image_extractor.analyze_media = Mock(return_value=mock_result)
        
        handler.media_file_manager = Mock()
        handler.media_file_manager.download_file = Mock(return_value=(b"data", True))
        handler.media_file_manager.validate_file_size = Mock(return_value=None)
        handler.media_file_manager.validate_format = Mock(return_value="image")
        handler.media_file_manager.create_storage_path = Mock(return_value=Path("/tmp/media"))
        handler.media_file_manager.save_file = Mock(return_value=Path("/tmp/media/DD-972501234567-uuid.jpg"))
        handler.media_file_manager.save_rawtext = Mock(return_value=Path("/tmp/media/DD-972501234567-uuid.jpg.rawtext"))
        
        result = handler.process_media_message(
            file_url="https://example.com/img.jpg",
            filename="contract.jpg",
            mime_type="image/jpeg",
            file_size=400000,
            sender_phone="972501234567",
            caption="Can you summarize this contract?"
        )
        
        # Verify caption in MediaAttachment (CHK111)
        assert result["media_attachment"].caption == "Can you summarize this contract?"
        assert result["success"] is True
    
    def test_message_without_caption(self):
        """
        Test processing works without caption (optional field).
        Maps to: CHK060 (optional caption)
        """
        mock_denidin = Mock()
        mock_denidin.config.data_root = "/tmp/test_data"
        
        handler = MediaHandler(mock_denidin)
        
        mock_result = {
            "raw_response": "Text",
            "document_analysis": {
                "document_type": "generic",
                "summary": "Document summary",
                "key_points": []
            },
            "extraction_quality": "high",
            "warnings": [],
            "model_used": "gpt-4o"
        }
        
        handler.image_extractor = Mock()
        handler.image_extractor.analyze_media = Mock(return_value=mock_result)
        
        handler.media_file_manager = Mock()
        handler.media_file_manager.download_file = Mock(return_value=(b"data", True))
        handler.media_file_manager.validate_file_size = Mock(return_value=None)
        handler.media_file_manager.validate_format = Mock(return_value="image")
        handler.media_file_manager.create_storage_path = Mock(return_value=Path("/tmp/media"))
        handler.media_file_manager.save_file = Mock(return_value=Path("/tmp/media/DD-972501234567-uuid.jpg"))
        handler.media_file_manager.save_rawtext = Mock(return_value=Path("/tmp/media/DD-972501234567-uuid.jpg.rawtext"))
        
        # No caption provided (CHK060)
        result = handler.process_media_message(
            file_url="https://example.com/img.jpg",
            filename="image.jpg",
            mime_type="image/jpeg",
            file_size=400000,
            sender_phone="972501234567"
        )
        
        assert result["success"] is True
        assert result["media_attachment"].caption == ""


class TestMediaHandlerErrorHandling:
    """Error handling tests - validate graceful degradation."""
    
    def test_handle_file_too_large_error(self):
        """
        Test file size validation (over 10MB limit).
        
        With bugfix-006: Download first, THEN validate size.
        Maps to: CHK001-002 (size validation)
        """
        mock_denidin = Mock()
        mock_denidin.config.data_root = "/tmp/test_data"
        handler = MediaHandler(mock_denidin)
        
        handler.media_file_manager = Mock()
        # Mock download to succeed with large file
        large_content = b'x' * (11 * 1024 * 1024)  # 11MB
        handler.media_file_manager.download_file = Mock(
            return_value=(large_content, True)
        )
        # Mock validate_file_size to raise error for large files
        handler.media_file_manager.validate_file_size = Mock(
            side_effect=ValueError("File too large: 11534336 bytes (max 10485760)")
        )
        
        result = handler.process_media_message(
            file_url="https://example.com/huge.jpg",
            filename="huge.jpg",
            mime_type="image/jpeg",
            file_size=0,  # Green API doesn't provide fileSize - validate after download
            sender_phone="972501234567"
        )
        
        assert result["success"] is False
        # ValueError message is propagated directly to user
        assert "File too large" in result["error_message"]
        assert "11534336 bytes" in result["error_message"]
        
        # Verify download WAS attempted (new behavior: download first, then validate)
        handler.media_file_manager.download_file.assert_called_once_with('https://example.com/huge.jpg')
        # Verify validation was attempted on the downloaded content
        handler.media_file_manager.validate_file_size.assert_called_once_with(len(large_content))
    
    def test_handle_pdf_too_many_pages(self):
        """
        Test PDF page count validation (over 10 pages).
        
        Maps to: CHK003-004 (page limit), CHK077 (boundary)
        """
        mock_denidin = Mock()
        mock_denidin.config.data_root = "/tmp/test_data"
        
        handler = MediaHandler(mock_denidin)
        
        # Mock PDFExtractor raises ValueError for too many pages
        handler.pdf_extractor = Mock()
        handler.pdf_extractor.analyze_media = Mock(
            side_effect=ValueError("PDF has 15 pages (max 10)")
        )
        
        handler.media_file_manager = Mock()
        handler.media_file_manager.download_file = Mock(return_value=(b"pdf_data", True))
        handler.media_file_manager.validate_file_size = Mock(return_value=None)
        handler.media_file_manager.validate_format = Mock(return_value="pdf")
        handler.media_file_manager.create_storage_path = Mock(return_value=Path("/tmp/media"))
        handler.media_file_manager.save_file = Mock(return_value=Path("/tmp/media/DD-972501234567-uuid.pdf"))
        
        result = handler.process_media_message(
            file_url="https://example.com/big.pdf",
            filename="big_document.pdf",
            mime_type="application/pdf",
            file_size=2000000,
            sender_phone="972501234567"
        )
        
        assert result["success"] is False
        assert "PDF has 15 pages" in result["error_message"]
    
    def test_handle_unsupported_format_gif(self):
        """
        Test unsupported file format rejection (GIF).
        
        Maps to: CHK040 (GIF unsupported)
        """
        mock_denidin = Mock()
        mock_denidin.config.data_root = "/tmp/test_data"
        handler = MediaHandler(mock_denidin)
        
        handler.media_file_manager = Mock()
        handler.media_file_manager.download_file = Mock(return_value=(b"gif_data", True))
        handler.media_file_manager.validate_file_size = Mock(return_value=None)
        handler.media_file_manager.validate_format = Mock(
            side_effect=ValueError("Unsupported format: gif. Supported: JPG, PNG, PDF, DOCX")
        )
        
        result = handler.process_media_message(
            file_url="https://example.com/animation.gif",
            filename="animation.gif",
            mime_type="image/gif",
            file_size=500000,
            sender_phone="972501234567"
        )
        
        assert result["success"] is False
        assert "Unsupported format" in result["error_message"]
        assert "gif" in result["error_message"].lower()
    
    def test_handle_download_failure_with_retry(self):
        """
        Test download failure after retry exhausted.
        
        Mock download fails twice (exhausts 1 retry).
        Maps to: CHK048 (1 retry max)
        """
        mock_denidin = Mock()
        mock_denidin.config.data_root = "/tmp/test_data"
        handler = MediaHandler(mock_denidin)
        
        handler.media_file_manager = Mock()
        handler.media_file_manager.validate_file_size = Mock(return_value=None)
        # Download fails after retry
        handler.media_file_manager.download_file = Mock(return_value=(b"", False))
        
        result = handler.process_media_message(
            file_url="https://example.com/broken.jpg",
            filename="broken.jpg",
            mime_type="image/jpeg",
            file_size=500000,
            sender_phone="972501234567"
        )
        
        assert result["success"] is False
        assert "Unable to download" in result["error_message"]
    
    def test_handle_extraction_failure_corrupted_file(self):
        """
        Test extraction failure for corrupted file.
        
        Extractor returns: extraction_quality="failed", warnings=["Corrupted file"]
        Maps to: CHK005 (corrupted handling)
        """
        mock_denidin = Mock()
        mock_denidin.config.data_root = "/tmp/test_data"
        
        handler = MediaHandler(mock_denidin)
        
        # Extractor returns failed extraction
        mock_failed_result = {
            "raw_response": "",
            "document_analysis": None,
            "extraction_quality": "failed",
            "warnings": ["Corrupted file or unreadable format"],
            "model_used": "gpt-4o"
        }
        
        handler.image_extractor = Mock()
        handler.image_extractor.analyze_media = Mock(return_value=mock_failed_result)
        
        handler.media_file_manager = Mock()
        handler.media_file_manager.download_file = Mock(return_value=(b"corrupted_data", True))
        handler.media_file_manager.validate_file_size = Mock(return_value=None)
        handler.media_file_manager.validate_format = Mock(return_value="image")
        handler.media_file_manager.create_storage_path = Mock(return_value=Path("/tmp/media"))
        handler.media_file_manager.save_file = Mock(return_value=Path("/tmp/media/DD-972501234567-uuid.jpg"))
        
        result = handler.process_media_message(
            file_url="https://example.com/corrupted.jpg",
            filename="corrupted.jpg",
            mime_type="image/jpeg",
            file_size=500000,
            sender_phone="972501234567"
        )
        
        assert result["success"] is False
        assert "Unable to analyze this file" in result["error_message"]
    
    def test_handle_empty_document(self):
        """
        Test empty document handling.
        
        Extractor returns: extracted_text="", warnings=["Document appears empty"]
        Maps to: CHK078 (empty files)
        """
        mock_denidin = Mock()
        mock_denidin.config.data_root = "/tmp/test_data"
        
        handler = MediaHandler(mock_denidin)
        
        mock_empty_result = {
            "raw_response": "",
            "document_analysis": None,
            "extraction_quality": "poor",
            "warnings": ["Document appears empty"],
            "model_used": "python-docx"
        }
        
        handler.docx_extractor = Mock()
        handler.docx_extractor.analyze_media = Mock(return_value=mock_empty_result)
        
        handler.media_file_manager = Mock()
        handler.media_file_manager.download_file = Mock(return_value=(b"empty_docx", True))
        handler.media_file_manager.validate_file_size = Mock(return_value=None)
        handler.media_file_manager.validate_format = Mock(return_value="docx")
        handler.media_file_manager.create_storage_path = Mock(return_value=Path("/tmp/media"))
        handler.media_file_manager.save_file = Mock(return_value=Path("/tmp/media/DD-972501234567-uuid.docx"))
        
        result = handler.process_media_message(
            file_url="https://example.com/empty.docx",
            filename="empty.docx",
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            file_size=5000,
            sender_phone="972501234567"
        )
        
        assert result["success"] is False
        assert "unable to analyze" in result["error_message"].lower()
    
    def test_handle_zero_byte_file(self):
        """
        Test zero-byte file rejection.
        
        File size: 0 bytes → immediate error (no download).
        Maps to: CHK075 (zero-byte edge case)
        """
        mock_denidin = Mock()
        mock_denidin.config.data_root = "/tmp/test_data"
        handler = MediaHandler(mock_denidin)
        
        handler.media_file_manager = Mock()
        handler.media_file_manager.validate_file_size = Mock(
            side_effect=ValueError("File is empty (0 bytes)")
        )
        
        result = handler.process_media_message(
            file_url="https://example.com/zero.jpg",
            filename="zero.jpg",
            mime_type="image/jpeg",
            file_size=0,
            sender_phone="972501234567"
        )
        
        assert result["success"] is False
        # Generic error message returned when validation fails
        assert "Unable to process" in result["error_message"]
    
    def test_route_to_correct_extractor_by_type(self):
        """
        Test routing logic to correct extractor based on media_type.
        
        - media_type='image' → ImageExtractor
        - media_type='pdf' → PDFExtractor  
        - media_type='docx' → DOCXExtractor
        
        Maps to: File type routing
        """
        mock_denidin = Mock()
        mock_denidin.config.data_root = "/tmp/test_data"
        
        handler = MediaHandler(mock_denidin)
        
        # Mock all extractors
        handler.image_extractor = Mock()
        handler.pdf_extractor = Mock()
        handler.docx_extractor = Mock()
        
        mock_result = {
            "raw_response": "text",
            "document_analysis": {"document_type": "generic", "summary": "doc", "key_points": []},
            "extraction_quality": "high",
            "warnings": [],
            "model_used": "test"
        }
        
        handler.image_extractor.analyze_media = Mock(return_value=mock_result)
        handler.pdf_extractor.analyze_media = Mock(return_value=mock_result)
        handler.docx_extractor.analyze_media = Mock(return_value=mock_result)
        
        handler.media_file_manager = Mock()
        handler.media_file_manager.download_file = Mock(return_value=(b"data", True))
        handler.media_file_manager.validate_file_size = Mock(return_value=None)
        handler.media_file_manager.create_storage_path = Mock(return_value=Path("/tmp/media"))
        handler.media_file_manager.save_file = Mock(return_value=Path("/tmp/media/file"))
        handler.media_file_manager.save_rawtext = Mock(return_value=Path("/tmp/media/file.rawtext"))
        
        # Test image routing
        handler.media_file_manager.validate_format = Mock(return_value="image")
        handler.process_media_message("url", "file.jpg", "image/jpeg", 1000, "972501234567")
        handler.image_extractor.analyze_media.assert_called_once()
        
        # Test PDF routing
        handler.image_extractor.analyze_media.reset_mock()
        handler.media_file_manager.validate_format = Mock(return_value="pdf")
        handler.process_media_message("url", "file.pdf", "application/pdf", 1000, "972501234567")
        handler.pdf_extractor.analyze_media.assert_called_once()
        
        # Test DOCX routing
        handler.pdf_extractor.analyze_media.reset_mock()
        handler.media_file_manager.validate_format = Mock(return_value="docx")
        handler.process_media_message("url", "file.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", 1000, "972501234567")
        handler.docx_extractor.analyze_media.assert_called_once()
