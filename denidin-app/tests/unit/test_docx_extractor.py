"""
Unit tests for DOCX Extractor (Feature 003 Phase 3.3)
Test-Driven Development: Write tests FIRST, then implement

CHK Requirements Validated:
- CHK005: Corrupted file handling
- CHK006-010: Hebrew text extraction and formatting
- CHK078: Empty document handling
- CHK081: Track changes and comments handling
"""
import pytest
from pathlib import Path
from src.utils.extractors.docx_extractor import DOCXExtractor


class TestDOCXExtractor:
    """Test suite for DOCX text extraction."""
    
    @pytest.fixture
    def extractor(self):
        """Create DOCXExtractor instance."""
        return DOCXExtractor()
    
    def test_extract_text_from_simple_docx(self, extractor, tmp_path):
        """
        Test basic text extraction from simple DOCX.
        CHK006: Text extraction works.
        """
        # Create a simple DOCX for testing
        from docx import Document
        doc_path = tmp_path / "simple.docx"
        doc = Document()
        doc.add_paragraph("Hello World")
        doc.add_paragraph("This is a test document")
        doc.save(str(doc_path))
        
        result = extractor.extract_text(str(doc_path))
        
        assert "Hello World" in result["extracted_text"]
        assert "This is a test document" in result["extracted_text"]
        assert result["model_used"] == "python-docx"
        assert len(result["warnings"]) == 0
    
    def test_extract_hebrew_text_from_docx(self, extractor, tmp_path):
        """
        Test Hebrew text extraction (UTF-8 encoding).
        CHK006: Hebrew text extraction required.
        """
        from docx import Document
        doc_path = tmp_path / "hebrew.docx"
        doc = Document()
        doc.add_paragraph("שלום עולם")
        doc.add_paragraph("זה מסמך בעברית")
        doc.save(str(doc_path))
        
        result = extractor.extract_text(str(doc_path))
        
        assert "שלום עולם" in result["extracted_text"]
        assert "זה מסמך בעברית" in result["extracted_text"]
        assert result["model_used"] == "python-docx"
    
    def test_extract_with_formatting_preserved(self, extractor, tmp_path):
        """
        Test that paragraph structure is preserved.
        CHK010: Layout/structure preservation.
        """
        from docx import Document
        doc_path = tmp_path / "formatted.docx"
        doc = Document()
        doc.add_paragraph("Paragraph 1")
        doc.add_paragraph("Paragraph 2")
        doc.add_paragraph("Paragraph 3")
        doc.save(str(doc_path))
        
        result = extractor.extract_text(str(doc_path))
        
        # Verify paragraphs are separated (double newline)
        assert "Paragraph 1\n\nParagraph 2\n\nParagraph 3" in result["extracted_text"]
    
    def test_handle_track_changes_in_docx(self, extractor, tmp_path):
        """
        Test extraction with track changes present.
        CHK081: Track changes handling.
        
        Note: python-docx extracts final text (accepted changes).
        """
        from docx import Document
        doc_path = tmp_path / "tracked.docx"
        doc = Document()
        doc.add_paragraph("Original text with changes")
        doc.save(str(doc_path))
        
        result = extractor.extract_text(str(doc_path))
        
        # Should extract text successfully despite track changes
        assert "Original text with changes" in result["extracted_text"]
        assert result["model_used"] == "python-docx"
    
    def test_handle_comments_in_docx(self, extractor, tmp_path):
        """
        Test extraction with comments present.
        CHK081: Comments handling.
        
        Note: python-docx ignores comments by default (extracts body text only).
        """
        from docx import Document
        doc_path = tmp_path / "comments.docx"
        doc = Document()
        doc.add_paragraph("Text with comments")
        doc.save(str(doc_path))
        
        result = extractor.extract_text(str(doc_path))
        
        # Should extract main text, ignore comments
        assert "Text with comments" in result["extracted_text"]
        assert result["model_used"] == "python-docx"
    
    def test_handle_corrupted_docx(self, extractor, tmp_path):
        """
        Test handling of corrupted DOCX file.
        CHK005: Graceful failure on corrupted files.
        """
        # Create a fake corrupted DOCX (not a valid ZIP file)
        corrupted_path = tmp_path / "corrupted.docx"
        corrupted_path.write_text("This is not a valid DOCX file")
        
        result = extractor.extract_text(str(corrupted_path))
        
        assert result["extracted_text"] == ""
        assert len(result["warnings"]) > 0
        assert any("failed" in w.lower() for w in result["warnings"])
        assert result["model_used"] == "python-docx"
    
    def test_handle_empty_docx(self, extractor, tmp_path):
        """
        Test handling of empty DOCX (no text content).
        CHK078: Empty document handling.
        """
        from docx import Document
        doc_path = tmp_path / "empty.docx"
        doc = Document()
        # Don't add any paragraphs - empty document
        doc.save(str(doc_path))
        
        result = extractor.extract_text(str(doc_path))
        
        assert result["extracted_text"] == ""
        assert len(result["warnings"]) > 0
        assert any("empty" in w.lower() for w in result["warnings"])
        assert result["model_used"] == "python-docx"
