"""
Unit tests for Media Configuration.
Tests configuration constants for media processing.

TASK-004: Media Config (TEST) - TDD Red Phase
All tests should FAIL initially - config module doesn't exist yet.

CHK References: 
- CHK002: 10MB file size limit
- CHK011: 150 DPI for PDF conversion
- CHK023: UTF-8 encoding
- CHK039-041: Format support (JPG/JPEG/PNG/PDF/DOCX only)
- CHK042: Storage path consistency
- CHK044-046: AI model consistency
- CHK048: Retry logic (1 max)
"""
import pytest
from pathlib import Path
from src.config.media_config import MediaConfig


class TestMediaConfig:
    """Test MediaConfig constants and configuration values."""
    
    def test_supported_image_formats(self):
        """CHK039: JPG, JPEG, PNG only (no GIF)."""
        config = MediaConfig()
        assert 'jpg' in config.SUPPORTED_IMAGE_FORMATS
        assert 'jpeg' in config.SUPPORTED_IMAGE_FORMATS
        assert 'png' in config.SUPPORTED_IMAGE_FORMATS
        assert 'gif' not in config.SUPPORTED_IMAGE_FORMATS
    
    def test_supported_document_formats(self):
        """CHK040-041: PDF and DOCX only (no TXT)."""
        config = MediaConfig()
        assert 'pdf' in config.SUPPORTED_DOCUMENT_FORMATS
        assert 'docx' in config.SUPPORTED_DOCUMENT_FORMATS
        assert 'txt' not in config.SUPPORTED_DOCUMENT_FORMATS
    
    def test_all_supported_formats_combined(self):
        """Combined list of all supported formats."""
        config = MediaConfig()
        all_formats = config.SUPPORTED_IMAGE_FORMATS + config.SUPPORTED_DOCUMENT_FORMATS
        
        # Should have exactly 5 formats: jpg, jpeg, png, pdf, docx
        assert len(all_formats) == 5
        assert 'jpg' in all_formats
        assert 'jpeg' in all_formats
        assert 'png' in all_formats
        assert 'pdf' in all_formats
        assert 'docx' in all_formats
    
    def test_max_file_size_10mb(self):
        """CHK002: 10MB file size limit."""
        config = MediaConfig()
        assert config.MAX_FILE_SIZE_MB == 10
        assert config.MAX_FILE_SIZE_BYTES == 10 * 1024 * 1024
        assert config.MAX_FILE_SIZE_BYTES == 10485760  # Exact byte count
    
    def test_max_pdf_pages_10(self):
        """CHK003-004: 10 pages max for PDFs."""
        config = MediaConfig()
        assert config.MAX_PDF_PAGES == 10
    
    def test_pdf_dpi_150(self):
        """CHK011: 150 DPI for PDF-to-image conversion (Hebrew quality)."""
        config = MediaConfig()
        assert config.PDF_DPI == 150
    
    def test_storage_base_path(self):
        """CHK042: Storage at data/images/."""
        config = MediaConfig()
        assert config.STORAGE_BASE == Path("data/images")
        assert str(config.STORAGE_BASE) == "data/images"
    
    def test_storage_path_uses_forward_slashes(self):
        """CHK042: Path consistency across platforms."""
        config = MediaConfig()
        # Path should use forward slashes (platform-independent)
        path_str = str(config.STORAGE_BASE)
        assert "/" in path_str or path_str == "data/images"
    
    def test_ai_model_names(self):
        """CHK044-046: Model consistency - gpt-4o and gpt-4o-mini."""
        config = MediaConfig()
        assert config.VISION_MODEL == "gpt-4o"
        assert config.TEXT_MODEL == "gpt-4o-mini"
    
    def test_vision_model_for_images_and_pdfs(self):
        """CHK044: gpt-4o used for images and PDFs (vision tasks)."""
        config = MediaConfig()
        # Vision model should be gpt-4o (not gpt-4-vision-preview)
        assert config.VISION_MODEL == "gpt-4o"
        assert "vision" not in config.VISION_MODEL.lower()  # Not the old preview name
    
    def test_text_model_for_docx_and_analysis(self):
        """CHK045: gpt-4o-mini used for DOCX and document analysis."""
        config = MediaConfig()
        assert config.TEXT_MODEL == "gpt-4o-mini"
    
    def test_max_download_retries(self):
        """CHK048: 1 retry max (2 total attempts)."""
        config = MediaConfig()
        assert config.MAX_DOWNLOAD_RETRIES == 1
    
    def test_retry_logic_clarification(self):
        """CHK048: Clarify retry means 1 additional attempt after initial failure."""
        config = MediaConfig()
        # 1 retry = 2 total attempts (original + 1 retry)
        assert config.MAX_DOWNLOAD_RETRIES == 1
        # This will result in 2 total attempts in implementation
    
    def test_rawtext_encoding_utf8(self):
        """CHK023: UTF-8 encoding for Hebrew support in .rawtext files."""
        config = MediaConfig()
        assert config.RAWTEXT_ENCODING == "utf-8"
    
    def test_rawtext_encoding_supports_hebrew(self):
        """CHK006-010: Verify UTF-8 can handle Hebrew characters."""
        config = MediaConfig()
        # UTF-8 must support Hebrew text
        assert config.RAWTEXT_ENCODING == "utf-8"
        # Test that encoding name is lowercase (standard Python encoding name)
        assert config.RAWTEXT_ENCODING.islower()


