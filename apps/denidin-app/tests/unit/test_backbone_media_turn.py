"""Unit tests (Feature 063, 2026-09-30): the Backbone media turn -
the first-round "[מדיה מצורפת: ...]" marker, analyze_media filling the extracted
text into the already-stored media message (same field the legacy MediaHandler
path sets), record_planning_status storing its note the moment it's recorded,
and MediaFileManager.store_media."""
import time
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.backbone.backbone import Backbone
from src.capabilities.media_analysis.handler import dispatch_direct_tool_call
from src.core.chat_log import ChatLog
from src.managers.media_file_manager import MediaFileManager
from src.models.config import AppConfiguration
from src.models.media import Media
from src.models.message import AIRequest, WhatsAppMessage
from tests.backbone_test_support import make_session_manager

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
    session_manager = make_session_manager()
    chat_log = ChatLog(session_manager, None, rbac_enabled=False)
    return Backbone(MagicMock(), config, session_manager=session_manager, chat_log=chat_log)


def _inbound(text="", message_id="msg-media-1"):
    return WhatsAppMessage(
        message_id=message_id, chat_id=CHAT_ID, sender_id=SENDER, sender_name="Yaron",
        text_content=text, timestamp=int(time.time()), message_type="imageMessage",
        is_group=False, received_timestamp=datetime.now(timezone.utc),
        whatsapp_id_message="WA-media-1",
    )


def _request(user_prompt: str) -> AIRequest:
    return AIRequest(user_prompt=user_prompt, constitution="", max_tokens=100,
                     model="m", chat_id=CHAT_ID, message_id="msg-media-1",
                     timestamp=1_780_000_000)


def _media_context(media_type="image", filename="receipt.jpg", **extra):
    ctx = {"is_media": True, "media_type": media_type,
           "media": Media(data=b"x", mime_type="image/jpeg", filename=filename)}
    ctx.update(extra)
    return ctx


def _stored_messages(backbone):
    sm = backbone.session_manager
    session = sm.get_session(CHAT_ID)
    return [mdata for _mid, mdata in sm._iter_persisted_messages(session, live_only=True)]


class TestFirstRoundMarker:
    def test_text_turn_is_the_plain_prompt(self, backbone):
        assert Backbone._first_round_user_content(_request("שלום"), {}, is_media=False) == "שלום"

    def test_media_turn_with_caption_prefixes_the_marker(self):
        content = Backbone._first_round_user_content(
            _request("מה זה?"), _media_context(), is_media=True)
        assert content == "[מדיה מצורפת: תמונה, קובץ: receipt.jpg]\nמה זה?"

    def test_media_turn_without_caption_is_the_marker_only(self):
        content = Backbone._first_round_user_content(
            _request(""), _media_context("pdf", "agreement.pdf"), is_media=True)
        assert content == "[מדיה מצורפת: PDF, קובץ: agreement.pdf]"

    def test_docx_label(self):
        content = Backbone._first_round_user_content(
            _request(""), _media_context("docx", "a.docx"), is_media=True)
        assert content.startswith("[מדיה מצורפת: מסמך Word,")


class TestAnalyzeMediaFillsExtractedTextIntoTheStoredMessage:
    def _analyze(self, backbone, extracted_text):
        backbone.chat_log.store_inbound(_inbound("מה זה?"))
        ctx = {"chat_id": CHAT_ID, "message_id": "msg-media-1",
               "media_extraction": {"extracted_text": extracted_text, "document_analysis": {}}}
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
