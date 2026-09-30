"""Unit tests for the Media Analysis capability's `analyze_media` direct tool
(2026-09-24 "resolution" redesign)."""
from unittest.mock import MagicMock, patch

from src.capabilities.media_analysis.handler import dispatch_direct_tool_call
from src.constants.error_messages import BACKBONE_NO_MEDIA_ATTACHED


def test_no_media_in_turn_context_returns_fallback():
    assert dispatch_direct_tool_call(MagicMock(), "analyze_media", {}, {}) == BACKBONE_NO_MEDIA_ATTACHED


def test_dispatches_to_image_extractor_for_image_media_type():
    fake_media = MagicMock()
    turn_context = {"media": fake_media, "media_type": "image", "caption": "a receipt", "timestamp": 12345}

    with patch("src.handlers.extractors.image_extractor.ImageExtractor") as mock_extractor_cls:
        instance = mock_extractor_cls.return_value
        instance.analyze_media.return_value = {
            "extracted_text": "Bank transfer 500 NIS",
            "document_analysis": {"document_type": "בנק"},
        }
        result = dispatch_direct_tool_call(MagicMock(), "analyze_media", {}, turn_context)

    instance.analyze_media.assert_called_once_with(fake_media, caption="a receipt", today_timestamp=12345)
    assert "Bank transfer 500 NIS" in result


def test_already_extracted_result_is_formatted_without_a_second_call():
    turn_context = {"media_extraction": {"extracted_text": "hello", "document_analysis": {"k": 1}}}
    with patch("src.handlers.extractors.image_extractor.ImageExtractor") as mock_extractor_cls:
        result = dispatch_direct_tool_call(MagicMock(), "analyze_media", {}, turn_context)
    mock_extractor_cls.assert_not_called()
    assert "hello" in result


def test_unsupported_media_type_raises():
    try:
        dispatch_direct_tool_call(MagicMock(), "analyze_media", {}, {"media": MagicMock(), "media_type": "video"})
        assert False, "expected ValueError"
    except ValueError:
        pass
