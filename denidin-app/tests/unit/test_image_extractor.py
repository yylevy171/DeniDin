"""
Unit tests for Image Extractor (Feature 003 Phase 3.1)
Test-Driven Development: Write tests FIRST, then implement

CHK Requirements Validated:
- CHK006: Hebrew text extraction required
- CHK007: Graceful degradation on extraction failures
- CHK008: Mixed Hebrew/English support
- CHK010: Layout/structure preservation
- CHK027: Specific prompt (not just example)
- CHK078: Empty document handling
"""
import pytest
from unittest.mock import Mock
from src.utils.extractors.image_extractor import ImageExtractor
from src.models.media import Media


class TestImageExtractor:
    """Test suite for image text extraction via GPT-4o Vision."""
    
    @pytest.fixture
    def mock_denidin(self):
        """Create mock DeniDin context."""
        denidin = Mock()
        denidin.ai_handler = Mock()
        denidin.ai_handler._load_constitution.return_value = ""
        denidin.config = Mock()
        denidin.config.ai_vision_model = "gpt-4o"
        denidin.config.ai_reply_max_tokens = 1000
        return denidin
    
    @pytest.fixture
    def test_media(self):
        """Create test media object."""
        return Media.from_bytes(b"fake image data", "image/jpeg", "test.jpg")
    
    @pytest.fixture
    def extractor(self, mock_denidin):
        """Create ImageExtractor instance with mocked DeniDin context."""
        return ImageExtractor(mock_denidin)
    
    def test_extract_text_from_hebrew_image(self, extractor, test_media, mock_denidin):
        """
        Test Hebrew text extraction (UTF-8 encoding).
        CHK006: Hebrew text extraction required.
        """
        # Mock OpenAI Vision API response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = (
            "TEXT:\nשלום עולם\nזה מסמך בעברית\nCONFIDENCE: high\nNOTES: Clear Hebrew text"
        )
        mock_denidin.ai_handler.client.chat.completions.create.return_value = mock_response
        
        result = extractor.extract_text(test_media)
        
        assert "שלום עולם" in result["extracted_text"]
        assert "זה מסמך בעברית" in result["extracted_text"]
        assert result["model_used"] == "gpt-4o"
        assert result["extraction_quality"] in ["high", "medium", "low", "failed"]
    
    def test_extract_with_layout_preservation(self, extractor, test_media, mock_denidin):
        """
        Test that line breaks and paragraph structure are preserved.
        CHK010: Layout/structure preservation.
        """
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = (
            "TEXT:\nLine 1\n\nLine 2\n\nLine 3\nCONFIDENCE: high"
        )
        mock_denidin.ai_handler.client.chat.completions.create.return_value = mock_response
        
        result = extractor.extract_text(test_media)
        
        # Verify newlines are preserved
        assert "\n\n" in result["extracted_text"]
        assert "Line 1" in result["extracted_text"]
        assert "Line 3" in result["extracted_text"]
    
    def test_handle_empty_image(self, extractor, test_media, mock_denidin):
        """
        Test warning when image contains no text.
        CHK078: Empty document handling.
        """
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = (
            "TEXT:\n\nCONFIDENCE: low\nNOTES: No visible text"
        )
        mock_denidin.ai_handler.client.chat.completions.create.return_value = mock_response
        
        result = extractor.extract_text(test_media)
        
        assert result["extracted_text"] == ""
        assert result["extraction_quality"] == "low"
        assert len(result["warnings"]) > 0
    
    def test_handle_garbled_text_extraction(self, extractor, test_media, mock_denidin):
        """
        Test graceful failure on OCR errors.
        CHK007: Graceful degradation.
        """
        mock_denidin.ai_handler.client.chat.completions.create.side_effect = Exception("Vision API failed")
        
        result = extractor.extract_text(test_media)
        
        assert result["extracted_text"] == ""
        assert result["extraction_quality"] == "failed"
        assert len(result["warnings"]) > 0
        assert any("failed" in w.lower() for w in result["warnings"])
    
    def test_prompt_includes_hebrew_requirements(self, extractor, test_media, mock_denidin):
        """
        Test that prompt explicitly requests RTL/Hebrew handling.
        CHK027: Specific prompt (not just example).
        """
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "TEXT:\ntest\nCONFIDENCE: high"
        mock_denidin.ai_handler.client.chat.completions.create.return_value = mock_response
        
        extractor.extract_text(test_media)
        
        # Verify vision API was called
        assert mock_denidin.ai_handler.client.chat.completions.create.called
        call_args = mock_denidin.ai_handler.client.chat.completions.create.call_args
        
        # Check that prompt includes Hebrew/RTL requirements
        messages = call_args[1]["messages"]
        user_content = messages[0]["content"]
        text_part = next((item["text"] for item in user_content if item.get("type") == "text"), "")
        assert "hebrew" in text_part.lower() or "rtl" in text_part.lower()
    
    def test_assess_quality_high(self, extractor, test_media, mock_denidin):
        """
        Test quality assessment uses AI confidence directly.
        Quality: high when AI reports high confidence.
        """
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = (
            "TEXT:\nThis is clear, readable text.\nCONFIDENCE: high\nNOTES: Image quality excellent"
        )
        mock_denidin.ai_handler.client.chat.completions.create.return_value = mock_response
        
        result = extractor.extract_text(test_media)
        
        assert result["extraction_quality"] == "high"
    
    def test_assess_quality_medium(self, extractor, test_media, mock_denidin):
        """
        Test quality assessment uses AI confidence directly.
        Quality: medium when AI reports medium confidence.
        """
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = (
            "TEXT:\nSomewhat blurry text\nCONFIDENCE: medium\nNOTES: Some characters unclear"
        )
        mock_denidin.ai_handler.client.chat.completions.create.return_value = mock_response
        
        result = extractor.extract_text(test_media)
        
        assert result["extraction_quality"] == "medium"
    
    # ========== Phase 4: Document Analysis Tests ==========
    
    def test_extract_includes_document_analysis(self, extractor, test_media, mock_denidin):
        """
        Phase 4: Verify extract_text returns document_analysis structure.
        """
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = (
            "TEXT:\nContract Agreement\n\n"
            "DOCUMENT_TYPE: contract\n"
            "SUMMARY: Service agreement between parties\n"
            "KEY_POINTS:\n"
            "- Client: David Cohen\n"
            "- Amount: ₪50,000\n"
            "CONFIDENCE: high"
        )
        mock_denidin.ai_handler.client.chat.completions.create.return_value = mock_response
        
        result = extractor.extract_text(test_media)
        
        # Verify document_analysis exists
        assert "document_analysis" in result
        analysis = result["document_analysis"]
        
        # Verify all required fields
        assert "document_type" in analysis
        assert "summary" in analysis
        assert "key_points" in analysis
        
        # Verify content
        assert analysis["document_type"] == "contract"
        assert "agreement" in analysis["summary"].lower()
        assert isinstance(analysis["key_points"], list)
        assert len(analysis["key_points"]) == 2
        assert "David Cohen" in analysis["key_points"][0]
    
    def test_document_analysis_generic_fallback(self, extractor, test_media, mock_denidin):
        """
        Phase 4: When AI can't determine type, defaults to 'generic'.
        """
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = (
            "TEXT:\nSome random notes\n\n"
            "DOCUMENT_TYPE: generic\n"
            "SUMMARY: Unstructured personal notes\n"
            "KEY_POINTS:\n"
            "- Note about meeting\n"
            "CONFIDENCE: medium"
        )
        mock_denidin.ai_handler.client.chat.completions.create.return_value = mock_response
        
        result = extractor.extract_text(test_media)
        
        assert result["document_analysis"]["document_type"] == "generic"
    
    def test_prompt_includes_document_analysis_request(self, extractor, test_media, mock_denidin):
        """
        Phase 4: Verify enhanced prompt requests document analysis.
        """
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = (
            "TEXT:\nTest\n\nDOCUMENT_TYPE: generic\nSUMMARY: test\nKEY_POINTS:\n- test\nCONFIDENCE: high"
        )
        mock_denidin.ai_handler.client.chat.completions.create.return_value = mock_response
        
        extractor.extract_text(test_media)
        
        call_args = mock_denidin.ai_handler.client.chat.completions.create.call_args
        messages = call_args[1]["messages"]
        user_content = messages[0]["content"]
        text_part = next((item["text"] for item in user_content if item.get("type") == "text"), "")
        
        # Verify prompt requests analysis
        assert "document" in text_part.lower()
        assert "analysis" in text_part.lower() or "analyze" in text_part.lower()
        assert "summary" in text_part.lower()
        assert "key" in text_part.lower() and "point" in text_part.lower()

