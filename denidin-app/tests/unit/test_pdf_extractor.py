"""
Unit tests for PDF Text Extractor (Feature 003 Phase 3.2)

CHK Requirements:
- CHK006: Hebrew text extraction required
- CHK007: Graceful degradation on extraction failures
- CHK008: Mixed Hebrew/English support
- CHK010: Layout/structure preservation
- CHK078: Empty document handling
"""
import pytest
from unittest.mock import Mock, MagicMock, patch
from src.utils.extractors.pdf_extractor import PDFExtractor
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
    with patch('src.utils.extractors.pdf_extractor.ImageExtractor', return_value=mock_image_extractor):
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
    with patch('src.utils.extractors.pdf_extractor.fitz') as mock_fitz:
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
                "extraction_quality": "high",
                "warnings": [],
                "model_used": "gpt-4o"
            },
            {
                "extracted_text": "עמוד שני",
                "extraction_quality": "medium",
                "warnings": ["AI notes: slight blur"],
                "model_used": "gpt-4o"
            },
            {
                "extracted_text": "עמוד שלישי",
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
        
        # Verify ImageExtractor was called 3 times
        assert mock_image_extractor.extract_text.call_count == 3


def test_extract_single_page_pdf(pdf_extractor, mock_image_extractor):
    """
    CHK010: Handle single-page PDF correctly.
    Should return single-element arrays.
    """
    pdf_media = Media.from_bytes(b"fake PDF data", "application/pdf", "single.pdf")
    
    with patch('src.utils.extractors.pdf_extractor.fitz') as mock_fitz:
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
        assert mock_image_extractor.extract_text.call_count == 1


def test_extract_empty_pdf(pdf_extractor, mock_image_extractor):
    """
    CHK078: Handle empty PDF (0 pages) gracefully.
    Should return empty arrays.
    """
    pdf_media = Media.from_bytes(b"fake empty PDF", "application/pdf", "empty.pdf")
    
    with patch('src.utils.extractors.pdf_extractor.fitz') as mock_fitz:
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
        assert mock_image_extractor.extract_text.call_count == 0


def test_pymupdf_failure_handling(pdf_extractor, mock_image_extractor):
    """
    CHK007: Gracefully handle PyMuPDF failures.
    Should return failed status with error warnings.
    """
    pdf_media = Media.from_bytes(b"corrupted PDF", "application/pdf", "bad.pdf")
    
    with patch('src.utils.extractors.pdf_extractor.fitz') as mock_fitz:
        mock_fitz.open.side_effect = Exception("PDF parsing error")
        
        result = pdf_extractor.extract_text(pdf_media)
        
        # Failed extraction
        assert result["extracted_text"] == []
        assert result["extraction_quality"] == []
        assert len(result["warnings"]) == 1
        assert len(result["warnings"][0]) == 1
        assert "PDF parsing error" in result["warnings"][0][0]
        assert result["model_used"] == "gpt-4o"


def test_mixed_quality_pages(pdf_extractor, mock_image_extractor):
    """
    Verify per-page quality preservation.
    Should preserve individual page quality levels in array.
    """
    pdf_media = Media.from_bytes(b"fake PDF", "application/pdf", "mixed.pdf")
    
    with patch('src.utils.extractors.pdf_extractor.fitz') as mock_fitz:
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
            {"extracted_text": "p1", "extraction_quality": "high", "warnings": [], "model_used": "gpt-4o"},
            {"extracted_text": "p2", "extraction_quality": "low", "warnings": ["blurry"], "model_used": "gpt-4o"},
            {"extracted_text": "p3", "extraction_quality": "medium", "warnings": [], "model_used": "gpt-4o"},
            {"extracted_text": "p4", "extraction_quality": "failed", "warnings": ["unreadable"], "model_used": "gpt-4o"}
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
    
    with patch('src.utils.extractors.pdf_extractor.fitz') as mock_fitz:
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
