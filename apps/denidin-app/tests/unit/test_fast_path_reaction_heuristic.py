"""
Unit tests for Feature 084's fast-path reaction heuristic (denidin.py).

Classification logic only - no network, no LLM call. `send_reaction` is stubbed
at the Green API boundary (permitted at the unit tier, CONSTITUTION §V).
Confirms classification IS the entire gate (contracts/group-discretion-gating.md's
Correction, 2026-09-12) - no separate addressed-to-bot predicate exists or is
checked.
"""
from unittest.mock import Mock, patch

import denidin as denidin_module


def _notification(type_message, *, text=None, id_message="wamid.1", chat_id="chat1@c.us"):
    if type_message == "extendedTextMessage":
        message_data = {"extendedTextMessageData": {"text": text or ""}}
    elif type_message == "textMessage":
        message_data = {"textMessageData": {"textMessage": text or ""}}
    else:
        message_data = {}
    return Mock(event={
        "idMessage": id_message,
        "messageData": {"typeMessage": type_message, **message_data},
        "senderData": {"chatId": chat_id},
    })


class TestClassifyFastPathReaction:
    def test_image_message_returns_a_media_pool_emoji(self):
        result = denidin_module._classify_fast_path_reaction(
            "imageMessage", _notification("imageMessage")
        )
        assert result in denidin_module._FAST_PATH_MEDIA_REACTIONS

    def test_document_message_returns_a_media_pool_emoji(self):
        result = denidin_module._classify_fast_path_reaction(
            "documentMessage", _notification("documentMessage")
        )
        assert result in denidin_module._FAST_PATH_MEDIA_REACTIONS

    def test_action_verb_text_message_returns_an_action_pool_emoji(self):
        result = denidin_module._classify_fast_path_reaction(
            "textMessage", _notification("textMessage", text="צור חשבונית ל2000 שח")
        )
        assert result in denidin_module._FAST_PATH_ACTION_REACTIONS

    def test_action_verb_extended_text_message_returns_an_action_pool_emoji(self):
        result = denidin_module._classify_fast_path_reaction(
            "extendedTextMessage",
            _notification("extendedTextMessage", text="please create an invoice"),
        )
        assert result in denidin_module._FAST_PATH_ACTION_REACTIONS

    def test_ambient_chatter_with_no_action_verb_returns_none(self):
        result = denidin_module._classify_fast_path_reaction(
            "textMessage", _notification("textMessage", text="haha that's so funny")
        )
        assert result is None

    def test_trivial_1on1_ok_returns_none(self):
        result = denidin_module._classify_fast_path_reaction(
            "textMessage", _notification("textMessage", text="ok thanks")
        )
        assert result is None

    def test_video_message_returns_none_no_matching_heuristic(self):
        result = denidin_module._classify_fast_path_reaction(
            "videoMessage", _notification("videoMessage")
        )
        assert result is None

    def test_edited_message_returns_none(self):
        result = denidin_module._classify_fast_path_reaction(
            "editedMessage", _notification("editedMessage")
        )
        assert result is None


class TestDispatchFastPathReaction:
    """Confirms the hook resolves id/chatId and calls send_reaction, and never
    raises - even on a malformed/incomplete notification."""

    def _denidin_app_with_bot(self):
        app = Mock()
        app.green_api_bot = Mock()
        return app

    def test_actionable_media_message_calls_send_reaction_with_resolved_ids(self):
        app = self._denidin_app_with_bot()
        with patch.object(denidin_module, "denidin_app", app), \
             patch("denidin.send_reaction") as mock_send:
            denidin_module._dispatch_fast_path_reaction(
                "imageMessage",
                _notification("imageMessage", id_message="wamid.42", chat_id="972501234567@c.us"),
            )
        mock_send.assert_called_once()
        args = mock_send.call_args[0]
        assert args[0] is app.green_api_bot
        assert args[1] == "972501234567@c.us"
        assert args[2] == "wamid.42"
        assert args[3] in denidin_module._FAST_PATH_MEDIA_REACTIONS

    def test_non_actionable_message_never_calls_send_reaction(self):
        app = self._denidin_app_with_bot()
        with patch.object(denidin_module, "denidin_app", app), \
             patch("denidin.send_reaction") as mock_send:
            denidin_module._dispatch_fast_path_reaction(
                "textMessage", _notification("textMessage", text="lol ok")
            )
        mock_send.assert_not_called()

    def test_missing_id_message_never_calls_send_reaction(self):
        app = self._denidin_app_with_bot()
        notification = _notification("imageMessage")
        notification.event["idMessage"] = None
        with patch.object(denidin_module, "denidin_app", app), \
             patch("denidin.send_reaction") as mock_send:
            denidin_module._dispatch_fast_path_reaction("imageMessage", notification)
        mock_send.assert_not_called()

    def test_no_green_api_bot_available_never_raises_and_skips(self):
        app = Mock()
        app.green_api_bot = None
        with patch.object(denidin_module, "denidin_app", app), \
             patch("denidin.send_reaction") as mock_send:
            denidin_module._dispatch_fast_path_reaction("imageMessage", _notification("imageMessage"))
        mock_send.assert_not_called()

    def test_denidin_app_none_never_raises(self):
        with patch.object(denidin_module, "denidin_app", None), \
             patch("denidin.send_reaction") as mock_send:
            denidin_module._dispatch_fast_path_reaction("imageMessage", _notification("imageMessage"))
        mock_send.assert_not_called()

    def test_exception_inside_is_caught_and_logged_never_raises(self):
        app = self._denidin_app_with_bot()
        with patch.object(denidin_module, "denidin_app", app), \
             patch("denidin.send_reaction", side_effect=RuntimeError("boom")):
            # Must not raise.
            denidin_module._dispatch_fast_path_reaction("imageMessage", _notification("imageMessage"))

    def test_malformed_notification_with_no_event_attribute_never_raises(self):
        app = self._denidin_app_with_bot()
        with patch.object(denidin_module, "denidin_app", app), \
             patch("denidin.send_reaction") as mock_send:
            denidin_module._dispatch_fast_path_reaction("imageMessage", object())
        mock_send.assert_not_called()


class TestDispatchNotificationCallsFastPath:
    """Confirms dispatch_notification() wires the hook in without altering the
    real handler's own invocation."""

    def test_hook_is_called_before_the_real_handler_and_handler_still_runs(self, monkeypatch):
        calls = []
        monkeypatch.setitem(
            denidin_module.HANDLER_REGISTRY, "imageMessage", lambda n: calls.append("handler")
        )
        with patch("denidin._dispatch_fast_path_reaction") as mock_fast_path:
            mock_fast_path.side_effect = lambda *a: calls.append("fast_path")
            denidin_module.dispatch_notification("imageMessage", _notification("imageMessage"))
        assert calls == ["fast_path", "handler"]
