"""Feature 080 (T018) — regression confirmation: WhatsAppHandler.send_response() still
delivers the final answer as exactly ONE outbound message, never split/chunked, regardless
of Feature 080. send_response() itself was never touched by Feature 080 (only ai_handler.py,
denidin.py, telemetry, and runtime_constitution.md were) - this test exists to make that a
checked fact rather than an inference from "the file wasn't edited."

Also confirms the two send channels stay genuinely separate: a simulated interim
send_progress_update (a direct notification.answer() call, exactly how
AIHandler._handle_send_progress_update's progress_callback fires - see ai_handler.py) does
NOT count against or interfere with send_response()'s own single call - proving the final
answer is still delivered whole, as its own message, even on a turn that already sent one or
more interim updates before it.
"""
from unittest.mock import MagicMock

from src.handlers.whatsapp_handler import WhatsAppHandler
from src.models.message import AIResponse


def _sample_response(text: str) -> AIResponse:
    return AIResponse(
        request_id="req_080_chunking",
        response_text=text,
        tokens_used=50,
        prompt_tokens=10,
        completion_tokens=40,
        model="gpt-4o-mini",
        finish_reason="stop",
        timestamp=1234567890,
        is_truncated=False,
    )


class TestNoResponseChunking080:
    def test_final_answer_is_one_notification_answer_call(self):
        """The baseline case: send_response() calls notification.answer() exactly once,
        with the complete response_text, not split into multiple sends."""
        handler = WhatsAppHandler()
        notification = MagicMock()
        notification.answer = MagicMock()
        long_text = "א" * 3500  # long, but under the 4000-char truncation threshold

        handler.send_response(notification, _sample_response(long_text))

        assert notification.answer.call_count == 1
        notification.answer.assert_called_once_with(long_text)

    def test_final_answer_still_one_call_after_a_simulated_interim_progress_update(self):
        """Feature 080: a turn that already sent an interim send_progress_update message
        (a direct notification.answer() call, out-of-band from send_response - see
        AIHandler._handle_send_progress_update's progress_callback) must still have its
        REAL final answer delivered as exactly one further, separate, complete message -
        never merged, chunked, or skipped because an interim message already went out."""
        handler = WhatsAppHandler()
        notification = MagicMock()
        notification.answer = MagicMock()

        # Simulates the interim send_progress_update call - happens BEFORE
        # send_response() is ever reached, via the same notification.answer channel.
        notification.answer("בודק את זה, רגע...")
        assert notification.answer.call_count == 1

        final_text = "התשובה הסופית המלאה לשאלה שלך."
        handler.send_response(notification, _sample_response(final_text))

        # Exactly one MORE call - the real final answer, delivered whole.
        assert notification.answer.call_count == 2
        notification.answer.assert_called_with(final_text)
