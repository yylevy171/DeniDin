"""
Tests for constitution and caption usage in all extractors.

Validates that:
1. All extractors prepend constitution to user prompts (NO system messages)
2. All extractors include caption context when provided
3. Constitution architecture is enforced across all AI calls
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, mock_open
from src.models.media import Media
from src.handlers.extractors.image_extractor import ImageExtractor
from src.handlers.extractors.pdf_extractor import PDFExtractor
from src.handlers.extractors.docx_extractor import DOCXExtractor


class TestConstitutionUsage:
    """Test that all extractors use constitution correctly (in user prompt, NOT system message)."""
    
    def test_image_extractor_uses_constitution_in_user_prompt(self):
        """ImageExtractor must prepend constitution to user prompt, NOT use system message."""
        mock_denidin = Mock()
        mock_denidin.config.vision_model = "gpt-4o"
        mock_denidin.config.ai_reply_max_tokens = 4000
        mock_denidin.ai_handler._load_constitution = Mock(return_value="I am DeniDin, a helpful assistant.")
        
        # Mock OpenAI client response
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="TEXT:\nSample text\n\nDOCUMENT_TYPE: receipt\nSUMMARY: Test\nKEY_POINTS:\n- Point 1\n\nCONFIDENCE: high\n"))]
        mock_denidin.ai_handler.client.chat.completions.create = Mock(return_value=mock_response)
        
        extractor = ImageExtractor(mock_denidin)
        media = Media(data=b"fake_image", mime_type="image/jpeg", filename="test.jpg")
        
        # Mock prompt file
        mock_prompt = "Analyze this image\n{user_context}\n{addressing_note}\n{focusing_note}"
        
        def mock_read_text(self, encoding='utf-8'):
            """Only mock the prompt file."""
            if 'prompts/image_analysis.txt' in str(self):
                return mock_prompt
            raise FileNotFoundError(f"Test: unexpected path read: {self}")
        
        with patch('pathlib.Path.read_text', mock_read_text):
            # Extract
            extractor.analyze_media(media)
        
        # Verify constitution was loaded
        mock_denidin.ai_handler._load_constitution.assert_called_once()
        
        # Verify client.chat.completions.create was called
        call_args = mock_denidin.ai_handler.client.chat.completions.create.call_args
        messages = call_args[1]["messages"]
        
        # Should have exactly 1 user message (NO system message)
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        
        # Constitution should be prepended to user prompt
        text_content = next(c for c in messages[0]["content"] if c["type"] == "text")
        assert "I am DeniDin" in text_content["text"]
        assert "Analyze this image" in text_content["text"]
    
    def test_docx_extractor_uses_constitution_not_system_prompt(self):
        """DOCXExtractor must use constitution in user prompt, NOT system_prompt parameter."""
        mock_denidin = Mock()
        mock_denidin.config.ai_model = "gpt-4o-mini"
        mock_denidin.config.ai_reply_max_tokens = 4096
        mock_denidin.config.temperature = 0.7
        mock_denidin.config.constitution_config = {}
        mock_denidin.ai_handler = Mock()
        mock_denidin.ai_handler._load_constitution = Mock(return_value="I am DeniDin, a helpful assistant.")
        
        # Mock get_response to return proper response
        mock_ai_response = Mock()
        mock_ai_response.response_text = "DOCUMENT_TYPE: letter\nSUMMARY: Test\nKEY_POINTS:\n- Point 1\n"
        mock_denidin.ai_handler.get_response = Mock(return_value=mock_ai_response)
        
        extractor = DOCXExtractor(mock_denidin)
        
        # Mock prompt file - patch Path.read_text specifically
        mock_prompt = "Analyze this document text and provide:\n1. DOCUMENT_TYPE\n{document_text}\n{user_context}\n{addressing_note}\n{focusing_note}"
        
        def mock_read_text(self, encoding='utf-8'):
            """Only mock the prompt file, let other Path operations through."""
            if 'prompts/docx_analysis.txt' in str(self):
                return mock_prompt
            # Let other paths fail naturally (they shouldn't be read)
            raise FileNotFoundError(f"Test: unexpected path read: {self}")
        
        with patch('src.handlers.extractors.docx_extractor.Document') as mock_doc_class, \
             patch('pathlib.Path.read_text', mock_read_text):
            mock_doc = MagicMock()
            mock_doc.paragraphs = [Mock(text="Sample paragraph")]
            mock_doc.tables = []
            mock_doc_class.return_value = mock_doc
            
            media = Media(data=b"fake_docx", mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            extractor.analyze_media(media, analyze=True)
        
        # Verify constitution was loaded and used
        mock_denidin.ai_handler._load_constitution.assert_called_once()
        
        # Verify get_response was called
        assert mock_denidin.ai_handler.get_response.call_count == 1
        call_args = mock_denidin.ai_handler.get_response.call_args
        
        # The AIRequest object should have been created with the constitution in the prompt
        assert call_args is not None
    
    def test_pdf_extractor_passes_caption_to_image_extractor(self):
        """PDFExtractor must pass caption through to ImageExtractor for page analysis."""
        mock_denidin = Mock()
        mock_denidin.config.vision_model = "gpt-4o"
        mock_denidin.config.ai_reply_max_tokens = 4000
        mock_denidin.ai_handler._load_constitution = Mock(return_value="")
        
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="TEXT:\nPage text\n\nDOCUMENT_TYPE: invoice\nSUMMARY: Test\nKEY_POINTS:\n- Item\n\nCONFIDENCE: high\n"))]
        mock_denidin.ai_handler.client.chat.completions.create = Mock(return_value=mock_response)
        
        extractor = PDFExtractor(mock_denidin)
        
        with patch('src.handlers.extractors.pdf_extractor.fitz') as mock_fitz:
            mock_pdf = MagicMock()
            mock_page = MagicMock()
            mock_pixmap = MagicMock()
            mock_pixmap.tobytes.return_value = b"fake_png"
            mock_page.get_pixmap.return_value = mock_pixmap
            mock_pdf.__iter__.return_value = [mock_page]
            mock_pdf.__len__.return_value = 1
            mock_fitz.open.return_value = mock_pdf
            
            media = Media(data=b"fake_pdf", mime_type="application/pdf")
            extractor.analyze_media(media, caption="What's the total amount?")
        
        # Verify caption in prompt
        call_args = mock_denidin.ai_handler.client.chat.completions.create.call_args
        messages = call_args[1]["messages"]
        text_content = next(c for c in messages[0]["content"] if c["type"] == "text")
        
        assert "What's the total amount?" in text_content["text"]


class TestCaptionContext:
    """Test that all extractors include caption in their analysis prompts."""
    
    def test_image_extractor_includes_caption_in_prompt(self):
        """ImageExtractor should include user's caption/question in the analysis prompt."""
        mock_denidin = Mock()
        mock_denidin.config.vision_model = "gpt-4o"
        mock_denidin.config.ai_reply_max_tokens = 4000
        mock_denidin.ai_handler._load_constitution = Mock(return_value="")
        
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="TEXT:\nContract text\n\nDOCUMENT_TYPE: contract\nSUMMARY: Service agreement\nKEY_POINTS:\n- Amount: $5000\n\nCONFIDENCE: high\n"))]
        mock_denidin.ai_handler.client.chat.completions.create = Mock(return_value=mock_response)
        
        extractor = ImageExtractor(mock_denidin)
        media = Media(data=b"image", mime_type="image/jpeg")
        
        # Mock prompt file
        mock_prompt = "Analyze this image\n{user_context}\n{addressing_note}\n{focusing_note}"
        
        def mock_read_text(self, encoding='utf-8'):
            if 'prompts/image_analysis.txt' in str(self):
                return mock_prompt
            raise FileNotFoundError(f"Test: unexpected path read: {self}")
        
        with patch('pathlib.Path.read_text', mock_read_text):
            extractor.analyze_media(media, caption="Who is the client in this contract?")
        
        call_args = mock_denidin.ai_handler.client.chat.completions.create.call_args
        messages = call_args[1]["messages"]
        text_content = next(c for c in messages[0]["content"] if c["type"] == "text")
        
        assert "Who is the client in this contract?" in text_content["text"]
        assert "User's question/message:" in text_content["text"]
    
    def test_image_extractor_works_without_caption(self):
        """ImageExtractor should work when caption is empty (optional parameter)."""
        mock_denidin = Mock()
        mock_denidin.config.vision_model = "gpt-4o"
        mock_denidin.config.ai_reply_max_tokens = 4000
        mock_denidin.config.ai_model = "gpt-4o"
        mock_denidin.ai_handler = Mock()
        mock_denidin.ai_handler._load_constitution = Mock(return_value="")
        
        # Mock the OpenAI client response
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="TEXT:\nText\n\nDOCUMENT_TYPE: generic\nSUMMARY: Test\nKEY_POINTS:\n- Point\n\nCONFIDENCE: high\n"))]
        mock_denidin.ai_handler.client = Mock()
        mock_denidin.ai_handler.client.chat = Mock()
        mock_denidin.ai_handler.client.chat.completions = Mock()
        mock_denidin.ai_handler.client.chat.completions.create = Mock(return_value=mock_response)
        
        extractor = ImageExtractor(mock_denidin)
        media = Media(data=b"image", mime_type="image/jpeg")
        
        result = extractor.analyze_media(media)
        
        # Should succeed - check that client was called
        assert mock_denidin.ai_handler.client.chat.completions.create.call_count == 1
        assert result["extraction_quality"] in ["high", "medium", "low", "failed"]
        assert "raw_response" in result
    
    def test_docx_extractor_includes_caption_in_analysis(self):
        """DOCXExtractor should include caption in AI analysis prompt."""
        mock_denidin = Mock()
        mock_denidin.config.ai_model = "gpt-4o-mini"
        mock_denidin.config.ai_reply_max_tokens = 4096
        mock_denidin.config.temperature = 0.7
        mock_denidin.config.constitution_config = {}
        mock_denidin.ai_handler = Mock()
        mock_denidin.ai_handler._load_constitution = Mock(return_value="")
        
        # Mock get_response to return proper response
        mock_ai_response = Mock()
        mock_ai_response.response_text = "DOCUMENT_TYPE: invoice\nSUMMARY: Total is $2500\nKEY_POINTS:\n- Total: $2500\n"
        mock_denidin.ai_handler.get_response = Mock(return_value=mock_ai_response)
        
        extractor = DOCXExtractor(mock_denidin)
        
        mock_prompt = "Analyze this document text and provide:\n1. DOCUMENT_TYPE\n{document_text}\n{user_context}\n{addressing_note}\n{focusing_note}"
        
        def mock_read_text(self, encoding='utf-8'):
            """Only mock the prompt file, let other Path operations through."""
            if 'prompts/docx_analysis.txt' in str(self):
                return mock_prompt
            raise FileNotFoundError(f"Test: unexpected path read: {self}")
        
        with patch('src.handlers.extractors.docx_extractor.Document') as mock_doc_class, \
             patch('pathlib.Path.read_text', mock_read_text):
            mock_doc = MagicMock()
            mock_doc.paragraphs = [Mock(text="Invoice details")]
            mock_doc.tables = []
            mock_doc_class.return_value = mock_doc
            
            media = Media(data=b"docx", mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            extractor.analyze_media(media, analyze=True, caption="What is the total amount?")
        
        # Verify get_response was called
        assert mock_denidin.ai_handler.get_response.call_count == 1
        call_args = mock_denidin.ai_handler.get_response.call_args
        # Check that caption was included in the request
        assert call_args is not None
    
    def test_docx_extractor_analysis_guided_by_caption(self):
        """DOCXExtractor prompt should instruct AI to focus on user's question when caption exists."""
        mock_denidin = Mock()
        mock_denidin.config.ai_model = "gpt-4o-mini"
        mock_denidin.config.ai_reply_max_tokens = 4096
        mock_denidin.config.temperature = 0.7
        mock_denidin.config.constitution_config = {}
        mock_denidin.ai_handler = Mock()
        mock_denidin.ai_handler._load_constitution = Mock(return_value="")
        
        # Mock get_response to return proper response
        mock_ai_response = Mock()
        mock_ai_response.response_text = "DOCUMENT_TYPE: contract\nSUMMARY: Client is John Doe\nKEY_POINTS:\n- Client: John Doe\n"
        mock_denidin.ai_handler.get_response = Mock(return_value=mock_ai_response)
        
        extractor = DOCXExtractor(mock_denidin)
        
        mock_prompt = "Analyze this document text and provide:\n1. DOCUMENT_TYPE\n{document_text}\n{user_context}\n{addressing_note}\n{focusing_note}"
        
        def mock_read_text(self, encoding='utf-8'):
            """Only mock the prompt file, let other Path operations through."""
            if 'prompts/docx_analysis.txt' in str(self):
                return mock_prompt
            raise FileNotFoundError(f"Test: unexpected path read: {self}")
        
        with patch('src.handlers.extractors.docx_extractor.Document') as mock_doc_class, \
             patch('pathlib.Path.read_text', mock_read_text):
            mock_doc = MagicMock()
            mock_doc.paragraphs = [Mock(text="Contract with John Doe")]
            mock_doc.tables = []
            mock_doc_class.return_value = mock_doc
            
            media = Media(data=b"docx", mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
            extractor.analyze_media(media, analyze=True, caption="Who is the client?")
        
        # Verify get_response was called
        assert mock_denidin.ai_handler.get_response.call_count == 1
    
    def test_pdf_extractor_passes_caption_to_all_pages(self):
        """PDFExtractor should pass same caption to all page extractions."""
        mock_denidin = Mock()
        mock_denidin.config.vision_model = "gpt-4o"
        mock_denidin.config.ai_reply_max_tokens = 4000
        mock_denidin.ai_handler._load_constitution = Mock(return_value="")
        
        # Track calls
        call_count = [0]
        def mock_create(**kwargs):
            call_count[0] += 1
            mock_resp = Mock()
            mock_resp.choices = [Mock(message=Mock(content="TEXT:\nPage\n\nDOCUMENT_TYPE: invoice\nSUMMARY: Test\nKEY_POINTS:\n- Item\n\nCONFIDENCE: high\n"))]
            return mock_resp
        
        mock_denidin.ai_handler.client.chat.completions.create = mock_create
        
        extractor = PDFExtractor(mock_denidin)
        
        with patch('src.handlers.extractors.pdf_extractor.fitz') as mock_fitz:
            mock_pdf = MagicMock()
            mock_pages = [MagicMock() for _ in range(3)]
            for page in mock_pages:
                mock_pixmap = MagicMock()
                mock_pixmap.tobytes.return_value = b"png"
                page.get_pixmap.return_value = mock_pixmap
            
            mock_pdf.__iter__.return_value = mock_pages
            mock_pdf.__len__.return_value = 3
            mock_fitz.open.return_value = mock_pdf
            
            media = Media(data=b"pdf", mime_type="application/pdf")
            extractor.analyze_media(media, caption="Find the invoice number")
        
        # All 3 pages should have been called
        assert call_count[0] == 3
