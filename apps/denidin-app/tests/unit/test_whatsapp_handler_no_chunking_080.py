"""Feature 080 (T018), updated for the no-turn redesign: every send_to_chat is exactly ONE outbound
message - never split or chunked - and several sends in a row (interim updates, then the answer) are
each their own complete message."""
from types import SimpleNamespace
from unittest.mock import Mock

from src.handlers.whatsapp_handler import WhatsAppHandler
from tests.denidin_test_support import make_denidin

CHAT = "972500000000@c.us"


def _handler():
    app = make_denidin()
    app.green_api_bot = Mock()
    app.green_api_bot.api.sending.sendMessage.return_value = SimpleNamespace(code=200, data={"idMessage": "X"})
    return WhatsAppHandler(app), app.green_api_bot.api.sending.sendMessage


class TestNoResponseChunking080:
    def test_a_message_is_one_send_call_with_the_complete_text(self):
        handler, send = _handler()
        long_text = "א" * 3500  # long, but under the 4000-char cut

        handler.send_to_chat(CHAT, long_text)

        send.assert_called_once_with(CHAT, long_text)

    def test_an_answer_after_an_interim_update_is_its_own_whole_message(self):
        handler, send = _handler()
        handler.send_to_chat(CHAT, "בודק את זה, רגע...")
        final_text = "התשובה הסופית המלאה לשאלה שלך."

        handler.send_to_chat(CHAT, final_text)

        assert send.call_count == 2
        send.assert_called_with(CHAT, final_text)
