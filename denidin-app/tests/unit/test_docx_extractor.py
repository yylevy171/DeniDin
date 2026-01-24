"""
Unit tests for DOCX Extractor (Feature 003 Phase 3.3 + Phase 4)

CHK Requirements:
- CHK005: Corrupted file handling
- CHK006: Hebrew text extraction
- CHK007: Graceful degradation on failures
- CHK010: Layout/structure preservation
- CHK078: Empty document handling

Phase 4: Optional AI-powered document analysis
"""
import pytest
import io
from unittest.mock import Mock, patch
from docx import Document
from src.handlers.extractors.docx_extractor import DOCXExtractor
from src.models.media import Media


@pytest.fixture
def mock_denidin_context():
    """Create mock DeniDin context."""
    context = Mock()
    context.config = Mock()
    context.config.ai_model = "gpt-4o"
    context.ai_handler = Mock()
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


def test_extract_simple_docx_text(docx_extractor, mock_denidin_context):
    """
    CHK006: Extract basic text from simple DOCX.
    Should handle plain paragraph text.
    Phase 4: Test with analyze=False (no AI call).
    """
    media = create_docx_media("Hello World", "This is a test document")
    
    # Phase 4: analyze=False should skip AI call
    result = docx_extractor.extract_text(media, analyze=False)
    
    assert "Hello World" in result["extracted_text"]
    assert "This is a test document" in result["extracted_text"]
    assert result["model_used"] == "python-docx"
    assert result["document_analysis"] is None  # Phase 4: No analysis
    assert result["extraction_quality"] == "high"
    assert len(result["warnings"]) == 0
    
    # Verify AI was not called
    assert mock_denidin_context.ai_handler.send_message.call_count == 0


def test_extract_hebrew_text(docx_extractor, mock_denidin_context):
    """
    CHK006: Extract Hebrew text with UTF-8 encoding.
    Should preserve Hebrew characters correctly.
    """
    media = create_docx_media("שלום עולם", "זהו מסמך בדיקה")
    
    # Test without analysis
    result = docx_extractor.extract_text(media, analyze=False)
    
    assert "שלום עולם" in result["extracted_text"]
    assert "זהו מסמך בדיקה" in result["extracted_text"]
    assert result["model_used"] == "python-docx"
    assert result["document_analysis"] is None
    assert len(result["warnings"]) == 0


def test_preserve_paragraph_structure(docx_extractor, mock_denidin_context):
    """
    CHK010: Preserve paragraph structure with separators.
    Should separate paragraphs with double newlines.
    """
    media = create_docx_media("First paragraph", "Second paragraph", "Third paragraph")
    
    result = docx_extractor.extract_text(media, analyze=False)
    
    # Check paragraphs are separated
    assert "First paragraph\n\nSecond paragraph\n\nThird paragraph" == result["extracted_text"]
    assert len(result["warnings"]) == 0


def test_handle_empty_docx(docx_extractor, mock_denidin_context):
    """
    CHK078: Handle empty DOCX gracefully.
    Should return empty text with warning.
    """
    media = create_docx_media()  # No paragraphs
    
    result = docx_extractor.extract_text(media, analyze=False)
    
    assert result["extracted_text"] == ""
    assert len(result["warnings"]) == 1
    assert "empty" in result["warnings"][0].lower()
    assert result["model_used"] == "python-docx"
    assert result["document_analysis"] is None  # No analysis for empty doc


def test_handle_corrupted_docx(docx_extractor, mock_denidin_context):
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
    
    result = docx_extractor.extract_text(corrupted_media, analyze=False)
    
    assert result["extracted_text"] == ""
    assert len(result["warnings"]) >= 1
    assert result["model_used"] == "python-docx"
    assert result["document_analysis"] is None
    assert result["extraction_quality"] == "failed"


def test_extract_text_ignoring_formatting(docx_extractor, mock_denidin_context):
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
    
    result = docx_extractor.extract_text(media, analyze=False)
    
    # All text should be extracted as plain text
    assert "Normal text." in result["extracted_text"]
    assert "Bold text." in result["extracted_text"]
    assert "Italic text." in result["extracted_text"]
    assert len(result["warnings"]) == 0


