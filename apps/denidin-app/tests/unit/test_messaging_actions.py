"""Shared react_to_message / send_progress_update actions (used by legacy AIHandler and backbone)."""
from unittest.mock import MagicMock, patch

from src.tool_actions.messaging_actions import (
    build_react_to_message_payload, send_progress_update_message,
)


def _request(whatsapp_id="wamid.cur"):
    request = MagicMock()
    request.original_message.whatsapp_id_message = whatsapp_id
    return request


def _session_manager(active_document_message_id=None):
    manager = MagicMock()
    manager.get_session.return_value.active_document_message_id = active_document_message_id
    return manager


def test_send_progress_update_calls_callback_marks_telemetry_and_reports_sent():
    callback, builder = MagicMock(), MagicMock()
    assert send_progress_update_message(callback, builder, "chat1", "רגע...") is True
    callback.assert_called_once_with("רגע...")
    builder.mark_progress_update_sent.assert_called_once_with()


def test_send_progress_update_without_callback_reports_not_sent():
    assert send_progress_update_message(None, None, "chat1", "רגע...") is False


def test_send_progress_update_callback_failure_is_swallowed():
    callback = MagicMock(side_effect=RuntimeError("boom"))
    assert send_progress_update_message(callback, None, "chat1", "רגע...") is False


def test_react_defaults_to_current_message_and_reports_ok():
    bot = MagicMock()
    with patch("src.tool_actions.messaging_actions.send_reaction", return_value=True) as mock_send:
        payload = build_react_to_message_payload(
            bot, _session_manager(), _request(), "chat1", {"emoji": "✅", "message_id": None}, "c1",
        )
    mock_send.assert_called_once_with(bot, "chat1", "wamid.cur", "✅")
    assert payload == {"status": "ok"}


def test_react_prefers_explicit_then_active_document_message_id():
    bot = MagicMock()
    with patch("src.tool_actions.messaging_actions.send_reaction", return_value=True) as mock_send:
        build_react_to_message_payload(
            bot, _session_manager("wamid.doc"), _request(), "chat1", {"emoji": "✅", "message_id": None}, "c1",
        )
        build_react_to_message_payload(
            bot, _session_manager("wamid.doc"), _request(), "chat1", {"emoji": "✅", "message_id": "wamid.x"}, "c2",
        )
    assert [call.args[2] for call in mock_send.call_args_list] == ["wamid.doc", "wamid.x"]


def test_react_without_bot_reports_failed():
    payload = build_react_to_message_payload(
        None, _session_manager(), _request(), "chat1", {"emoji": "✅", "message_id": None}, "c1",
    )
    assert payload == {"status": "failed"}


def test_react_send_failure_reports_failed():
    with patch("src.tool_actions.messaging_actions.send_reaction", return_value=False):
        payload = build_react_to_message_payload(
            MagicMock(), _session_manager(), _request(), "chat1", {"emoji": "✅", "message_id": None}, "c1",
        )
    assert payload == {"status": "failed"}
