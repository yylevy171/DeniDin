"""
Unit tests for DeniDinGreenAPIBot (bugfix-020).

Reproduces the real, confirmed Green API behavior: on an empty notification queue, the SDK's
Response.data is either the JSON literal `null` (older backend) or the library's own JSON-decode-
failure fallback string "[]" (the officially-documented genuinely-empty-body case that crashed
denidin-app-prod/dev's startup on 2026-08-03). Verifies both the corrected startup drain and the
corrected run_forever() polling loop treat any non-dict Response.data as "queue empty" instead of
crashing (startup) or logging+sleeping on every idle poll (run_forever).
"""
from unittest.mock import Mock, patch, call

from whatsapp_chatbot_python import GreenAPIBot

from src.utils.green_api_bot import DeniDinGreenAPIBot, _notification_data_or_none, send_proactive_message


def _fake_response(data):
    response = Mock()
    response.data = data
    return response


class TestNotificationDataOrNone:
    def test_real_notification_dict_passes_through(self):
        assert _notification_data_or_none({"receiptId": 1, "body": {}}) == {"receiptId": 1, "body": {}}

    def test_null_body_is_none(self):
        assert _notification_data_or_none(None) is None

    def test_empty_body_fallback_string_is_none(self):
        # whatsapp_api_client_python.Response.__init__'s fallback for a JSON-decode failure
        # (e.g. a genuinely empty HTTP body) - a truthy STRING, not None/[] - is the root cause
        # of bugfix-020: it must be treated as "no notification", not indexed like a dict.
        assert _notification_data_or_none("[]") is None

    def test_other_non_dict_is_none(self):
        assert _notification_data_or_none([]) is None
        assert _notification_data_or_none("") is None


def _make_bot(**overrides):
    """Builds a DeniDinGreenAPIBot without running the real (network-calling) Bot.__init__."""
    bot = object.__new__(DeniDinGreenAPIBot)
    bot.api = Mock()
    bot.api.session.headers = {}
    bot.logger = Mock()
    bot.router = Mock()
    bot.raise_errors = overrides.get("raise_errors", False)
    return bot


class TestDrainStartupNotifications:
    def test_stops_immediately_on_empty_body_fallback_string(self):
        """The exact bugfix-020 scenario: a fresh/drained instance whose backend returns the
        empty-body fallback "[]" right away must not crash and must not call deleteNotification."""
        bot = _make_bot()
        bot.api.receiving.receiveNotification.return_value = _fake_response("[]")

        bot._drain_startup_notifications()

        bot.api.receiving.deleteNotification.assert_not_called()

    def test_stops_on_null_body(self):
        bot = _make_bot()
        bot.api.receiving.receiveNotification.return_value = _fake_response(None)

        bot._drain_startup_notifications()

        bot.api.receiving.deleteNotification.assert_not_called()

    def test_drains_real_backlog_then_stops(self):
        bot = _make_bot()
        bot.api.receiving.receiveNotification.side_effect = [
            _fake_response({"receiptId": 1, "body": {}}),
            _fake_response({"receiptId": 2, "body": {}}),
            _fake_response("[]"),
        ]

        bot._drain_startup_notifications()

        bot.api.receiving.deleteNotification.assert_has_calls([call(1), call(2)])
        assert bot.api.receiving.deleteNotification.call_count == 2


class TestRunForever:
    @patch("src.utils.green_api_bot.time.sleep")
    def test_empty_body_does_not_log_error_or_sleep(self, mock_sleep):
        """bugfix-020's run_forever half: on a backend where an idle queue returns the empty-body
        fallback string, every poll cycle must not hit the except-Exception/5s-sleep/ERROR-log
        path - it should just continue polling."""
        bot = _make_bot()
        bot.api.receiving.receiveNotification.side_effect = [
            _fake_response("[]"),
            KeyboardInterrupt(),
        ]

        bot.run_forever()

        mock_sleep.assert_not_called()
        error_calls = [c for c in bot.logger.log.call_args_list if c.args and c.args[0] == 40]
        assert not error_calls, "no ERROR-level log expected for a genuinely empty queue"
        bot.router.route_event.assert_not_called()
        bot.api.receiving.deleteNotification.assert_not_called()

    def test_processes_real_notification_and_deletes_it(self):
        bot = _make_bot()
        bot.api.receiving.receiveNotification.side_effect = [
            _fake_response({"receiptId": 42, "body": {"typeWebhook": "incomingMessageReceived"}}),
            KeyboardInterrupt(),
        ]

        bot.run_forever()

        bot.router.route_event.assert_called_once_with({"typeWebhook": "incomingMessageReceived"})
        bot.api.receiving.deleteNotification.assert_called_once_with(42)

    @patch("src.utils.green_api_bot.time.sleep")
    def test_other_exceptions_still_caught_logged_and_slept(self, mock_sleep):
        """Unrelated failures (e.g. router.route_event raising) must keep the library's existing
        catch-log-sleep-continue behavior - this bugfix narrows the empty-queue case only."""
        bot = _make_bot()
        bot.api.receiving.receiveNotification.side_effect = [
            _fake_response({"receiptId": 1, "body": {}}),
            KeyboardInterrupt(),
        ]
        bot.router.route_event.side_effect = ValueError("boom")

        bot.run_forever()

        mock_sleep.assert_called_once_with(5.0)
        error_calls = [c for c in bot.logger.log.call_args_list if c.args and c.args[0] == 40]
        assert error_calls, "expected an ERROR-level log for the unrelated ValueError"

    def test_raise_errors_true_still_raises_wrapped_error(self):
        bot = _make_bot(raise_errors=True)
        bot.api.receiving.receiveNotification.side_effect = [
            _fake_response({"receiptId": 1, "body": {}}),
        ]
        bot.router.route_event.side_effect = ValueError("boom")

        from whatsapp_chatbot_python import GreenAPIBotError
        try:
            bot.run_forever()
            assert False, "expected GreenAPIBotError to propagate"
        except GreenAPIBotError:
            pass


