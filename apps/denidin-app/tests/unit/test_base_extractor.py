"""
Tests for MediaExtractor base interface (Feature 003 Phase 4).

Tests the interface contract that all extractors must implement.
"""
import pytest
from src.handlers.extractors.base import MediaExtractor
from src.models.media import Media


class ConcreteExtractor(MediaExtractor):
    """Test implementation of MediaExtractor."""
    
    def analyze_media(self, media: Media):
        return {
            "raw_response": "Sample analysis response",
            "extraction_quality": "high",
            "warnings": [],
            "model_used": "test-model"
        }


def test_media_extractor_is_abstract():
    """MediaExtractor cannot be instantiated directly."""
    with pytest.raises(TypeError):
        MediaExtractor(None)


def test_concrete_implementation_requires_extract_text():
    """Concrete extractors must implement extract_text()."""
    
    class IncompleteExtractor(MediaExtractor):
        pass
    
    with pytest.raises(TypeError):
        IncompleteExtractor(None)


def test_extract_text_returns_required_fields(mock_denidin_context):
    """analyze_media() must return all required fields."""
    extractor = ConcreteExtractor(mock_denidin_context)
    media = Media(
        data=b"test",
        mime_type="test/test"
    )
    
    result = extractor.analyze_media(media)
    
    # Verify all required fields present
    assert "raw_response" in result
    assert "extraction_quality" in result
    assert "warnings" in result
    assert "model_used" in result



def test_supports_analysis_default_true(mock_denidin_context):
    """Default supports_analysis() returns True."""
    extractor = ConcreteExtractor(mock_denidin_context)
    assert extractor.supports_analysis() is True


@pytest.fixture
def mock_denidin_context():
    """Mock DeniDin context for testing."""
    from unittest.mock import Mock
    context = Mock()
    context.config = Mock()
    return context
