"""
Unit tests for PlayerExportSource (Feature 043, tasks.md T012a).

Written BEFORE implementation, per TDD workflow (METHODOLOGY.md SS VI).

See contracts/message-source.md: PlayerExportSource never blocks, never
touches Green API, iterates its message list once in order, calling
dispatch(type_message, notification) for each synthesizable message.
"""
from datetime import datetime, timezone
from pathlib import Path

from player.export_parser import ParsedMessage
from player.export_source import PlayerExportSource


def _text_msg(sender="Ayelet", text="hi", minute=0):
    return ParsedMessage(
        timestamp=datetime(2025, 9, 1, 7, 30 + minute, tzinfo=timezone.utc),
        sender_display_name=sender, text=text, attachments=[], raw_line_no=1,
    )


class TestPlayerExportSourceStart:
    def test_dispatches_once_per_message_in_order(self):
        messages = [_text_msg(text="first", minute=0), _text_msg(text="second", minute=1)]
        source = PlayerExportSource(
            messages, chat_id="972501234567@c.us", sender_map={"Ayelet": "972500000000@c.us"},
        )
        received = []

        source.start(lambda type_message, notification: received.append(
            (type_message, notification.event["messageData"]["textMessageData"]["textMessage"])
        ))

        assert received == [("textMessage", "first"), ("textMessage", "second")]

    def test_start_returns_without_blocking(self):
        """No assertion needed beyond reaching this line - start() must not
        loop forever or spawn a listener; it processes the fixed message
        list once and returns."""
        source = PlayerExportSource([], chat_id="c", sender_map={})
        source.start(lambda type_message, notification: None)

    def test_notification_object_supports_answer(self):
        messages = [_text_msg()]
        source = PlayerExportSource(messages, chat_id="c", sender_map={"Ayelet": "s"})
        captured = []

        def _dispatch(type_message, notification):
            notification.answer("some reply")  # must not raise
            captured.append(notification)

        source.start(_dispatch)

        assert captured[0].last_answer == "some reply"

    def test_unmapped_sender_is_skipped_not_dispatched(self):
        messages = [_text_msg(sender="Unknown Person")]
        source = PlayerExportSource(messages, chat_id="c", sender_map={"Ayelet": "s"})
        received = []

        source.start(lambda type_message, notification: received.append(notification))

        assert received == []
        assert source.outcomes[0]["status"] == "unmapped-sender"

    def test_unsupported_attachment_is_skipped_not_dispatched(self):
        msg = ParsedMessage(
            timestamp=datetime(2025, 9, 1, 7, 30, tzinfo=timezone.utc),
            sender_display_name="Ayelet", text="",
            attachments=[Path("/tmp/media/voice.opus")], raw_line_no=1,
        )
        source = PlayerExportSource(
            [msg], chat_id="c", sender_map={"Ayelet": "s"}, media_base_url="http://127.0.0.1:9"
        )
        received = []

        source.start(lambda type_message, notification: received.append(notification))

        assert received == []
        assert source.outcomes[0]["status"] == "unsupported-type"

    def test_dispatched_message_recorded_in_outcomes(self):
        messages = [_text_msg()]
        source = PlayerExportSource(messages, chat_id="c", sender_map={"Ayelet": "s"})

        source.start(lambda type_message, notification: None)

        assert source.outcomes[0]["status"] == "dispatched"
        assert source.outcomes[0]["type_message"] == "textMessage"
