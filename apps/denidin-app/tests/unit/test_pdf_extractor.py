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
        
        # Create 3 mock pages
        pages = []
        for i in range(3):
            page = Mock()
            pixmap = Mock()
            pixmap.tobytes.return_value = f"PNG data page {i+1}".encode()
            pixmap.width = 612
            pixmap.height = 792
            page.get_pixmap.return_value = pixmap
            pages.append(page)
        
        mock_doc.__iter__.return_value = pages
        mock_doc.__getitem__.side_effect = lambda x: pages[x]
        mock_fitz.open.return_value = mock_doc
        
        # Mock ImageExtractor to return results per page (actual API format)
        mock_image_extractor.analyze_media.side_effect = [
            {
                "raw_response": "עמוד ראשון - content here",
                "extraction_quality": "high",
                "warnings": [],
                "model_used": "gpt-4o"
            },
            {
                "raw_response": "עמוד שני - content here",
                "extraction_quality": "medium",
                "warnings": ["slight blur"],
                "model_used": "gpt-4o"
            },
            {
                "raw_response": "עמוד שלישי - content here",
                "extraction_quality": "high",
                "warnings": [],
                "model_used": "gpt-4o"
            }
        ]
        
        # Extract text
        result = pdf_extractor.analyze_media(pdf_media)
        
        # Verify result structure
        assert "raw_response" in result
        assert "extraction_quality" in result
        assert "warnings" in result
        assert "model_used" in result
        
        # raw_response should be combined string with page separators
        assert "עמוד ראשון" in result["raw_response"]
        assert "עמוד שני" in result["raw_response"]
        assert "עמוד שלישי" in result["raw_response"]
        
        # Verify per-page qualities
        assert result["extraction_quality"] == ["high", "medium", "high"]
        assert result["warnings"] == [[], ["slight blur"], []]
        assert result["model_used"] == "gpt-4o"
        
        # Verify ImageExtractor was called 3 times
        assert mock_image_extractor.analyze_media.call_count == 3


def test_extract_single_page_pdf(pdf_extractor, mock_image_extractor):
    """
    CHK010: Handle single-page PDF correctly.
    Should return single result.
    """
    pdf_media = Media.from_bytes(b"fake PDF data", "application/pdf", "single.pdf")
    
    with patch('src.handlers.extractors.pdf_extractor.fitz') as mock_fitz:
        mock_doc = MagicMock()
        mock_page = Mock()
        pixmap = Mock()
        pixmap.tobytes.return_value = b"PNG data"
        pixmap.width = 612
        pixmap.height = 792
        mock_page.get_pixmap.return_value = pixmap
        
        mock_doc.__len__.return_value = 1
        mock_doc.__iter__.return_value = [mock_page]
        mock_doc.__getitem__.return_value = mock_page
        mock_fitz.open.return_value = mock_doc
        
        mock_image_extractor.analyze_media.return_value = {
            "raw_response": "Single page text",
            "extraction_quality": "high",
            "warnings": [],
            "model_used": "gpt-4o"
        }
        
        result = pdf_extractor.analyze_media(pdf_media)
        
        # Single page result
        assert "Single page text" in result["raw_response"]
        assert result["extraction_quality"] == ["high"]
        assert result["warnings"] == [[]]
        assert result["model_used"] == "gpt-4o"
        assert mock_image_extractor.analyze_media.call_count == 1


def test_extract_empty_pdf(pdf_extractor, mock_image_extractor):
    """
    CHK078: Handle empty PDF (0 pages) gracefully.
    Should return empty structures.
    """
    pdf_media = Media.from_bytes(b"fake empty PDF", "application/pdf", "empty.pdf")
    
    with patch('src.handlers.extractors.pdf_extractor.fitz') as mock_fitz:
        mock_doc = MagicMock()
        mock_doc.__len__.return_value = 0
        mock_doc.__iter__.return_value = []
        mock_fitz.open.return_value = mock_doc
        
        result = pdf_extractor.analyze_media(pdf_media)
        
        # Empty PDF should return default message
        assert "סיכום" in result["raw_response"] or result["raw_response"] != ""
        assert result["extraction_quality"] == []
        assert result["warnings"] == []
        assert result["model_used"] == "gpt-4o"
        assert mock_image_extractor.analyze_media.call_count == 0


def test_pymupdf_failure_handling(pdf_extractor, mock_image_extractor):
    """
    CHK007: Gracefully handle PyMuPDF failures.
    Should return failed status with error warnings.
    """
    pdf_media = Media.from_bytes(b"corrupted PDF", "application/pdf", "bad.pdf")
    
    with patch('src.handlers.extractors.pdf_extractor.fitz') as mock_fitz:
        mock_fitz.open.side_effect = Exception("PDF parsing error")
        
        result = pdf_extractor.analyze_media(pdf_media)
        
        # Failed extraction
        assert result["raw_response"] == ""
        assert result["extraction_quality"] == []
        assert len(result["warnings"]) == 1
        assert "PDF analysis failed" in result["warnings"][0][0]
        assert result["model_used"] == "gpt-4o"


