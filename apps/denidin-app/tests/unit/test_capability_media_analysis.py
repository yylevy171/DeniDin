"""Unit tests for the Media Analysis capability handler (T047)."""
from unittest.mock import MagicMock, patch

from src.capabilities.media_analysis.handler import extract
from src.constants.error_messages import BACKBONE_NO_MEDIA_ATTACHED


def test_extract_with_no_media_in_turn_context_returns_fallback():
    orchestrator = MagicMock()
    request = MagicMock()

    result = extract(orchestrator, request, "", "", {})
    assert result == BACKBONE_NO_MEDIA_ATTACHED


def test_extract_dispatches_to_image_extractor_for_image_media_type():
    orchestrator = MagicMock()
    request = MagicMock(timestamp=12345)
    fake_media = MagicMock()
    turn_context = {"media": fake_media, "media_type": "image", "caption": "a receipt"}

    with patch("src.handlers.extractors.image_extractor.ImageExtractor") as mock_extractor_cls:
        instance = mock_extractor_cls.return_value
        instance.analyze_media.return_value = {
            "extracted_text": "Bank transfer 500 NIS",
            "document_analysis": {"document_type": "בנק"},
        }
        result = extract(orchestrator, request, "", "", turn_context)

    instance.analyze_media.assert_called_once_with(fake_media, caption="a receipt", today_timestamp=12345)
    assert "Bank transfer 500 NIS" in result


def test_extract_unsupported_media_type_raises():
    orchestrator = MagicMock()
    request = MagicMock()
    turn_context = {"media": MagicMock(), "media_type": "video"}

    try:
        extract(orchestrator, request, "", "", turn_context)
        assert False, "expected ValueError"
    except ValueError:
        pass
