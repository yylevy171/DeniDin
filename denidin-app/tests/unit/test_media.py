"""
Unit tests for Media model (Feature 003 Phase 3.1)
Test-Driven Development: Write tests FIRST, then implement
"""
import pytest
from src.models.media import Media, MAX_MEDIA_SIZE


class TestMedia:
    """Test suite for in-memory media handling."""
    
    def test_create_media_from_bytes(self):
        """Test creating Media instance from bytes."""
        data = b"fake image data"
        media = Media.from_bytes(data, "image/jpeg", "test.jpg")
        
        assert media.data == data
        assert media.mime_type == "image/jpeg"
        assert media.filename == "test.jpg"
        assert media.size == len(data)
    
    def test_create_media_without_filename(self):
        """Test creating Media without filename (optional)."""
        data = b"fake image data"
        media = Media.from_bytes(data, "image/png")
        
        assert media.data == data
        assert media.mime_type == "image/png"
        assert media.filename is None
    
    def test_media_size_property(self):
        """Test media size property returns byte count."""
        data = b"x" * 1000
        media = Media.from_bytes(data, "image/jpeg")
        
        assert media.size == 1000
    
    def test_to_base64(self):
        """Test base64 encoding of media data."""
        data = b"Hello World"
        media = Media.from_bytes(data, "image/jpeg")
        
        # Expected base64 for "Hello World"
        expected = "SGVsbG8gV29ybGQ="
        assert media.to_base64() == expected
    
    def test_get_data_url(self):
        """Test data URL generation for API calls."""
        data = b"test"
        media = Media.from_bytes(data, "image/png")
        
        data_url = media.get_data_url()
        
        assert data_url.startswith("data:image/png;base64,")
        assert "dGVzdA==" in data_url  # base64 of "test"
    
    def test_reject_oversized_media(self):
        """Test that media exceeding 10MB is rejected."""
        # Create data just over 10MB
        oversized_data = b"x" * (MAX_MEDIA_SIZE + 1)
        
        with pytest.raises(ValueError) as excinfo:
            Media.from_bytes(oversized_data, "image/jpeg")
        
        assert "exceeds maximum" in str(excinfo.value)
        assert str(MAX_MEDIA_SIZE) in str(excinfo.value)
    
    def test_accept_max_size_media(self):
        """Test that media at exactly 10MB is accepted."""
        # Create data at exactly 10MB
        max_size_data = b"x" * MAX_MEDIA_SIZE
        
        media = Media.from_bytes(max_size_data, "application/pdf")
        
        assert media.size == MAX_MEDIA_SIZE
        assert media.mime_type == "application/pdf"
    
    def test_various_mime_types(self):
        """Test Media works with various MIME types."""
        test_cases = [
            ("image/jpeg", "photo.jpg"),
            ("image/png", "screenshot.png"),
            ("application/pdf", "document.pdf"),
            ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "doc.docx"),
        ]
        
        for mime_type, filename in test_cases:
            media = Media.from_bytes(b"data", mime_type, filename)
            assert media.mime_type == mime_type
            assert media.filename == filename
    
    def test_data_url_includes_correct_mime_type(self):
        """Test that data URL uses the correct MIME type."""
        media_jpeg = Media.from_bytes(b"jpg", "image/jpeg")
        media_png = Media.from_bytes(b"png", "image/png")
        media_pdf = Media.from_bytes(b"pdf", "application/pdf")
        
        assert media_jpeg.get_data_url().startswith("data:image/jpeg;base64,")
        assert media_png.get_data_url().startswith("data:image/png;base64,")
        assert media_pdf.get_data_url().startswith("data:application/pdf;base64,")
    
    def test_empty_media_allowed(self):
        """Test that empty media (0 bytes) is allowed."""
        media = Media.from_bytes(b"", "image/jpeg")
        
        assert media.size == 0
        assert media.to_base64() == ""
        assert media.get_data_url() == "data:image/jpeg;base64,"
