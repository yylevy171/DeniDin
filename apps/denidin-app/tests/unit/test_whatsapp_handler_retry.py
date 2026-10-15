"""WhatsAppHandler.send_to_chat retry policy (CONSTITUTION retry rule): one retry after 1s on a timeout,
connection error or 5xx; never on a 4xx; it never raises - a send that could not be made returns None."""
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
import requests

from src.handlers.whatsapp_handler import WhatsAppHandler
from tests.denidin_test_support import make_denidin

CHAT = "972500000000@c.us"


def _ok(n=1):
    return SimpleNamespace(code=200, data={"idMessage": f"ID{n}"})


@pytest.fixture
def handler():
    app = make_denidin()
    app.green_api_bot = Mock()
    return WhatsAppHandler(app)


def _send_message(handler):
    return handler.green_api_bot.api.sending.sendMessage


def _http_error(status):
    response = Mock()
    response.status_code = status
    return requests.HTTPError(f"{status}", response=response)


@pytest.mark.parametrize("error", [requests.Timeout("t"), requests.ConnectionError("c"), _http_error(500)])
def test_a_retryable_failure_is_retried_once_and_the_send_succeeds(handler, error):
    _send_message(handler).side_effect = [error, _ok(2)]
    with patch("time.sleep"):
        sent = handler.send_to_chat(CHAT, "שלום")
    assert _send_message(handler).call_count == 2
    assert sent is not None and sent.whatsapp_id_message == "ID2"


def test_the_wait_between_the_attempts_is_one_second(handler):
    _send_message(handler).side_effect = [requests.Timeout("t"), _ok()]
    with patch("time.sleep") as sleep:
        handler.send_to_chat(CHAT, "שלום")
    sleep.assert_called_once_with(1)


def test_a_persistent_failure_stops_after_two_attempts_and_returns_none(handler):
    _send_message(handler).side_effect = requests.Timeout("down")
    with patch("time.sleep"):
        assert handler.send_to_chat(CHAT, "שלום") is None
    assert _send_message(handler).call_count == 2


@pytest.mark.parametrize("status", [400, 401, 429])
def test_a_4xx_is_never_retried(handler, status):
    _send_message(handler).side_effect = _http_error(status)
    assert handler.send_to_chat(CHAT, "שלום") is None
    assert _send_message(handler).call_count == 1


def test_a_non_200_answer_is_a_failed_send(handler):
    _send_message(handler).return_value = SimpleNamespace(code=466, data={})
    assert handler.send_to_chat(CHAT, "שלום") is None


def test_an_empty_message_is_refused_without_calling_green_api(handler):
    assert handler.send_to_chat(CHAT, "   ") is None
    _send_message(handler).assert_not_called()


def test_a_long_message_is_cut_before_it_is_sent(handler):
    _send_message(handler).return_value = _ok()
    handler.send_to_chat(CHAT, "א" * 4500)
    assert _send_message(handler).call_args.args[1] == "א" * 4000 + "..."


def test_without_a_live_bot_nothing_is_sent_and_nothing_raises():
    assert WhatsAppHandler(make_denidin()).send_to_chat(CHAT, "שלום") is None
