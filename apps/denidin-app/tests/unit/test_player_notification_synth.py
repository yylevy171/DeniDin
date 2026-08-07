"""
Unit tests for the notification synthesizer (Feature 043, tasks.md T010a).

Written BEFORE implementation, per TDD workflow (METHODOLOGY.md SS VI).

Confirms a synthesized notification's `event` dict round-trips correctly
through the REAL WhatsAppMessage.from_notification (src/models/message.py) -
the actual contract that matters, not a re-derivation of its parsing logic.
See contracts/message-source.md.
"""
from datetime import datetime, timezone
from pathlib import Path

from scripts.player.export_parser import ParsedMessage
from scripts.player.notification_synth import synthesize_notification
from src.models.message import WhatsAppMessage


def _text_message(text="Hello there", sender="Ayelet"):
    return ParsedMessage(
        timestamp=datetime(2025, 9, 1, 7, 30, tzinfo=timezone.utc),
        sender_display_name=sender, text=text, attachments=[], raw_line_no=1,
    )


class TestTextMessageSynthesis:
    def test_produces_text_message_type(self):
        result = synthesize_notification(
            _text_message(), chat_id="972501234567@c.us", sender_id="972501234567@c.us",
            idmessage_seq=1,
        )
        assert result is not None
        event, type_message = result
        assert type_message == "textMessage"
        assert event["messageData"]["typeMessage"] == "textMessage"

    def test_round_trips_through_real_whatsapp_message_parsing(self):
        event, _type_message = synthesize_notification(
            _text_message(text="David Cohen, 5000 NIS"),
            chat_id="972501234567@c.us", sender_id="972501234567@c.us", idmessage_seq=1,
        )

        class _FakeNotification:
            pass

        notification = _FakeNotification()
        notification.event = event
        parsed = WhatsAppMessage.from_notification(notification)

        assert parsed.text_content == "David Cohen, 5000 NIS"
        assert parsed.chat_id == "972501234567@c.us"
        assert parsed.sender_id == "972501234567@c.us"
        assert parsed.message_type == "textMessage"

    def test_real_historical_timestamp_preserved(self):
        event, _ = synthesize_notification(
            _text_message(), chat_id="c", sender_id="s", idmessage_seq=1,
        )

        assert event["timestamp"] == int(datetime(2025, 9, 1, 7, 30, tzinfo=timezone.utc).timestamp())

    def test_sender_display_name_becomes_sender_name(self):
        event, _ = synthesize_notification(
            _text_message(sender="Ayelet \U0001F98B"), chat_id="c", sender_id="s", idmessage_seq=1,
        )

        assert event["senderData"]["senderName"] == "Ayelet \U0001F98B"

    def test_idmessage_is_unique_per_sequence_number(self):
        event1, _ = synthesize_notification(_text_message(), chat_id="c", sender_id="s", idmessage_seq=1)
        event2, _ = synthesize_notification(_text_message(), chat_id="c", sender_id="s", idmessage_seq=2)

        assert event1["idMessage"] != event2["idMessage"]


class TestImageMessageSynthesis:
    def _image_message(self, filename="IMG-0001.jpg", caption=""):
        return ParsedMessage(
            timestamp=datetime(2025, 9, 1, 7, 30, tzinfo=timezone.utc),
            sender_display_name="Ayelet", text=caption,
            attachments=[Path(f"/tmp/fake_media/{filename}")], raw_line_no=1,
        )

    def test_produces_image_message_type_for_jpg(self):
        result = synthesize_notification(
            self._image_message(), chat_id="c", sender_id="s", idmessage_seq=1,
            media_base_url="http://127.0.0.1:8000",
        )
        assert result is not None
        event, type_message = result
        assert type_message == "imageMessage"
        assert event["messageData"]["typeMessage"] == "imageMessage"

    def test_download_url_built_from_media_base_url_and_filename(self):
        event, _ = synthesize_notification(
            self._image_message(filename="IMG-0001.jpg"), chat_id="c", sender_id="s",
            idmessage_seq=1, media_base_url="http://127.0.0.1:8000",
        )

        assert event["messageData"]["fileMessageData"]["downloadUrl"] == "http://127.0.0.1:8000/IMG-0001.jpg"
        assert event["messageData"]["fileMessageData"]["fileName"] == "IMG-0001.jpg"

    def test_caption_threaded_into_file_message_data(self):
        event, _ = synthesize_notification(
            self._image_message(caption="Signed agreement"), chat_id="c", sender_id="s",
            idmessage_seq=1, media_base_url="http://127.0.0.1:8000",
        )

        assert event["messageData"]["fileMessageData"]["caption"] == "Signed agreement"

    def test_mime_type_inferred_from_extension(self):
        event, _ = synthesize_notification(
            self._image_message(filename="photo.png"), chat_id="c", sender_id="s",
            idmessage_seq=1, media_base_url="http://127.0.0.1:8000",
        )

        assert event["messageData"]["fileMessageData"]["mimeType"] == "image/png"

    def test_round_trips_through_real_whatsapp_message_parsing(self):
        event, _ = synthesize_notification(
            self._image_message(), chat_id="972501234567@c.us", sender_id="972501234567@c.us",
            idmessage_seq=1, media_base_url="http://127.0.0.1:8000",
        )

        class _FakeNotification:
            pass

        notification = _FakeNotification()
        notification.event = event
        parsed = WhatsAppMessage.from_notification(notification)

        assert parsed.message_type == "imageMessage"
        assert parsed.chat_id == "972501234567@c.us"


class TestDocumentMessageSynthesis:
    def _pdf_message(self, filename="agreement.pdf"):
        return ParsedMessage(
            timestamp=datetime(2025, 9, 1, 7, 30, tzinfo=timezone.utc),
            sender_display_name="Ayelet", text="",
            attachments=[Path(f"/tmp/fake_media/{filename}")], raw_line_no=1,
        )

    def test_pdf_produces_document_message_type(self):
        result = synthesize_notification(
            self._pdf_message(), chat_id="c", sender_id="s", idmessage_seq=1,
            media_base_url="http://127.0.0.1:8000",
        )
        assert result is not None
        event, type_message = result
        assert type_message == "documentMessage"

    def test_docx_produces_document_message_type(self):
        result = synthesize_notification(
            self._pdf_message(filename="agreement.docx"), chat_id="c", sender_id="s",
            idmessage_seq=1, media_base_url="http://127.0.0.1:8000",
        )
        assert result is not None
        _event, type_message = result
        assert type_message == "documentMessage"


class TestUnsupportedAttachmentTypes:
    def test_voice_note_returns_none(self):
        msg = ParsedMessage(
            timestamp=datetime(2025, 9, 1, 7, 30, tzinfo=timezone.utc),
            sender_display_name="Ayelet", text="",
            attachments=[Path("/tmp/fake_media/voice.opus")], raw_line_no=1,
        )

        result = synthesize_notification(
            msg, chat_id="c", sender_id="s", idmessage_seq=1, media_base_url="http://127.0.0.1:8000",
        )

        assert result is None

    def test_video_returns_none(self):
        msg = ParsedMessage(
            timestamp=datetime(2025, 9, 1, 7, 30, tzinfo=timezone.utc),
            sender_display_name="Ayelet", text="",
            attachments=[Path("/tmp/fake_media/clip.mp4")], raw_line_no=1,
        )

        result = synthesize_notification(
            msg, chat_id="c", sender_id="s", idmessage_seq=1, media_base_url="http://127.0.0.1:8000",
        )

        assert result is None
