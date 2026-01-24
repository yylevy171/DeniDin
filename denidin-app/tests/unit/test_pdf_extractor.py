"""
Unit tests for PDF Text Extractor (Feature 003 Phase 3.2 + Phase 4)

CHK Requirements:
- CHK006: Hebrew text extraction required
- CHK007: Graceful degradation on extraction failures
- CHK008: Mixed Hebrew/English support
- CHK010: Layout/structure preservation
- CHK078: Empty document handling

Phase 4: Document analysis aggregation from multiple pages
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from src.handlers.extractors.pdf_extractor import PDFExtractor
from src.models.media import Media


@pytest.fixture
def mock_denidin_context():
    """Create mock DeniDin context."""
    context = Mock()
    context.ai_handler = Mock()
    context.config = Mock()
    context.config.ai_vision_model = "gpt-4o"
    return context


@pytest.fixture
def mock_image_extractor():
    """Create mock ImageExtractor."""
    extractor = Mock()
    return extractor


@pytest.fixture
def pdf_extractor(mock_denidin_context, mock_image_extractor):
    """Create PDFExtractor with mocked dependencies."""
    with patch('src.handlers.extractors.pdf_extractor.ImageExtractor', return_value=mock_image_extractor):
        extractor = PDFExtractor(mock_denidin_context)
    return extractor


def test_extract_hebrew_multipage_pdf(pdf_extractor, mock_image_extractor):
    """
    CHK006, CHK008: Extract Hebrew text from multi-page PDF.
    Should convert each page to image and delegate to ImageExtractor.
    """
    # Create fake PDF media
    pdf_media = Media.from_bytes(b"fake PDF data", "application/pdf", "test.pdf")
    
    # Mock PyMuPDF to return 3 pages
    with patch('src.handlers.extractors.pdf_extractor.fitz') as mock_fitz:
        mock_doc = MagicMock()
        mock_doc.__len__.return_value = 3
        mock_doc.__iter__.return_value = [Mock(), Mock(), Mock()]
        
        # Mock page.get_pixmap() to return fake image data
        for page in mock_doc:
            mock_pixmap = Mock()
            mock_pixmap.tobytes.return_value = b"fake PNG data"
            page.get_pixmap.return_value = mock_pixmap
        
        mock_fitz.open.return_value = mock_doc
        
        # Mock ImageExtractor to return different results per page
        mock_image_extractor.extract_text.side_effect = [
            {
                "extracted_text": "עמוד ראשון",
                "document_analysis": {
                    "document_type": "receipt",
                    "summary": "Page 1 summary",
                    "key_points": ["Point A", "Point B"]
                },
                "extraction_quality": "high",
                "warnings": [],
                "model_used": "gpt-4o"
            },
            {
                "extracted_text": "עמוד שני",
                "document_analysis": {
                    "document_type": "receipt",
                    "summary": "Page 2 summary",
                    "key_points": ["Point C", "Point A"]  # Duplicate "Point A"
                },
                "extraction_quality": "medium",
                "warnings": ["AI notes: slight blur"],
                "model_used": "gpt-4o"
            },
            {
                "extracted_text": "עמוד שלישי",
                "document_analysis": {
                    "document_type": "receipt",
                    "summary": "Page 3 summary",
                    "key_points": ["Point D"]
                },
                "extraction_quality": "high",
                "warnings": [],
                "model_used": "gpt-4o"
            }
        ]
        
        # Extract text
        result = pdf_extractor.extract_text(pdf_media)
        
        # Verify per-page arrays
        assert result["extracted_text"] == ["עמוד ראשון", "עמוד שני", "עמוד שלישי"]
        assert result["extraction_quality"] == ["high", "medium", "high"]
        assert result["warnings"] == [[], ["AI notes: slight blur"], []]
        assert result["model_used"] == "gpt-4o"
        
        # Phase 4: Verify document analysis aggregation
        assert "document_analysis" in result
        analysis = result["document_analysis"]
        assert analysis["document_type"] == "receipt"  # Most common type
        assert "Page 1 summary" in analysis["summary"]
        assert "Page 2 summary" in analysis["summary"]
        assert "Page 3 summary" in analysis["summary"]
        # Key points should be deduplicated
        assert "Point A" in analysis["key_points"]
        assert "Point B" in analysis["key_points"]
        assert "Point C" in analysis["key_points"]
        assert "Point D" in analysis["key_points"]
        # "Point A" should appear only once despite being in 2 pages
        assert analysis["key_points"].count("Point A") == 1
        
        # Verify ImageExtractor was called 3 times
        assert mock_image_extractor.extract_text.call_count == 3


def test_extract_single_page_pdf(pdf_extractor, mock_image_extractor):
    """
    CHK010: Handle single-page PDF correctly.
    Should return single-element arrays.
    """
    pdf_media = Media.from_bytes(b"fake PDF data", "application/pdf", "single.pdf")
    
    with patch('src.handlers.extractors.pdf_extractor.fitz') as mock_fitz:
        mock_doc = MagicMock()
        mock_doc.__len__.return_value = 1
        mock_page = Mock()
        mock_pixmap = Mock()
        mock_pixmap.tobytes.return_value = b"fake PNG data"
        mock_page.get_pixmap.return_value = mock_pixmap
        mock_doc.__iter__.return_value = [mock_page]
        mock_fitz.open.return_value = mock_doc
        
        mock_image_extractor.extract_text.return_value = {
            "extracted_text": "Single page text",
            "document_analysis": {
                "document_type": "generic",
                "summary": "Single page summary",
                "key_points": ["Point X"]
            },
            "extraction_quality": "high",
            "warnings": [],
            "model_used": "gpt-4o"
        }
        
        result = pdf_extractor.extract_text(pdf_media)
        
        # Single-element arrays
        assert result["extracted_text"] == ["Single page text"]
        assert result["extraction_quality"] == ["high"]
        assert result["warnings"] == [[]]
        assert result["model_used"] == "gpt-4o"
        
        # Phase 4: Single page analysis passed through directly
        assert result["document_analysis"]["document_type"] == "generic"
        assert result["document_analysis"]["summary"] == "Single page summary"
        assert result["document_analysis"]["key_points"] == ["Point X"]
        assert mock_image_extractor.extract_text.call_count == 1


def test_extract_empty_pdf(pdf_extractor, mock_image_extractor):
    """
    CHK078: Handle empty PDF (0 pages) gracefully.
    Should return empty arrays.
    """
    pdf_media = Media.from_bytes(b"fake empty PDF", "application/pdf", "empty.pdf")
    
    with patch('src.handlers.extractors.pdf_extractor.fitz') as mock_fitz:
        mock_doc = MagicMock()
        mock_doc.__len__.return_value = 0
        mock_doc.__iter__.return_value = []
        mock_fitz.open.return_value = mock_doc
        
        result = pdf_extractor.extract_text(pdf_media)
        
        # Empty arrays for empty PDF
        assert result["extracted_text"] == []
        assert result["extraction_quality"] == []
        assert result["warnings"] == []
        assert result["model_used"] == "gpt-4o"
        
        # Phase 4: Empty PDF has generic document_analysis
        assert result["document_analysis"]["document_type"] == "generic"
        assert "Empty PDF document" in result["document_analysis"]["summary"]
        assert result["document_analysis"]["key_points"] == []
        assert mock_image_extractor.extract_text.call_count == 0


def test_pymupdf_failure_handling(pdf_extractor, mock_image_extractor):
    """
    CHK007: Gracefully handle PyMuPDF failures.
    Should return failed status with error warnings.
    """
    pdf_media = Media.from_bytes(b"corrupted PDF", "application/pdf", "bad.pdf")
    
    with patch('src.handlers.extractors.pdf_extractor.fitz') as mock_fitz:
        mock_fitz.open.side_effect = Exception("PDF parsing error")
        
        result = pdf_extractor.extract_text(pdf_media)
        
        # Failed extraction
        assert result["extracted_text"] == []
        assert result["extraction_quality"] == []
        assert len(result["warnings"]) == 1
        assert len(result["warnings"][0]) == 1
        assert "PDF parsing error" in result["warnings"][0][0]
        assert result["model_used"] == "gpt-4o"
        
        # Phase 4: Failed extraction has generic document_analysis
        assert result["document_analysis"]["document_type"] == "generic"
        assert "PDF analysis failed" in result["document_analysis"]["summary"]


def test_mixed_quality_pages(pdf_extractor, mock_image_extractor):
    """
    Verify per-page quality preservation.
    Should preserve individual page quality levels in array.
    """
    pdf_media = Media.from_bytes(b"fake PDF", "application/pdf", "mixed.pdf")
    
    with patch('src.handlers.extractors.pdf_extractor.fitz') as mock_fitz:
        mock_doc = MagicMock()
        mock_doc.__len__.return_value = 4
        mock_doc.__iter__.return_value = [Mock(), Mock(), Mock(), Mock()]
        
        for page in mock_doc:
            mock_pixmap = Mock()
            mock_pixmap.tobytes.return_value = b"fake PNG"
            page.get_pixmap.return_value = mock_pixmap
        
        mock_fitz.open.return_value = mock_doc
        
        # Different quality per page
        mock_image_extractor.extract_text.side_effect = [
            {"extracted_text": "p1", "document_analysis": {"document_type": "generic", "summary": "s1", "key_points": []}, "extraction_quality": "high", "warnings": [], "model_used": "gpt-4o"},
            {"extracted_text": "p2", "document_analysis": {"document_type": "generic", "summary": "s2", "key_points": []}, "extraction_quality": "low", "warnings": ["blurry"], "model_used": "gpt-4o"},
            {"extracted_text": "p3", "document_analysis": {"document_type": "generic", "summary": "s3", "key_points": []}, "extraction_quality": "medium", "warnings": [], "model_used": "gpt-4o"},
            {"extracted_text": "p4", "document_analysis": {"document_type": "generic", "summary": "s4", "key_points": []}, "extraction_quality": "failed", "warnings": ["unreadable"], "model_used": "gpt-4o"}
        ]
        
        result = pdf_extractor.extract_text(pdf_media)
        
        # Preserve per-page quality
        assert result["extraction_quality"] == ["high", "low", "medium", "failed"]
        assert result["warnings"] == [[], ["blurry"], [], ["unreadable"]]


def test_image_extractor_delegation(pdf_extractor, mock_image_extractor):
    """
    Verify that ImageExtractor is called with correct Media objects.
    Each page should be converted to image/png Media.
    """
    pdf_media = Media.from_bytes(b"fake PDF", "application/pdf", "test.pdf")
    
    with patch('src.handlers.extractors.pdf_extractor.fitz') as mock_fitz:
        mock_doc = MagicMock()
        mock_doc.__len__.return_value = 2
        mock_page1, mock_page2 = Mock(), Mock()
        
        mock_pixmap1 = Mock()
        mock_pixmap1.tobytes.return_value = b"PNG data page 1"
        mock_page1.get_pixmap.return_value = mock_pixmap1
        
        mock_pixmap2 = Mock()
        mock_pixmap2.tobytes.return_value = b"PNG data page 2"
        mock_page2.get_pixmap.return_value = mock_pixmap2
        
        mock_doc.__iter__.return_value = [mock_page1, mock_page2]
        mock_fitz.open.return_value = mock_doc
        
        mock_image_extractor.extract_text.return_value = {
            "extracted_text": "text",
            "document_analysis": {
                "document_type": "generic",
                "summary": "test summary",
                "key_points": []
            },
            "extraction_quality": "high",
            "warnings": [],
            "model_used": "gpt-4o"
        }
        
        result = pdf_extractor.extract_text(pdf_media)
        
        # Verify ImageExtractor was called with Media objects
        assert mock_image_extractor.extract_text.call_count == 2
        
        # Check first call - should be Media with PNG data
        first_call_media = mock_image_extractor.extract_text.call_args_list[0][0][0]
        assert isinstance(first_call_media, Media)
        assert first_call_media.mime_type == "image/png"
        assert first_call_media.data == b"PNG data page 1"
        
        # Check second call
        second_call_media = mock_image_extractor.extract_text.call_args_list[1][0][0]
        assert isinstance(second_call_media, Media)
        assert second_call_media.mime_type == "image/png"
        assert second_call_media.data == b"PNG data page 2"


# ===== Phase 4: Document Analysis Aggregation Tests =====

def test_aggregates_document_type_most_common(pdf_extractor, mock_image_extractor):
    """
    Phase 4: Document type should be most common across pages.
    """
    pdf_media = Media.from_bytes(b"fake PDF", "application/pdf", "mixed.pdf")
    
    with patch('src.handlers.extractors.pdf_extractor.fitz') as mock_fitz:
        mock_doc = MagicMock()
        mock_doc.__len__.return_value = 4
        mock_doc.__iter__.return_value = [Mock(), Mock(), Mock(), Mock()]
        
        for page in mock_doc:
            mock_pixmap = Mock()
            mock_pixmap.tobytes.return_value = b"fake PNG"
            page.get_pixmap.return_value = mock_pixmap
        
        mock_fitz.open.return_value = mock_doc
        
        # Pages 1,2,4 are invoices, page 3 is receipt
        mock_image_extractor.extract_text.side_effect = [
            {"extracted_text": "p1", "document_analysis": {"document_type": "invoice", "summary": "s1", "key_points": []}, "extraction_quality": "high", "warnings": [], "model_used": "gpt-4o"},
            {"extracted_text": "p2", "document_analysis": {"document_type": "invoice", "summary": "s2", "key_points": []}, "extraction_quality": "high", "warnings": [], "model_used": "gpt-4o"},
            {"extracted_text": "p3", "document_analysis": {"document_type": "receipt", "summary": "s3", "key_points": []}, "extraction_quality": "high", "warnings": [], "model_used": "gpt-4o"},
            {"extracted_text": "p4", "document_analysis": {"document_type": "invoice", "summary": "s4", "key_points": []}, "extraction_quality": "high", "warnings": [], "model_used": "gpt-4o"}
        ]
        
        result = pdf_extractor.extract_text(pdf_media)
        
        # Most common type is "invoice" (3 out of 4)
        assert result["document_analysis"]["document_type"] == "invoice"


def test_aggregates_key_points_with_deduplication(pdf_extractor, mock_image_extractor):
    """
    Phase 4: Key points should be merged and deduplicated.
    """
    pdf_media = Media.from_bytes(b"fake PDF", "application/pdf", "points.pdf")
    
    with patch('src.handlers.extractors.pdf_extractor.fitz') as mock_fitz:
        mock_doc = MagicMock()
        mock_doc.__len__.return_value = 3
        mock_doc.__iter__.return_value = [Mock(), Mock(), Mock()]
        
        for page in mock_doc:
            mock_pixmap = Mock()
            mock_pixmap.tobytes.return_value = b"fake PNG"
            page.get_pixmap.return_value = mock_pixmap
        
        mock_fitz.open.return_value = mock_doc
        
        mock_image_extractor.extract_text.side_effect = [
            {"extracted_text": "p1", "document_analysis": {"document_type": "generic", "summary": "s1", "key_points": ["Point A", "Point B"]}, "extraction_quality": "high", "warnings": [], "model_used": "gpt-4o"},
            {"extracted_text": "p2", "document_analysis": {"document_type": "generic", "summary": "s2", "key_points": ["Point B", "Point C", "point a"]}, "extraction_quality": "high", "warnings": [], "model_used": "gpt-4o"},  # "point a" is duplicate of "Point A"
            {"extracted_text": "p3", "document_analysis": {"document_type": "generic", "summary": "s3", "key_points": ["Point D"]}, "extraction_quality": "high", "warnings": [], "model_used": "gpt-4o"}
        ]
        
        result = pdf_extractor.extract_text(pdf_media)
        
        key_points = result["document_analysis"]["key_points"]
        
        # Should have Point A, Point B, Point C, Point D
        # "point a" should be deduplicated (case-insensitive)
        assert "Point A" in key_points or "point a" in key_points  # One of them
        assert "Point B" in key_points
        assert "Point C" in key_points
        assert "Point D" in key_points
        
        # Count: should be 4-5 points (depending on case sensitivity)
        # But definitely NOT 6 (which would mean no deduplication)
        assert len(key_points) <= 5


def test_aggregates_summaries_from_all_pages(pdf_extractor, mock_image_extractor):
    """
    Phase 4: Summary should combine information from all pages.
    """
    pdf_media = Media.from_bytes(b"fake PDF", "application/pdf", "summary.pdf")
    
    with patch('src.handlers.extractors.pdf_extractor.fitz') as mock_fitz:
        mock_doc = MagicMock()
        mock_doc.__len__.return_value = 2
        mock_doc.__iter__.return_value = [Mock(), Mock()]
        
        for page in mock_doc:
            mock_pixmap = Mock()
            mock_pixmap.tobytes.return_value = b"fake PNG"
            page.get_pixmap.return_value = mock_pixmap
        
        mock_fitz.open.return_value = mock_doc
        
        mock_image_extractor.extract_text.side_effect = [
            {"extracted_text": "p1", "document_analysis": {"document_type": "generic", "summary": "First page summary", "key_points": []}, "extraction_quality": "high", "warnings": [], "model_used": "gpt-4o"},
            {"extracted_text": "p2", "document_analysis": {"document_type": "generic", "summary": "Second page summary", "key_points": []}, "extraction_quality": "high", "warnings": [], "model_used": "gpt-4o"}
        ]
        
        result = pdf_extractor.extract_text(pdf_media)
        
        summary = result["document_analysis"]["summary"]
        
        # Multi-page summary should include content from both pages
        assert "First page summary" in summary
        assert "Second page summary" in summary


def test_handles_failed_page_analysis_gracefully(pdf_extractor, mock_image_extractor):
    """
    Phase 4: Should aggregate only valid analyses, skip None/failed pages.
    """
    pdf_media = Media.from_bytes(b"fake PDF", "application/pdf", "partial.pdf")
    
    with patch('src.handlers.extractors.pdf_extractor.fitz') as mock_fitz:
        mock_doc = MagicMock()
        mock_doc.__len__.return_value = 3
        
        # Mock first two pages normally, third page fails
        mock_page1 = Mock()
        mock_pixmap1 = Mock()
        mock_pixmap1.tobytes.return_value = b"PNG1"
        mock_page1.get_pixmap.return_value = mock_pixmap1
        
        mock_page2 = Mock()
        mock_pixmap2 = Mock()
        mock_pixmap2.tobytes.return_value = b"PNG2"
        mock_page2.get_pixmap.return_value = mock_pixmap2
        
        mock_page3 = Mock()
        mock_page3.get_pixmap.side_effect = Exception("Page 3 corrupt")
        
        mock_doc.__iter__.return_value = [mock_page1, mock_page2, mock_page3]
        mock_fitz.open.return_value = mock_doc
        
        # First two pages succeed, third fails
        mock_image_extractor.extract_text.side_effect = [
            {"extracted_text": "p1", "document_analysis": {"document_type": "generic", "summary": "Page 1", "key_points": ["A"]}, "extraction_quality": "high", "warnings": [], "model_used": "gpt-4o"},
            {"extracted_text": "p2", "document_analysis": {"document_type": "generic", "summary": "Page 2", "key_points": ["B"]}, "extraction_quality": "high", "warnings": [], "model_used": "gpt-4o"}
        ]
        
        result = pdf_extractor.extract_text(pdf_media)
        
        # Should have 3 text entries (including failed page)
        assert len(result["extracted_text"]) == 3
        assert result["extracted_text"][2] == ""  # Failed page
        
        # But document analysis aggregates only successful pages
        analysis = result["document_analysis"]
        assert analysis["document_type"] == "generic"
        assert "Page 1" in analysis["summary"]
        assert "Page 2" in analysis["summary"]
        assert "A" in analysis["key_points"]
        assert "B" in analysis["key_points"]

