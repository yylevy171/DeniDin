"""Unit tests (Feature 063, 2026-09-30): the Backbone media turn -
the first-round "[מדיה מצורפת: ...]" marker, analyze_media recording the
extracted text on the turn, the turn persisted with image_path/extracted_text
(same as the legacy MediaHandler path), and MediaFileManager.store_media."""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.backbone.backbone import Backbone, _TurnParties
from src.capabilities.media_analysis.handler import dispatch_direct_tool_call
from src.managers.media_file_manager import MediaFileManager
from src.models.config import AppConfiguration
from src.models.media import Media
from src.models.message import AIRequest
from src.models.user import Role
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
    return Backbone(MagicMock(), config, session_manager=make_session_manager())


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
    messages_dir = sm.storage_dir / session.session_id / "messages"
    return [json.loads((messages_dir / f"{mid}.json").read_text(encoding="utf-8"))
            for mid in session.message_ids]


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


class TestAnalyzeMediaRecordsExtractedText:
    def test_extracted_text_stored_on_turn_context(self, backbone):
        ctx = {"media_extraction": {"extracted_text": "סכום: 500", "document_analysis": {}}}
        dispatch_direct_tool_call(backbone, "analyze_media", {}, ctx)
        assert ctx["extracted_text"] == "סכום: 500"

    def test_empty_extracted_text_normalizes_to_none(self, backbone):
        ctx = {"media_extraction": {"extracted_text": "", "document_analysis": {}}}
        dispatch_direct_tool_call(backbone, "analyze_media", {}, ctx)
        assert ctx["extracted_text"] is None


class TestMediaTurnPersistence:
    def _persist(self, backbone, request, turn_context):
        parties = _TurnParties(CHAT_ID, Role.GODFATHER, "Yaron", SENDER, SENDER, False, None)
        backbone._persist_turn(request, "קיבלתי", True, parties, turn_context)

    def test_user_message_carries_image_path_and_extracted_text(self, backbone):
        self._persist(backbone, _request("מה זה?"), _media_context(
            media_path="media/DD-972501234567-u.jpg", extracted_text="סכום: 500"))
        user_msg, reply = _stored_messages(backbone)
        assert user_msg["content"] == "מה זה?"
        assert user_msg["image_path"] == "media/DD-972501234567-u.jpg"
        assert user_msg["extracted_text"] == "סכום: 500"
        assert reply["content"] == "קיבלתי"
        assert reply.get("image_path") is None

    def test_captionless_media_stored_as_type_sent(self, backbone):
        self._persist(backbone, _request(""), _media_context("pdf", "a.pdf", media_path=None))
        user_msg, _ = _stored_messages(backbone)
        assert user_msg["content"] == "[pdf sent]"
        assert user_msg.get("image_path") is None

    def test_interim_progress_messages_stored_between_user_and_reply(self, backbone):
        backbone._turn_interim_messages = ["רגע, בודק..."]
        self._persist(backbone, _request("שלום"), {})
        contents = [m["content"] for m in _stored_messages(backbone)]
        assert contents == ["שלום", "רגע, בודק...", "קיבלתי"]
        assert backbone._turn_interim_messages == []


class TestStoreMedia:
    def test_returns_path_relative_to_data_root(self, tmp_path):
        context = SimpleNamespace(config=SimpleNamespace(data_root=str(tmp_path)))
        manager = MediaFileManager(context)
        relative = manager.store_media(b"bytes", "photo.JPG", "972501234567")
        assert relative.startswith("media/DD-972501234567-")
        assert relative.endswith(".jpg")
        assert (tmp_path / relative).read_bytes() == b"bytes"
