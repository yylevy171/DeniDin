"""Shared react_to_message / send_progress_update actions (used by legacy AIHandler and backbone)."""
from unittest.mock import MagicMock

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


def _denidin(active_document_message_id=None, reaction_sent=True):
    """The DeniDin the actions send through (REQ-063-08) - a stand-in, so the tests
    see exactly what was asked of it."""
    denidin = MagicMock()
    denidin.session_manager = _session_manager(active_document_message_id)
    denidin.send_reaction.return_value = reaction_sent
    return denidin


def test_send_progress_update_sends_through_denidin_marks_telemetry_and_reports_sent():
    denidin, builder = MagicMock(), MagicMock()
    denidin.send_progress_update.return_value = True
    assert send_progress_update_message(denidin, builder, "chat1", "רגע...") is True
    denidin.send_progress_update.assert_called_once_with("chat1", "רגע...")
    builder.mark_progress_update_sent.assert_called_once_with()


def test_send_progress_update_not_sent_reports_not_sent():
    """No turn in progress in the chat (or no WhatsApp side) - DeniDin sends nothing."""
    denidin, builder = MagicMock(), MagicMock()
    denidin.send_progress_update.return_value = None
    assert send_progress_update_message(denidin, builder, "chat1", "רגע...") is False
    builder.mark_progress_update_sent.assert_not_called()


def test_send_progress_update_without_text_sends_nothing():
    denidin = MagicMock()
    assert send_progress_update_message(denidin, None, "chat1", "") is False
    denidin.send_progress_update.assert_not_called()


def test_send_progress_update_send_failure_is_swallowed():
    denidin = MagicMock()
    denidin.send_progress_update.side_effect = RuntimeError("boom")
    assert send_progress_update_message(denidin, None, "chat1", "רגע...") is False


def test_react_defaults_to_current_message_and_reports_ok():
    denidin = _denidin()
    payload = build_react_to_message_payload(
        denidin, _request(), "chat1", {"emoji": "✅", "message_id": None}, "c1",
    )
    denidin.send_reaction.assert_called_once_with("chat1", "wamid.cur", "✅")
    assert payload == {"status": "ok"}


def test_react_prefers_explicit_then_active_document_message_id():
    denidin = _denidin("wamid.doc")
    build_react_to_message_payload(
        denidin, _request(), "chat1", {"emoji": "✅", "message_id": None}, "c1",
    )
    build_react_to_message_payload(
        denidin, _request(), "chat1", {"emoji": "✅", "message_id": "wamid.x"}, "c2",
    )
    assert [call.args[1] for call in denidin.send_reaction.call_args_list] == ["wamid.doc", "wamid.x"]


def test_react_with_nothing_to_react_to_reports_failed_and_sends_nothing():
    denidin = _denidin()
    payload = build_react_to_message_payload(
        denidin, _request(whatsapp_id=None), "chat1", {"emoji": "✅", "message_id": None}, "c1",
    )
    assert payload == {"status": "failed"}
    denidin.send_reaction.assert_not_called()


def test_react_send_failure_reports_failed():
    payload = build_react_to_message_payload(
        _denidin(reaction_sent=False), _request(), "chat1", {"emoji": "✅", "message_id": None}, "c1",
    )
    assert payload == {"status": "failed"}
