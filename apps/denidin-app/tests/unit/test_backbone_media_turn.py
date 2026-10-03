"""Unit tests (Feature 063, 2026-09-30): the Backbone media turn -
the first-round "[מדיה מצורפת: ...]" marker, analyze_media filling the extracted
text into the already-stored media message (same field the legacy MediaHandler
path sets), record_planning_status storing its note the moment it's recorded,
and MediaFileManager.store_media."""
import time
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.backbone.backbone import Backbone
from src.capabilities.media_analysis.handler import dispatch_direct_tool_call
from src.managers.media_file_manager import MediaFileManager
from src.models.config import AppConfiguration
from src.models.media import Media
from src.models.message import AIRequest, WhatsAppMessage
from tests.backbone_test_support import make_backbone, make_session_manager

CHAT_ID = "972501234567@c.us"
SENDER = "972501234567@c.us"


@pytest.fixture
def backbone(tmp_path):
    base = tmp_path / "config"
    (base / "prompts" / "capabilities").mkdir(parents=True)
    (base / "prompts" / "backbone.md").write_text("BACKBONE", encoding="utf-8")
    config = AppConfiguration(
        green_api_instance_id="x", green_api_token="y", ai_api_key="z",
        backbone_config={"base_dir": str(base)},
    )
    return make_backbone(MagicMock(), config, session_manager=make_session_manager())


def _inbound(text="", message_id="msg-media-1"):
    return WhatsAppMessage(
        message_id=message_id, chat_id=CHAT_ID, sender_id=SENDER, sender_name="Yaron",
        text_content=text, timestamp=int(time.time()), message_type="imageMessage",
        is_group=False, received_timestamp=datetime.now(timezone.utc),
        whatsapp_id_message="WA-media-1",
    )


def _tap_message():
    """The tapped buttons message's sender/chat details, as WhatsAppMessage carries them."""
    from types import SimpleNamespace
    return SimpleNamespace(chat_id=CHAT_ID, sender_id=SENDER, message_id="TAP-1",
                           sender_display_name="Yaron", is_group=False, chat_name=None)


def _request(user_prompt: str, media=None) -> AIRequest:
    return AIRequest(user_prompt=user_prompt, constitution="", max_tokens=100,
                     model="m", chat_id=CHAT_ID, message_id="msg-media-1",
                     timestamp=1_780_000_000, media=media)


def _media(media_type="image", filename="receipt.jpg"):
    return Media(data=b"x", mime_type="image/jpeg", filename=filename, media_type=media_type)


def _stored_messages(backbone):
    sm = backbone.session_manager
    session = sm.get_session(CHAT_ID)
    return [mdata for _mid, mdata in sm._iter_persisted_messages(session, live_only=True)]


class TestFirstRoundMarker:
    def test_text_turn_is_the_plain_prompt(self, backbone):
        assert Backbone._first_round_user_content(_request("שלום")) == "שלום"

    def test_media_turn_with_caption_prefixes_the_marker(self):
        content = Backbone._first_round_user_content(_request("מה זה?", _media()))
        assert content == "[מדיה מצורפת: תמונה, קובץ: receipt.jpg]\nמה זה?"

    def test_media_turn_without_caption_is_the_marker_only(self):
        content = Backbone._first_round_user_content(_request("", _media("pdf", "agreement.pdf")))
        assert content == "[מדיה מצורפת: PDF, קובץ: agreement.pdf]"

    def test_docx_label(self):
        content = Backbone._first_round_user_content(_request("", _media("docx", "a.docx")))
        assert content.startswith("[מדיה מצורפת: מסמך Word,")


class TestAnalyzeMediaFillsExtractedTextIntoTheStoredMessage:
    def _analyze(self, backbone, extracted_text):
        backbone.denidin.store_inbound(_inbound("מה זה?"))
        ctx = {"chat_id": CHAT_ID, "message_id": "msg-media-1", "media": _media()}
        with patch("src.handlers.extractors.image_extractor.ImageExtractor") as mock_extractor_cls:
            mock_extractor_cls.return_value.analyze_media.return_value = {
                "extracted_text": extracted_text, "document_analysis": {}}
            dispatch_direct_tool_call(backbone, "analyze_media", {}, ctx)
        [stored] = _stored_messages(backbone)
        return stored

    def test_extracted_text_filled_in(self, backbone):
        stored = self._analyze(backbone, "סכום: 500")
        assert stored["content"] == "מה זה?"
        assert stored["extracted_text"] == "סכום: 500"

    def test_empty_extracted_text_normalizes_to_none(self, backbone):
        assert self._analyze(backbone, "")["extracted_text"] is None


class TestPlanningNoteStoredImmediately:
    def test_note_stored_the_moment_it_is_recorded(self, backbone):
        backbone._turn_original_message = _inbound("שלום")
        result = backbone._dispatch_resolution_tool(
            "record_planning_status",
            {"where_i_was": "התחלה", "this_turns_purpose": "לענות", "expectation": "תשובה"},
            CHAT_ID)

        assert result == "recorded"
        [note] = _stored_messages(backbone)
        assert note["ai_required_role"] == "assistant"
        assert note["content"].startswith("[[INTERNAL_PLANNING_NOTE]]\nWHERE I WAS: התחלה")


class TestStoreMedia:
    def test_returns_path_relative_to_data_root(self, tmp_path):
        context = SimpleNamespace(config=SimpleNamespace(data_root=str(tmp_path)))
        manager = MediaFileManager(context)
        relative = manager.store_media(b"bytes", "photo.JPG", "972501234567")
        assert relative.startswith("media/DD-972501234567-")
        assert relative.endswith(".jpg")
        assert (tmp_path / relative).read_bytes() == b"bytes"


class _RecordingBackbone(Backbone):
    """Records what a turn is run with instead of calling the model."""
    def single_turn(self, request, **kwargs):  # pylint: disable=arguments-differ
        self.turn_kwargs = kwargs
        return "ran"


class TestButtonTapRunsAsAFullTurn:
    """2026-09-30: a live tap's turn gets the same sender/chat details as a typed turn
    (REQ-063-08: its progress updates go through DeniDin's turn in progress, which
    denidin.py begins around the tap - no callback is passed)."""

    def test_live_tap_passes_sender_details(self, backbone):
        tapping = make_backbone(MagicMock(), backbone.config, backbone_class=_RecordingBackbone,
                                     session_manager=backbone.session_manager)
        tapping.session_manager.set_approval_message_id(CHAT_ID, "WA-BUTTONS-1")
        result = tapping.resolve_button_tap(
            _tap_message(), "denidin_approve", "WA-BUTTONS-1", user_role="godfather")

        assert result == "ran"
        assert tapping.turn_kwargs["sender"] == "Yaron"
        assert tapping.turn_kwargs["user_phone"] == SENDER

    def test_stale_tap_runs_nothing(self, backbone):
        tapping = make_backbone(MagicMock(), backbone.config, backbone_class=_RecordingBackbone,
                                     session_manager=backbone.session_manager)
        tapping.session_manager.set_approval_message_id(CHAT_ID, "WA-BUTTONS-1")

        assert tapping.resolve_button_tap(
            _tap_message(), "denidin_approve", "WA-OLD") is None
        assert not hasattr(tapping, "turn_kwargs")
