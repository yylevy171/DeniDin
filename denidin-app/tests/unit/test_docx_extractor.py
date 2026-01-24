"""
Unit tests for DOCX Extractor (Feature 003 Phase 3.3)

CHK Requirements:
- CHK005: Corrupted file handling
- CHK006: Hebrew text extraction
- CHK007: Graceful degradation on failures
- CHK010: Layout/structure preservation
- CHK078: Empty document handling
"""
import pytest
import io
from unittest.mock import Mock
from docx import Document
from src.utils.extractors.docx_extractor import DOCXExtractor
from src.models.media import Media


@pytest.fixture
def mock_denidin_context():
    """Create mock DeniDin context."""
    context = Mock()
    context.config = Mock()
    return context


@pytest.fixture
def docx_extractor(mock_denidin_context):
    """Create DOCXExtractor instance."""
    return DOCXExtractor(mock_denidin_context)


def create_docx_media(*paragraphs) -> Media:
    """Helper to create DOCX Media object from paragraph texts."""
    doc = Document()
    for para_text in paragraphs:
        doc.add_paragraph(para_text)
    
    # Save to in-memory bytes
    docx_bytes = io.BytesIO()
    doc.save(docx_bytes)
    docx_bytes.seek(0)
    
    return Media.from_bytes(
        data=docx_bytes.read(),
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename="test.docx"
    )


def test_extract_simple_docx_text(docx_extractor):
    """
    CHK006: Extract basic text from simple DOCX.
    Should handle plain paragraph text.
    """
    media = create_docx_media("Hello World", "This is a test document")
    
    result = docx_extractor.extract_text(media)
    
    assert "Hello World" in result["extracted_text"]
    assert "This is a test document" in result["extracted_text"]
    assert result["model_used"] == "python-docx"
    assert len(result["warnings"]) == 0


def test_extract_hebrew_text(docx_extractor):
    """
    CHK006: Extract Hebrew text with UTF-8 encoding.
    Should preserve Hebrew characters correctly.
    """
    media = create_docx_media("שלום עולם", "זהו מסמך בדיקה")
    
    result = docx_extractor.extract_text(media)
    
    assert "שלום עולם" in result["extracted_text"]
    assert "זהו מסמך בדיקה" in result["extracted_text"]
    assert result["model_used"] == "python-docx"
    assert len(result["warnings"]) == 0


def test_preserve_paragraph_structure(docx_extractor):
    """
    CHK010: Preserve paragraph structure with separators.
    Should separate paragraphs with double newlines.
    """
    media = create_docx_media("First paragraph", "Second paragraph", "Third paragraph")
    
    result = docx_extractor.extract_text(media)
    
    # Check paragraphs are separated
    assert "First paragraph\n\nSecond paragraph\n\nThird paragraph" == result["extracted_text"]
    assert len(result["warnings"]) == 0


def test_handle_empty_docx(docx_extractor):
    """
    CHK078: Handle empty DOCX gracefully.
    Should return empty text with warning.
    """
    media = create_docx_media()  # No paragraphs
    
    result = docx_extractor.extract_text(media)
    
    assert result["extracted_text"] == ""
    assert len(result["warnings"]) == 1
    assert "empty" in result["warnings"][0].lower()
    assert result["model_used"] == "python-docx"


def test_handle_corrupted_docx(docx_extractor):
    """
    CHK005, CHK007: Gracefully handle corrupted DOCX.
    Should return empty text with error warning.
    """
    # Create corrupted DOCX data
    corrupted_media = Media.from_bytes(
        data=b"This is not a valid DOCX file",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename="corrupted.docx"
    )
    
    result = docx_extractor.extract_text(corrupted_media)
    
    assert result["extracted_text"] == ""
    assert len(result["warnings"]) >= 1
    assert result["model_used"] == "python-docx"


def test_extract_text_ignoring_formatting(docx_extractor):
    """
    Extract plain text, ignoring formatting.
    Should extract text regardless of bold/italic/underline.
    """
    doc = Document()
    para = doc.add_paragraph()
    para.add_run("Normal text. ")
    para.add_run("Bold text. ").bold = True
    para.add_run("Italic text.").italic = True
    
    docx_bytes = io.BytesIO()
    doc.save(docx_bytes)
    docx_bytes.seek(0)
    
    media = Media.from_bytes(
        data=docx_bytes.read(),
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename="formatted.docx"
    )
    
    result = docx_extractor.extract_text(media)
    
    # All text should be extracted as plain text
    assert "Normal text." in result["extracted_text"]
    assert "Bold text." in result["extracted_text"]
    assert "Italic text." in result["extracted_text"]
    assert len(result["warnings"]) == 0


def test_extract_complex_structure(docx_extractor):
    """
    Extract text from complex document structure.
    Should handle tables, lists, and mixed content.
    """
    doc = Document()
    doc.add_heading("Document Title", level=1)
    doc.add_paragraph("Introduction paragraph")
    
    # Add a table
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Cell 1"
    table.cell(0, 1).text = "Cell 2"
    table.cell(1, 0).text = "Cell 3"
    table.cell(1, 1).text = "Cell 4"
    
    doc.add_paragraph("Conclusion paragraph")
    
    docx_bytes = io.BytesIO()
    doc.save(docx_bytes)
    docx_bytes.seek(0)
    
    media = Media.from_bytes(
        data=docx_bytes.read(),
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename="complex.docx"
    )
    
    result = docx_extractor.extract_text(media)
    
    # Should extract headings, paragraphs, and table text
    assert "Document Title" in result["extracted_text"]
    assert "Introduction paragraph" in result["extracted_text"]
    assert "Cell 1" in result["extracted_text"]
    assert "Cell 2" in result["extracted_text"]
    assert "Conclusion paragraph" in result["extracted_text"]
