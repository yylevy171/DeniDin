"""
Tests for MediaExtractor base interface (Feature 003 Phase 4).

Tests the interface contract that all extractors must implement.
"""
import pytest
from src.utils.extractors.base import MediaExtractor
from src.models.media import Media


class ConcreteExtractor(MediaExtractor):
    """Test implementation of MediaExtractor."""
    
    def extract_text(self, media: Media):
        return {
            "extracted_text": "Sample text",
            "document_analysis": {
                "document_type": "generic",
                "summary": "A sample document",
                "key_points": ["Point 1", "Point 2"]
            },
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
    """extract_text() must return all required fields."""
    extractor = ConcreteExtractor(mock_denidin_context)
    media = Media(
        data=b"test",
        mime_type="test/test"
    )
    
    result = extractor.extract_text(media)
    
    # Verify all required fields present
    assert "extracted_text" in result
    assert "document_analysis" in result
    assert "extraction_quality" in result
    assert "warnings" in result
    assert "model_used" in result


def test_document_analysis_has_required_structure(mock_denidin_context):
    """document_analysis must have document_type, summary, key_points."""
    extractor = ConcreteExtractor(mock_denidin_context)
    media = Media(
        data=b"test",
        mime_type="test/test"
    )
    
    result = extractor.extract_text(media)
    analysis = result["document_analysis"]
    
    assert "document_type" in analysis
    assert "summary" in analysis
    assert "key_points" in analysis
    assert isinstance(analysis["key_points"], list)


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