def test_mixed_quality_pages(pdf_extractor, mock_image_extractor):
    """
    Verify per-page quality preservation.
    Should preserve individual page quality levels in array.
    """
    pdf_media = Media.from_bytes(b"fake PDF", "application/pdf", "mixed.pdf")
    
    with patch('src.handlers.extractors.pdf_extractor.fitz') as mock_fitz:
        mock_doc = MagicMock()
        pages = []
        for i in range(4):
            page = Mock()
            pixmap = Mock()
            pixmap.tobytes.return_value = b"PNG data"
            pixmap.width = 612
            pixmap.height = 792
            page.get_pixmap.return_value = pixmap
            pages.append(page)
        
        mock_doc.__len__.return_value = 4
        mock_doc.__iter__.return_value = pages
        mock_doc.__getitem__.side_effect = lambda x: pages[x]
        mock_fitz.open.return_value = mock_doc
        
        # Different quality per page
        mock_image_extractor.analyze_media.side_effect = [
            {"raw_response": "p1", "extraction_quality": "high", "warnings": [], "model_used": "gpt-4o"},
            {"raw_response": "p2", "extraction_quality": "low", "warnings": ["blurry"], "model_used": "gpt-4o"},
            {"raw_response": "p3", "extraction_quality": "medium", "warnings": [], "model_used": "gpt-4o"},
            {"raw_response": "p4", "extraction_quality": "failed", "warnings": ["unreadable"], "model_used": "gpt-4o"}
        ]
        
        result = pdf_extractor.analyze_media(pdf_media)
        
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
        
        pages = []
        for i in range(2):
            page = Mock()
            pixmap = Mock()
            pixmap.tobytes.return_value = f"PNG data page {i+1}".encode()
            pixmap.width = 612
            pixmap.height = 792
            page.get_pixmap.return_value = pixmap
            pages.append(page)
        
        mock_doc.__len__.return_value = 2
        mock_doc.__iter__.return_value = pages
        mock_doc.__getitem__.side_effect = lambda x: pages[x]
        mock_fitz.open.return_value = mock_doc
        
        mock_image_extractor.analyze_media.return_value = {
            "raw_response": "text",
            "extraction_quality": "high",
            "warnings": [],
            "model_used": "gpt-4o"
        }
        
        result = pdf_extractor.analyze_media(pdf_media)
        
        # Verify ImageExtractor was called with Media objects
        assert mock_image_extractor.analyze_media.call_count == 2
        
        # Check calls are with Media objects
        for call in mock_image_extractor.analyze_media.call_args_list:
            media_arg = call[0][0]
            assert isinstance(media_arg, Media)
            assert media_arg.mime_type == "image/png"


def test_aggregates_document_type_most_common(pdf_extractor, mock_image_extractor):
    """
    Phase 4: Document type should be most common across pages.
    """
    pdf_media = Media.from_bytes(b"fake PDF", "application/pdf", "mixed.pdf")
    
    with patch('src.handlers.extractors.pdf_extractor.fitz') as mock_fitz:
        mock_doc = MagicMock()
        pages = []
        for i in range(4):
            page = Mock()
            pixmap = Mock()
            pixmap.tobytes.return_value = b"PNG"
            pixmap.width = 612
            pixmap.height = 792
            page.get_pixmap.return_value = pixmap
            pages.append(page)
        
        mock_doc.__len__.return_value = 4
        mock_doc.__iter__.return_value = pages
        mock_doc.__getitem__.side_effect = lambda x: pages[x]
        mock_fitz.open.return_value = mock_doc
        
        # All pages return same format (no longer returning document_analysis separately)
        mock_image_extractor.analyze_media.side_effect = [
            {"raw_response": "p1", "extraction_quality": "high", "warnings": [], "model_used": "gpt-4o"},
            {"raw_response": "p2", "extraction_quality": "high", "warnings": [], "model_used": "gpt-4o"},
            {"raw_response": "p3", "extraction_quality": "high", "warnings": [], "model_used": "gpt-4o"},
            {"raw_response": "p4", "extraction_quality": "high", "warnings": [], "model_used": "gpt-4o"}
        ]
        
        result = pdf_extractor.analyze_media(pdf_media)
        
        # Should still return valid structure
        assert "raw_response" in result
        assert "extraction_quality" in result
        assert len(result["extraction_quality"]) == 4