class TestInit:
    def test_forces_library_drain_off_and_runs_own_drain_by_default(self):
        with patch("src.utils.green_api_bot.GreenAPIBot.__init__", return_value=None) as mock_init, \
             patch.object(DeniDinGreenAPIBot, "_drain_startup_notifications") as mock_drain:
            DeniDinGreenAPIBot("id123", "token123")

        mock_init.assert_called_once()
        assert mock_init.call_args.kwargs["delete_notifications_at_startup"] is False
        mock_drain.assert_called_once()

    def test_delete_notifications_at_startup_false_skips_our_drain_too(self):
        with patch("src.utils.green_api_bot.GreenAPIBot.__init__", return_value=None) as mock_init, \
             patch.object(DeniDinGreenAPIBot, "_drain_startup_notifications") as mock_drain:
            DeniDinGreenAPIBot("id123", "token123", delete_notifications_at_startup=False)

        assert mock_init.call_args.kwargs["delete_notifications_at_startup"] is False
        mock_drain.assert_not_called()

    def test_is_a_real_green_api_bot(self):
        assert issubclass(DeniDinGreenAPIBot, GreenAPIBot)


class TestSendProactiveMessage:
    """Feature 054 (T011a): the delivery sweep's unprompted-send helper - the
    one genuine new external boundary this feature adds. No lock-related test
    (none exists, by explicit user decision - see contracts/reminder-delivery.md)."""

    def _bot_with_sending_result(self, code, data):
        bot = Mock()
        bot.api.sending.sendMessage.return_value = Mock(code=code, data=data)
        return bot

    def test_success_returns_id_message(self):
        bot = self._bot_with_sending_result(200, {"idMessage": "wamid.123"})
        result = send_proactive_message(bot, "972501234567@c.us", "hello")
        assert result == "wamid.123"
        bot.api.sending.sendMessage.assert_called_once_with("972501234567@c.us", "hello")

    def test_non_200_code_returns_none(self):
        bot = self._bot_with_sending_result(400, {"error": "bad request"})
        assert send_proactive_message(bot, "chat1", "hi") is None

    def test_non_dict_data_returns_none(self):
        # The library's raise_errors=False default means a failure comes back
        # as a Response with non-dict/garbage data rather than an exception -
        # same shape WhatsAppHandler._send_approval_buttons already guards for.
        bot = self._bot_with_sending_result(200, "not a dict")
        assert send_proactive_message(bot, "chat1", "hi") is None

    def test_missing_id_message_key_returns_none(self):
        bot = self._bot_with_sending_result(200, {"no_id_message_here": True})
        assert send_proactive_message(bot, "chat1", "hi") is None

    def test_none_response_returns_none(self):
        bot = Mock()
        bot.api.sending.sendMessage.return_value = None
        assert send_proactive_message(bot, "chat1", "hi") is None

    def test_exception_from_sending_call_returns_none_never_raises(self):
        bot = Mock()
        bot.api.sending.sendMessage.side_effect = ConnectionError("network down")
        result = send_proactive_message(bot, "chat1", "hi")
        assert result is None

    def test_never_constructs_a_second_bot_only_uses_the_passed_one(self):
        """Sanity check that this function is a pure pass-through to the given
        bot object - no internal GreenAPIBot()/GreenAPI() construction (the
        hard constraint denidin.py documents: constructing a second one drains
        pending notifications from the live instance, must only ever happen
        once)."""
        import inspect
        source = inspect.getsource(send_proactive_message)
        assert "GreenAPIBot(" not in source
        assert "GreenAPI(" not in source