class TestMediaConfigMimeTypes:
    """Test MIME type mappings for format validation."""
    
    def test_image_mime_types(self):
        """Image MIME types for JPG/JPEG/PNG."""
        config = MediaConfig()
        
        # Should have MIME type mappings
        assert hasattr(config, 'IMAGE_MIME_TYPES')
        assert 'image/jpeg' in config.IMAGE_MIME_TYPES
        assert 'image/png' in config.IMAGE_MIME_TYPES
    
    def test_document_mime_types(self):
        """Document MIME types for PDF/DOCX."""
        config = MediaConfig()
        
        assert hasattr(config, 'DOCUMENT_MIME_TYPES')
        assert 'application/pdf' in config.DOCUMENT_MIME_TYPES
        # DOCX has long MIME type
        assert any('wordprocessing' in mime for mime in config.DOCUMENT_MIME_TYPES)
    
    def test_gif_mime_type_not_supported(self):
        """CHK040: GIF MIME type not in supported list."""
        config = MediaConfig()
        
        all_mime_types = config.IMAGE_MIME_TYPES + config.DOCUMENT_MIME_TYPES
        assert 'image/gif' not in all_mime_types
    
    def test_txt_mime_type_not_supported(self):
        """CHK041: TXT MIME type not in supported list."""
        config = MediaConfig()
        
        all_mime_types = config.IMAGE_MIME_TYPES + config.DOCUMENT_MIME_TYPES
        assert 'text/plain' not in all_mime_types


class TestMediaConfigConstants:
    """Test additional configuration constants."""
    
    def test_config_is_singleton_or_class_constants(self):
        """Config should provide constants (class-level or instance)."""
        config1 = MediaConfig()
        config2 = MediaConfig()
        
        # Constants should be the same across instances
        assert config1.MAX_FILE_SIZE_BYTES == config2.MAX_FILE_SIZE_BYTES
        assert config1.PDF_DPI == config2.PDF_DPI
        assert config1.VISION_MODEL == config2.VISION_MODEL
    
    def test_storage_base_is_path_object(self):
        """CHK042: STORAGE_BASE should be a Path object for consistency."""
        config = MediaConfig()
        assert isinstance(config.STORAGE_BASE, Path)
    
    def test_file_size_constants_consistent(self):
        """CHK002: MB and bytes values must match."""
        config = MediaConfig()
        assert config.MAX_FILE_SIZE_BYTES == config.MAX_FILE_SIZE_MB * 1024 * 1024
