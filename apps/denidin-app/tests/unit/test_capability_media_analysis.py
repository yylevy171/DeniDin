"""Unit tests for the Media Analysis capability's `analyze_media` direct tool
(2026-09-24 "resolution" redesign; output carries the extractor's structured
result, 2026-10-01)."""
import json
from unittest.mock import MagicMock, patch

from src.capabilities.media_analysis.handler import (
    dispatch_direct_tool_call,
)
from src.constants.error_messages import BACKBONE_NO_MEDIA_ATTACHED
from src.models.media import Media


def _image(media_type="image"):
    return Media(data=b"x", mime_type="image/jpeg", filename="slip.jpg", media_type=media_type)


def _analyze_with(extraction):
    """analyze_media on an attached image whose (patched) extractor returns `extraction`."""
    with patch("src.handlers.extractors.image_extractor.ImageExtractor") as mock_extractor_cls:
        mock_extractor_cls.return_value.analyze_media.return_value = extraction
        return dispatch_direct_tool_call(MagicMock(), "analyze_media", {}, {"media": _image()})


def test_no_media_in_turn_context_returns_fallback():
    assert dispatch_direct_tool_call(MagicMock(), "analyze_media", {}, {}) == BACKBONE_NO_MEDIA_ATTACHED


def test_dispatches_to_image_extractor_for_image_media_type():
    fake_media = _image()
    turn_context = {"media": fake_media, "caption": "a receipt", "timestamp": 12345}

    with patch("src.handlers.extractors.image_extractor.ImageExtractor") as mock_extractor_cls:
        instance = mock_extractor_cls.return_value
        instance.analyze_media.return_value = {"extracted_text": "Bank transfer 500 NIS"}
        result = dispatch_direct_tool_call(MagicMock(), "analyze_media", {}, turn_context)

    instance.analyze_media.assert_called_once_with(fake_media, caption="a receipt", today_timestamp=12345)
    assert json.loads(result)["extracted_text"] == "Bank transfer 500 NIS"


def test_output_carries_the_extractors_classification_and_fields():
    """The image/PDF extractors return doc_type/fields/missing_required_fields; the
    model needs them to choose a flow and ask for what is missing - none may be
    dropped (they were, 2026-10-01: only extracted_text/document_analysis passed)."""
    extraction = {
        "extracted_text": "העברה מאסולין אסתר 554",
        "doc_type": "bank",
        "fields": {"payer_name": "אסולין אסתר", "amount": 554, "txn_date": "05/08/2026"},
        "missing_required_fields": ["bank_branch"],
        "raw_response": "העברה מאסולין אסתר 554",
        "model_used": "vision-model",
    }
    result = json.loads(_analyze_with(extraction))
    assert result == {
        "extracted_text": "העברה מאסולין אסתר 554",
        "doc_type": "bank",
        "fields": {"payer_name": "אסולין אסתר", "amount": 554, "txn_date": "05/08/2026"},
        "missing_required_fields": ["bank_branch"],
    }


def test_empty_structured_text_falls_back_to_the_raw_response():
    """The extractors' own fallback (bugfix-028 B5): when the structured text is
    empty, the raw vision output is passed on rather than nothing."""
    extraction = {"extracted_text": "", "raw_response": "raw vision output", "doc_type": "unknown"}
    result = json.loads(_analyze_with(extraction))
    assert result["extracted_text"] == "raw vision output"


def test_extractors_get_no_conversational_prompt_to_prepend():
    """The vision model gets its extraction prompt alone - never the backbone or a
    capability prompt (2026-10-01: those made it write fake tool calls before its
    JSON). extraction_prompt_prefix is what the extractors prepend."""
    from src.backbone.backbone import Backbone
    assert Backbone.extraction_prompt_prefix(MagicMock()) == ""


def test_unsupported_media_type_raises():
    try:
        dispatch_direct_tool_call(MagicMock(), "analyze_media", {}, {"media": _image("video")})
        assert False, "expected ValueError"
    except ValueError:
        pass