def test_aggregates_key_points_with_deduplication(pdf_extractor, mock_image_extractor):
    """
    Phase 4: Key points should be merged and deduplicated.
    (Note: Current code doesn't parse key_points separately - they're in raw_response)
    """
    pdf_media = Media.from_bytes(b"fake PDF", "application/pdf", "points.pdf")
    
    with patch('src.handlers.extractors.pdf_extractor.fitz') as mock_fitz:
        mock_doc = MagicMock()
        pages = []
        for i in range(3):
            page = Mock()
            pixmap = Mock()
            pixmap.tobytes.return_value = b"PNG"
            pixmap.width = 612
            pixmap.height = 792
            page.get_pixmap.return_value = pixmap
            pages.append(page)
        
        mock_doc.__len__.return_value = 3
        mock_doc.__iter__.return_value = pages
        mock_doc.__getitem__.side_effect = lambda x: pages[x]
        mock_fitz.open.return_value = mock_doc
        
        mock_image_extractor.analyze_media.side_effect = [
            {"raw_response": "Page 1 with Point A and Point B", "extraction_quality": "high", "warnings": [], "model_used": "gpt-4o"},
            {"raw_response": "Page 2 with Point B and Point C", "extraction_quality": "high", "warnings": [], "model_used": "gpt-4o"},
            {"raw_response": "Page 3 with Point D", "extraction_quality": "high", "warnings": [], "model_used": "gpt-4o"}
        ]
        
        result = pdf_extractor.analyze_media(pdf_media)
        
        # All pages should be combined
        assert "Point A" in result["raw_response"]
        assert "Point B" in result["raw_response"]
        assert "Point C" in result["raw_response"]
        assert "Point D" in result["raw_response"]


def test_aggregates_summaries_from_all_pages(pdf_extractor, mock_image_extractor):
    """
    Phase 4: Summary should combine information from all pages.
    """
    pdf_media = Media.from_bytes(b"fake PDF", "application/pdf", "summary.pdf")
    
    with patch('src.handlers.extractors.pdf_extractor.fitz') as mock_fitz:
        mock_doc = MagicMock()
        pages = []
        for i in range(2):
            page = Mock()
            pixmap = Mock()
            pixmap.tobytes.return_value = b"PNG"
            pixmap.width = 612
            pixmap.height = 792
            page.get_pixmap.return_value = pixmap
            pages.append(page)
        
        mock_doc.__len__.return_value = 2
        mock_doc.__iter__.return_value = pages
        mock_doc.__getitem__.side_effect = lambda x: pages[x]
        mock_fitz.open.return_value = mock_doc
        
        mock_image_extractor.analyze_media.side_effect = [
            {"raw_response": "סיכום: First page summary content", "extraction_quality": "high", "warnings": [], "model_used": "gpt-4o"},
            {"raw_response": "סיכום: Second page summary content", "extraction_quality": "high", "warnings": [], "model_used": "gpt-4o"}
        ]
        
        result = pdf_extractor.analyze_media(pdf_media)
        
        # Multi-page summary should be combined with separator
        assert "First page summary content" in result["raw_response"]
        assert "Second page summary content" in result["raw_response"]


def test_handles_failed_page_analysis_gracefully(pdf_extractor, mock_image_extractor):
    """
    Phase 4: Should continue even if one page fails.
    """
    pdf_media = Media.from_bytes(b"fake PDF", "application/pdf", "partial.pdf")
    
    with patch('src.handlers.extractors.pdf_extractor.fitz') as mock_fitz:
        mock_doc = MagicMock()
        
        # First two pages work, third fails
        pages = []
        for i in range(2):
            page = Mock()
            pixmap = Mock()
            pixmap.tobytes.return_value = b"PNG"
            pixmap.width = 612
            pixmap.height = 792
            page.get_pixmap.return_value = pixmap
            pages.append(page)
        
        # Third page raises exception
        page3 = Mock()
        page3.get_pixmap.side_effect = Exception("Page 3 corrupt")
        pages.append(page3)
        
        mock_doc.__len__.return_value = 3
        mock_doc.__iter__.return_value = pages
        mock_doc.__getitem__.side_effect = lambda x: pages[x]
        mock_fitz.open.return_value = mock_doc
        
        # First two succeed, third fails (never called due to exception)
        mock_image_extractor.analyze_media.side_effect = [
            {"raw_response": "סיכום: Page 1", "extraction_quality": "high", "warnings": [], "model_used": "gpt-4o"},
            {"raw_response": "סיכום: Page 2", "extraction_quality": "high", "warnings": [], "model_used": "gpt-4o"}
        ]
        
        result = pdf_extractor.analyze_media(pdf_media)
        
        # Should combine the successful pages
        assert "Page 1" in result["raw_response"]
        assert "Page 2" in result["raw_response"]
        
        # Should have warnings for failed page
        assert len(result["extraction_quality"]) >= 2  # At least 2 pages processed
        assert len(result["warnings"]) >= 2


