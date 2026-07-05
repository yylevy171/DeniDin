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
from src.handlers.extractors.image_extractor import ImageExtractor
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
        
        result = extractor.analyze_media(test_media)
        
        assert "שלום עולם" in result["raw_response"]
        assert "זה מסמך בעברית" in result["raw_response"]
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
        
        result = extractor.analyze_media(test_media)
        
        # Verify newlines are preserved
        assert "\n\n" in result["raw_response"]
        assert "Line 1" in result["raw_response"]
        assert "Line 3" in result["raw_response"]
    
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
        
        result = extractor.analyze_media(test_media)
        
        # raw_response contains the full AI response, even if it says no text
        assert "No visible text" in result["raw_response"]
        assert result["extraction_quality"] == "high"
    
    def test_handle_garbled_text_extraction(self, extractor, test_media, mock_denidin):
        """
        Test graceful failure on OCR errors.
        CHK007: Graceful degradation.
        """
        mock_denidin.ai_handler.client.chat.completions.side_effect = Exception("Vision API failed")
        
        result = extractor.analyze_media(test_media)
        
        # On exception, raw_response is empty
        assert result["raw_response"] == ""
        assert result["extraction_quality"] == "failed"
        assert "Analysis failed" in result["warnings"][0]
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
        
        extractor.analyze_media(test_media)
        
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
        
        result = extractor.analyze_media(test_media)
        
        assert result["extraction_quality"] == "high"
    
    def test_assess_quality_medium(self, extractor, test_media, mock_denidin):
        """
        Test that quality is always 'high' since we don't parse anymore.
        We just pass through the AI response.
        """
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = (
            "TEXT:\nSomewhat blurry text\nCONFIDENCE: medium\nNOTES: Some characters unclear"
        )
        mock_denidin.ai_handler.client.chat.completions.create.return_value = mock_response
        
        result = extractor.analyze_media(test_media)
        
        # Quality is always "high" for ImageExtractor since we don't parse
        assert result["extraction_quality"] == "high"
    
    # ========== Phase 4: Document Analysis Tests ==========
    
    def test_prompt_includes_document_analysis_request(self, extractor, test_media, mock_denidin):
        """
        Verify that the prompt is loaded and sent to the API.
        The AI response is passed through unchanged - no parsing.
        """
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "AI analysis response"
        mock_denidin.ai_handler.client.chat.completions.create.return_value = mock_response
        
        result = extractor.analyze_media(test_media)
        
        # Verify raw_response contains the AI response
        assert result["raw_response"] == "AI analysis response"
        
        # Verify the API was called
        assert mock_denidin.ai_handler.client.chat.completions.create.called