def test_extract_complex_structure(docx_extractor, mock_denidin_context):
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
    
    result = docx_extractor.extract_text(media, analyze=False)
    
    # Should extract headings, paragraphs, and table text
    assert "Document Title" in result["extracted_text"]
    assert "Introduction paragraph" in result["extracted_text"]
    assert "Cell 1" in result["extracted_text"]
    assert "Cell 2" in result["extracted_text"]
    assert "Conclusion paragraph" in result["extracted_text"]


# ===== Phase 4: AI-Powered Document Analysis Tests =====

def test_analyze_document_with_ai(docx_extractor, mock_denidin_context):
    """
    Phase 4: With analyze=True, should call AI to analyze document.
    """
    media = create_docx_media("Invoice #12345", "Total: $100", "Due Date: 2024-01-01")
    
    # Mock AI response
    mock_denidin_context.ai_handler.send_message.return_value = """DOCUMENT_TYPE: invoice
SUMMARY: Invoice for $100 due on 2024-01-01
KEY_POINTS:
- Invoice number 12345
- Amount $100
- Due date 2024-01-01"""
    
    # Phase 4: analyze=True (default) should call AI
    result = docx_extractor.extract_text(media, analyze=True)
    
    # Text extraction should work
    assert "Invoice #12345" in result["extracted_text"]
    
    # Document analysis should be present
    assert result["document_analysis"] is not None
    assert result["document_analysis"]["document_type"] == "invoice"
    assert "$100" in result["document_analysis"]["summary"]
    assert len(result["document_analysis"]["key_points"]) == 3
    assert "Invoice number 12345" in result["document_analysis"]["key_points"]
    
    # Model used should include both python-docx and AI model
    assert "python-docx + gpt-4o" == result["model_used"]
    
    # Verify AI was called
    assert mock_denidin_context.ai_handler.send_message.call_count == 1


def test_analyze_skipped_when_false(docx_extractor, mock_denidin_context):
    """
    Phase 4: With analyze=False, should NOT call AI.
    """
    media = create_docx_media("Some document text")
    
    result = docx_extractor.extract_text(media, analyze=False)
    
    # Text extraction should work
    assert "Some document text" in result["extracted_text"]
    
    # No document analysis
    assert result["document_analysis"] is None
    assert result["model_used"] == "python-docx"
    
    # AI should NOT have been called
    assert mock_denidin_context.ai_handler.send_message.call_count == 0


def test_analyze_default_is_true(docx_extractor, mock_denidin_context):
    """
    Phase 4: Default behavior (no analyze parameter) should analyze.
    """
    media = create_docx_media("Document content")
    
    # Mock AI response
    mock_denidin_context.ai_handler.send_message.return_value = """DOCUMENT_TYPE: generic
SUMMARY: Document with content
KEY_POINTS:
- Content present"""
    
    # Call without analyze parameter (should default to True)
    result = docx_extractor.extract_text(media)
    
    # Should have document analysis
    assert result["document_analysis"] is not None
    assert "python-docx + gpt-4o" in result["model_used"]
    assert mock_denidin_context.ai_handler.send_message.call_count == 1


def test_analyze_graceful_ai_failure(docx_extractor, mock_denidin_context):
    """
    Phase 4: If AI analysis fails, should fallback gracefully.
    """
    media = create_docx_media("Document text")
    
    # Mock AI failure
    mock_denidin_context.ai_handler.send_message.side_effect = Exception("AI service down")
    
    result = docx_extractor.extract_text(media, analyze=True)
    
    # Text extraction should still work
    assert "Document text" in result["extracted_text"]
    
    # Document analysis should have fallback values
    assert result["document_analysis"] is not None
    assert result["document_analysis"]["document_type"] == "generic"
    assert "failed" in result["document_analysis"]["summary"].lower()
    assert result["document_analysis"]["key_points"] == []


def test_analyze_empty_document_no_ai_call(docx_extractor, mock_denidin_context):
    """
    Phase 4: Empty documents should NOT call AI for analysis.
    """
    media = create_docx_media()  # Empty
    
    result = docx_extractor.extract_text(media, analyze=True)
    
    # Empty text
    assert result["extracted_text"] == ""
    
    # No AI call for empty document
    assert result["document_analysis"] is None
    assert mock_denidin_context.ai_handler.send_message.call_count == 0

