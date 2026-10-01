"""Unit tests for the Media Analysis capability's `analyze_media` direct tool
(2026-09-24 "resolution" redesign; output carries the extractor's structured
result, 2026-10-01)."""
import json
from unittest.mock import MagicMock, patch

from src.capabilities.media_analysis.handler import (
    _ExtractorAIHandlerShim, dispatch_direct_tool_call,
)
from src.constants.error_messages import BACKBONE_NO_MEDIA_ATTACHED


def test_no_media_in_turn_context_returns_fallback():
    assert dispatch_direct_tool_call(MagicMock(), "analyze_media", {}, {}) == BACKBONE_NO_MEDIA_ATTACHED


def test_dispatches_to_image_extractor_for_image_media_type():
    fake_media = MagicMock()
    turn_context = {"media": fake_media, "media_type": "image", "caption": "a receipt", "timestamp": 12345}

    with patch("src.handlers.extractors.image_extractor.ImageExtractor") as mock_extractor_cls:
        instance = mock_extractor_cls.return_value
        instance.analyze_media.return_value = {"extracted_text": "Bank transfer 500 NIS"}
        result = dispatch_direct_tool_call(MagicMock(), "analyze_media", {}, turn_context)

    instance.analyze_media.assert_called_once_with(fake_media, caption="a receipt", today_timestamp=12345)
    assert json.loads(result)["extracted_text"] == "Bank transfer 500 NIS"


def test_already_extracted_result_is_formatted_without_a_second_call():
    turn_context = {"media_extraction": {"extracted_text": "hello", "document_analysis": {"k": 1}}}
    with patch("src.handlers.extractors.image_extractor.ImageExtractor") as mock_extractor_cls:
        result = dispatch_direct_tool_call(MagicMock(), "analyze_media", {}, turn_context)
    mock_extractor_cls.assert_not_called()
    assert json.loads(result) == {"extracted_text": "hello", "document_analysis": {"k": 1}}


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
    result = json.loads(dispatch_direct_tool_call(
        MagicMock(), "analyze_media", {}, {"media_extraction": extraction}))
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
    result = json.loads(dispatch_direct_tool_call(
        MagicMock(), "analyze_media", {}, {"media_extraction": extraction}))
    assert result["extracted_text"] == "raw vision output"


def test_extractors_get_no_conversational_prompt_to_prepend():
    """The vision model gets its extraction prompt alone - never the backbone or a
    capability prompt (2026-10-01: those made it write fake tool calls before its
    JSON). The shim's _load_constitution is what the extractors prepend."""
    assert _ExtractorAIHandlerShim(MagicMock())._load_constitution() == ""


def test_unsupported_media_type_raises():
    try:
        dispatch_direct_tool_call(MagicMock(), "analyze_media", {}, {"media": MagicMock(), "media_type": "video"})
        assert False, "expected ValueError"
    except ValueError:
        pass
