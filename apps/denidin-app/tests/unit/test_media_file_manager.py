"""
Unit tests for MediaFileManager - file download, validation, and storage.

TASK-006: Media File Manager Test File (TEST) - TDD Red Phase
All tests should FAIL initially - MediaFileManager doesn't exist yet.

CHK References: CHK001-005 (file validation), CHK019-024 (storage), 
                CHK039-041 (format support), CHK048 (retry), CHK075-076 (boundaries)
"""
import pytest
import requests
from unittest.mock import Mock, patch, mock_open
from pathlib import Path
from datetime import datetime, timezone
from src.managers.media_file_manager import MediaFileManager


@pytest.fixture
def mock_denidin():
    """Create mock DeniDin context for MediaFileManager."""
    mock = Mock()
    mock.config.data_root = "/tmp/test_data"
    return mock


class TestMediaFileManagerDownload:
    """Test file download functionality with retry logic."""
    
    def test_download_file_success(self, mock_denidin):
        """CHK064: Successful file download returns content."""
        manager = MediaFileManager(mock_denidin)
        with patch('src.managers.media_file_manager.requests.get') as mock_get:
            mock_response = Mock()
            mock_response.content = b"file content"
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response
            
            content, success = manager.download_file("https://example.com/file.pdf")
            
            assert success is True
            assert content == b"file content"
            mock_get.assert_called_once()
    
    def test_download_file_retry_on_failure(self, mock_denidin):
        """CHK048: Retry once on network failure, then succeed."""
        manager = MediaFileManager(mock_denidin)
        with patch('src.managers.media_file_manager.requests.get') as mock_get:
            # First call fails, second succeeds
            mock_response = Mock()
            mock_response.content = b"file content"
            mock_response.raise_for_status = Mock()
            mock_get.side_effect = [
                requests.RequestException("Network error"),
                mock_response
            ]
            
            content, success = manager.download_file("https://example.com/file.pdf")
            
            assert success is True
            assert content == b"file content"
            assert mock_get.call_count == 2  # Original + 1 retry
    
    def test_download_file_max_retries_exceeded(self, mock_denidin):
        """CHK048: Fail after 1 retry (2 total attempts)."""
        manager = MediaFileManager(mock_denidin)
        with patch('src.managers.media_file_manager.requests.get') as mock_get:
            mock_get.side_effect = requests.RequestException("Network error")
            
            content, success = manager.download_file("https://example.com/file.pdf")
            
            assert success is False
            assert content == b""  # Returns empty bytes on failure
            assert mock_get.call_count == 2  # Original + 1 retry


class TestMediaFileManagerValidation:
    """Test file size and format validation."""
    
    def test_validate_file_size_under_limit(self, mock_denidin):
        """CHK001-002: File under 10MB passes validation."""
        manager = MediaFileManager(mock_denidin)
        manager.validate_file_size(5 * 1024 * 1024)  # 5MB - should not raise
    
    def test_validate_file_size_over_limit(self, mock_denidin):
        """CHK001-002: File over 10MB raises ValueError."""
        manager = MediaFileManager(mock_denidin)
        with pytest.raises(ValueError, match="File too large"):
            manager.validate_file_size(15 * 1024 * 1024)
    
    def test_validate_file_size_exactly_10mb(self, mock_denidin):
        """CHK076: Exactly 10MB (10,485,760 bytes) should pass."""
        manager = MediaFileManager(mock_denidin)
        manager.validate_file_size(10 * 1024 * 1024)  # Should not raise
    
    def test_validate_zero_byte_file(self, mock_denidin):
        """CHK075: Reject 0-byte files as empty."""
        manager = MediaFileManager(mock_denidin)
        with pytest.raises(ValueError, match="File is empty"):
            manager.validate_file_size(0)
    
    def test_validate_format_jpg(self, mock_denidin):
        """CHK039: JPG is supported image format."""
        manager = MediaFileManager(mock_denidin)
        media_type = manager.validate_format("photo.jpg", "image/jpeg")
        assert media_type == "image"
    
    def test_validate_format_jpeg(self, mock_denidin):
        """CHK039: JPEG variant supported (case-insensitive)."""
        manager = MediaFileManager(mock_denidin)
        media_type = manager.validate_format("photo.JPEG", "image/jpeg")
        assert media_type == "image"
    
    def test_validate_format_png(self, mock_denidin):
        """CHK039: PNG is supported image format."""
        manager = MediaFileManager(mock_denidin)
        media_type = manager.validate_format("diagram.png", "image/png")
        assert media_type == "image"
    
    def test_validate_format_pdf(self, mock_denidin):
        """CHK039: PDF is supported document format."""
        manager = MediaFileManager(mock_denidin)
        media_type = manager.validate_format("contract.pdf", "application/pdf")
        assert media_type == "pdf"
    
    def test_validate_format_docx(self, mock_denidin):
        """CHK039: DOCX is supported document format."""
        manager = MediaFileManager(mock_denidin)
        media_type = manager.validate_format(
            "report.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
        assert media_type == "docx"
    
    def test_validate_format_gif_rejected(self, mock_denidin):
        """CHK040: GIF not supported - raise ValueError."""
        manager = MediaFileManager(mock_denidin)
        with pytest.raises(ValueError, match="Unsupported format: gif"):
            manager.validate_format("animation.gif", "image/gif")
    
    def test_validate_format_txt_rejected(self, mock_denidin):
        """CHK041: TXT not supported - raise ValueError."""
        manager = MediaFileManager(mock_denidin)
        with pytest.raises(ValueError, match="Unsupported format: txt"):
            manager.validate_format("notes.txt", "text/plain")


class TestMediaFileManagerStorage:
    """Test file storage path generation."""
    
    def test_create_storage_path_utc_timestamp(self, mock_denidin):
        """CHK019: UTC timestamp with microsecond precision in path."""
        manager = MediaFileManager(mock_denidin)
        
        with patch('pathlib.Path.mkdir') as mock_mkdir:
            path = manager.create_storage_path()
        
        # Path format: {data_root}/media/ (flat structure)
        assert str(path) == "/tmp/test_data/media"
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
    
    def test_create_storage_path_creates_directory(self, mock_denidin):
        """CHK020: Storage directory is created with parents."""
        manager = MediaFileManager(mock_denidin)
        with patch('pathlib.Path.mkdir') as mock_mkdir:
            manager.create_storage_path()
            
            mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
