"""
Unit tests for WhatsAppHandler.send_document_response() (Feature 083, Phase 4).

Same retry-logic testing pattern as test_whatsapp_handler_retry.py: only
`green_api_bot.api.sending.sendFileByUpload` (a real external Green API call)
is a stand-in - retry policy is real tenacity code exercised for real.
"""
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests

from src.handlers.whatsapp_handler import WhatsAppHandler
from src.models.fee_agreement import GeneratedDocument
from src.utils.time_utils import now_local


@pytest.fixture
def whatsapp_handler():
    return WhatsAppHandler()


@pytest.fixture
def mock_bot():
    bot = MagicMock()
    return bot


@pytest.fixture
def generated_document(tmp_path):
    temp_path = tmp_path / "doc123.docx"
    temp_path.write_bytes(b"fake docx bytes")
    return GeneratedDocument(
        document_id="doc123",
        variant_id="hourly_consultation",
        values={"CLIENT_NAME": "X"},
        temp_path=temp_path,
        created_at=now_local(),
        verified=True,
    )


class TestSendDocumentResponse:
    def test_sends_exactly_once_on_success(self, whatsapp_handler, mock_bot, generated_document):
        whatsapp_handler.green_api_bot = mock_bot

        result = whatsapp_handler.send_document_response(
            generated_document, chat_id="972500000000@c.us", caption="הנה ההסכם"
        )

        assert result is True
        mock_bot.api.sending.sendFileByUpload.assert_called_once_with(
            "972500000000@c.us", str(generated_document.temp_path),
            fileName=generated_document.temp_path.name, caption="הנה ההסכם",
        )

    def test_refuses_outright_when_not_verified(self, whatsapp_handler, mock_bot, generated_document):
        whatsapp_handler.green_api_bot = mock_bot
        generated_document.verified = False

        result = whatsapp_handler.send_document_response(
            generated_document, chat_id="972500000000@c.us", caption="x"
        )

        assert result is False
        mock_bot.api.sending.sendFileByUpload.assert_not_called()

    def test_returns_false_when_no_bot_injected(self, whatsapp_handler, generated_document):
        whatsapp_handler.green_api_bot = None

        result = whatsapp_handler.send_document_response(
            generated_document, chat_id="972500000000@c.us", caption="x"
        )

        assert result is False

    def test_retries_once_on_5xx_then_succeeds(self, whatsapp_handler, mock_bot, generated_document):
        whatsapp_handler.green_api_bot = mock_bot
        error_response = MagicMock()
        error_response.status_code = 500
        http_error = requests.HTTPError(response=error_response)
        mock_bot.api.sending.sendFileByUpload.side_effect = [http_error, None]

        result = whatsapp_handler.send_document_response(
            generated_document, chat_id="972500000000@c.us", caption="x"
        )

        assert result is True
        assert mock_bot.api.sending.sendFileByUpload.call_count == 2

    def test_never_retries_a_4xx_error(self, whatsapp_handler, mock_bot, generated_document):
        whatsapp_handler.green_api_bot = mock_bot
        error_response = MagicMock()
        error_response.status_code = 400
        http_error = requests.HTTPError(response=error_response)
        mock_bot.api.sending.sendFileByUpload.side_effect = http_error

        result = whatsapp_handler.send_document_response(
            generated_document, chat_id="972500000000@c.us", caption="x"
        )

        assert result is False
        assert mock_bot.api.sending.sendFileByUpload.call_count == 1

    def test_returns_false_after_retry_exhausted(self, whatsapp_handler, mock_bot, generated_document):
        whatsapp_handler.green_api_bot = mock_bot
        error_response = MagicMock()
        error_response.status_code = 500
        http_error = requests.HTTPError(response=error_response)
        mock_bot.api.sending.sendFileByUpload.side_effect = http_error

        result = whatsapp_handler.send_document_response(
            generated_document, chat_id="972500000000@c.us", caption="x"
        )

        assert result is False
        assert mock_bot.api.sending.sendFileByUpload.call_count == 2

    def test_never_raises_on_connection_error(self, whatsapp_handler, mock_bot, generated_document):
        whatsapp_handler.green_api_bot = mock_bot
        mock_bot.api.sending.sendFileByUpload.side_effect = requests.ConnectionError("boom")

        result = whatsapp_handler.send_document_response(
            generated_document, chat_id="972500000000@c.us", caption="x"
        )

        assert result is False

    def test_does_not_delete_the_temp_file_itself(self, whatsapp_handler, mock_bot, generated_document):
        # Deletion is FeeAgreementToolHandler._cleanup's job, not this
        # method's - send_document_response must leave the file alone
        # either way (success or failure).
        whatsapp_handler.green_api_bot = mock_bot

        whatsapp_handler.send_document_response(
            generated_document, chat_id="972500000000@c.us", caption="x"
        )

        assert generated_document.temp_path.exists()
