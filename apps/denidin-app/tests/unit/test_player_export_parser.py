"""
Unit tests for the WhatsApp export parser (Feature 043, tasks.md T009a).

Written BEFORE implementation, per TDD workflow (METHODOLOGY.md SS VI).

Format confirmed against a REAL sample export this session (research.md R1) -
these tests use hand-written SYNTHETIC fixtures mimicking that exact format
(fake names/amounts), never the real sample itself or any real client data,
per the user's explicit instruction (spec.md's Clarifications).
"""
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from player.export_parser import ParsedMessage, filter_date_range, filter_from_line, parse_export


def _make_export_zip(tmp_path, chat_text: str, media_files=None) -> Path:
    """Builds a real zip (chat .txt + optional media files) matching the real
    WhatsApp export shape confirmed in research.md R1."""
    zip_path = tmp_path / "export.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("WhatsApp Chat with Test Chat.txt", chat_text)
        for filename, content in (media_files or {}).items():
            zf.writestr(filename, content)
    return zip_path


class TestBasicMessageParsing:
    def test_single_text_message_parsed(self, tmp_path):
        chat_text = "9/1/25, 10:30 - Ayelet: Hello there\n"
        zip_path = _make_export_zip(tmp_path, chat_text)

        messages = parse_export(zip_path, tmp_path / "extracted")

        assert len(messages) == 1
        assert messages[0].sender_display_name == "Ayelet"
        assert messages[0].text == "Hello there"
        assert messages[0].attachments == []

    def test_timestamp_converted_from_israel_local_to_utc(self, tmp_path):
        # 9/1/25, 10:30 Asia/Jerusalem (UTC+3 in September, DST) -> 07:30 UTC.
        chat_text = "9/1/25, 10:30 - Ayelet: Hello there\n"
        zip_path = _make_export_zip(tmp_path, chat_text)

        messages = parse_export(zip_path, tmp_path / "extracted")

        assert messages[0].timestamp == datetime(2025, 9, 1, 7, 30, tzinfo=timezone.utc)

    def test_multiple_messages_parsed_in_order(self, tmp_path):
        chat_text = (
            "9/1/25, 10:30 - Ayelet: First message\n"
            "9/1/25, 10:31 - Ayelet: Second message\n"
            "9/2/25, 09:00 - Danny: Third message\n"
        )
        zip_path = _make_export_zip(tmp_path, chat_text)

        messages = parse_export(zip_path, tmp_path / "extracted")

        assert [m.text for m in messages] == ["First message", "Second message", "Third message"]
        assert messages[2].sender_display_name == "Danny"

    def test_multiline_continuation_joined(self, tmp_path):
        chat_text = (
            "9/1/25, 10:30 - Ayelet: David Cohen\n"
            "Office matter\n"
            "5,000 NIS\n"
            "9/1/25, 10:31 - Ayelet: Next message\n"
        )
        zip_path = _make_export_zip(tmp_path, chat_text)

        messages = parse_export(zip_path, tmp_path / "extracted")

        assert len(messages) == 2
        assert messages[0].text == "David Cohen\nOffice matter\n5,000 NIS"
        assert messages[1].text == "Next message"

    def test_sender_name_with_emoji_preserved(self, tmp_path):
        chat_text = "9/1/25, 10:30 - Ayelet \U0001F98B: Hello\n"
        zip_path = _make_export_zip(tmp_path, chat_text)

        messages = parse_export(zip_path, tmp_path / "extracted")

        assert messages[0].sender_display_name == "Ayelet \U0001F98B"

    def test_bidi_control_characters_stripped_from_text(self, tmp_path):
        # U+200F (RLM) commonly prefixes message bodies in real exports.
        chat_text = "9/1/25, 10:30 - Ayelet: ‏David Cohen\n"
        zip_path = _make_export_zip(tmp_path, chat_text)

        messages = parse_export(zip_path, tmp_path / "extracted")

        assert messages[0].text == "David Cohen"
        assert "‏" not in messages[0].text


class TestAttachmentParsing:
    def test_attachment_line_detected_and_resolved(self, tmp_path):
        chat_text = "9/1/25, 14:00 - Ayelet: IMG-20250901-WA0001.jpg (file attached)\n"
        zip_path = _make_export_zip(
            tmp_path, chat_text, media_files={"IMG-20250901-WA0001.jpg": b"fake jpeg bytes"}
        )

        messages = parse_export(zip_path, tmp_path / "extracted")

        assert len(messages) == 1
        assert len(messages[0].attachments) == 1
        assert messages[0].attachments[0].name == "IMG-20250901-WA0001.jpg"
        assert messages[0].attachments[0].exists()
        assert messages[0].attachments[0].read_bytes() == b"fake jpeg bytes"

    def test_attachment_with_no_caption_has_empty_text(self, tmp_path):
        chat_text = "9/1/25, 14:00 - Ayelet: IMG-20250901-WA0001.jpg (file attached)\n"
        zip_path = _make_export_zip(
            tmp_path, chat_text, media_files={"IMG-20250901-WA0001.jpg": b"data"}
        )

        messages = parse_export(zip_path, tmp_path / "extracted")

        assert messages[0].text == ""

    def test_attachment_with_caption_on_continuation_line(self, tmp_path):
        chat_text = (
            "9/1/25, 14:00 - Ayelet: IMG-20250901-WA0001.jpg (file attached)\n"
            "This is the signed agreement\n"
        )
        zip_path = _make_export_zip(
            tmp_path, chat_text, media_files={"IMG-20250901-WA0001.jpg": b"data"}
        )

        messages = parse_export(zip_path, tmp_path / "extracted")

        assert len(messages) == 1
        assert messages[0].attachments[0].name == "IMG-20250901-WA0001.jpg"
        assert messages[0].text == "This is the signed agreement"

    def test_multiple_image_burst_kept_as_separate_messages(self, tmp_path):
        """A run of consecutive attachment-only messages (same timestamp) must
        NOT be merged into one - Green API delivers each as its own webhook."""
        chat_text = (
            "9/1/25, 14:41 - Ayelet: IMG-0001.jpg (file attached)\n"
            "9/1/25, 14:41 - Ayelet: IMG-0002.jpg (file attached)\n"
            "9/1/25, 14:41 - Ayelet: IMG-0003.jpg (file attached)\n"
        )
        zip_path = _make_export_zip(
            tmp_path, chat_text,
            media_files={"IMG-0001.jpg": b"1", "IMG-0002.jpg": b"2", "IMG-0003.jpg": b"3"},
        )

        messages = parse_export(zip_path, tmp_path / "extracted")

        assert len(messages) == 3
        assert [m.attachments[0].name for m in messages] == ["IMG-0001.jpg", "IMG-0002.jpg", "IMG-0003.jpg"]

    def test_referenced_file_missing_from_zip_does_not_crash(self, tmp_path):
        chat_text = "9/1/25, 14:00 - Ayelet: IMG-nonexistent.jpg (file attached)\n"
        zip_path = _make_export_zip(tmp_path, chat_text, media_files={})

        messages = parse_export(zip_path, tmp_path / "extracted")

        assert len(messages) == 1
        assert messages[0].attachments[0].name == "IMG-nonexistent.jpg"
        assert not messages[0].attachments[0].exists()


class TestSystemMessageFiltering:
    def test_encryption_notice_filtered_out(self, tmp_path):
        chat_text = (
            "9/1/25, 10:00 - Messages and calls are end-to-end encrypted. "
            "No one outside of this chat, not even WhatsApp, can read or listen to them.\n"
            "9/1/25, 10:30 - Ayelet: Real message\n"
        )
        zip_path = _make_export_zip(tmp_path, chat_text)

        messages = parse_export(zip_path, tmp_path / "extracted")

        assert len(messages) == 1
        assert messages[0].text == "Real message"

    def test_system_notice_mid_conversation_does_not_corrupt_prior_message(self, tmp_path):
        """Regression test: a system notice (no "Name:" colon structure) has
        a date prefix just like a real message, so a naive parser could
        mistake it for a continuation line of whatever real message came
        right before it, silently polluting that message's text (e.g. a fee
        agreement's raw_message_excerpt gaining bogus system text)."""
        chat_text = (
            "9/1/25, 10:30 - Ayelet: 5,000 NIS agreement\n"
            "9/1/25, 10:31 - Messages and calls are end-to-end encrypted. Tap to learn more.\n"
            "9/1/25, 10:32 - Ayelet: Next real message\n"
        )
        zip_path = _make_export_zip(tmp_path, chat_text)

        messages = parse_export(zip_path, tmp_path / "extracted")

        assert len(messages) == 2
        assert messages[0].text == "5,000 NIS agreement"
        assert "encrypted" not in messages[0].text
        assert messages[1].text == "Next real message"


class TestZipStructureErrors:
    def test_no_txt_file_raises(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("photo.jpg", b"data")

        with pytest.raises(ValueError):
            parse_export(zip_path, tmp_path / "extracted")

    def test_multiple_txt_files_raises(self, tmp_path):
        zip_path = tmp_path / "export.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("a.txt", "9/1/25, 10:30 - Ayelet: Hi\n")
            zf.writestr("b.txt", "9/1/25, 10:30 - Ayelet: Hi\n")

        with pytest.raises(ValueError):
            parse_export(zip_path, tmp_path / "extracted")


class TestFilterDateRange:
    def _msg(self, y, m, d):
        return ParsedMessage(
            timestamp=datetime(y, m, d, 12, 0, tzinfo=timezone.utc),
            sender_display_name="Ayelet", text="x", attachments=[], raw_line_no=1,
        )

    def test_filters_to_inclusive_range(self):
        messages = [self._msg(2025, 9, 1), self._msg(2025, 9, 15), self._msg(2025, 10, 1)]

        result = filter_date_range(
            messages, start=date(2025, 9, 1), end=date(2025, 9, 30), today=date(2026, 8, 7)
        )

        assert len(result) == 2
        assert result[0].timestamp.day == 1
        assert result[1].timestamp.day == 15

    def test_start_never_earlier_than_sep_1_2025(self):
        messages = [self._msg(2025, 8, 15), self._msg(2025, 9, 5)]

        result = filter_date_range(
            messages, start=date(2025, 1, 1), end=date(2025, 12, 31), today=date(2026, 8, 7)
        )

        assert len(result) == 1
        assert result[0].timestamp.month == 9

    def test_end_never_later_than_today(self):
        messages = [self._msg(2026, 8, 5), self._msg(2026, 8, 10)]

        result = filter_date_range(
            messages, start=date(2025, 9, 1), end=date(2026, 12, 31), today=date(2026, 8, 7)
        )

        assert len(result) == 1
        assert result[0].timestamp.day == 5

    def test_default_range_is_sep_1_to_today(self):
        messages = [self._msg(2025, 8, 31), self._msg(2025, 9, 1), self._msg(2026, 8, 7)]

        result = filter_date_range(messages, start=None, end=None, today=date(2026, 8, 7))

        assert len(result) == 2


class TestFilterFromLine:
    def _msg(self, raw_line_no):
        return ParsedMessage(
            timestamp=datetime(2026, 8, 9, 12, 0, tzinfo=timezone.utc),
            sender_display_name="Ayelet", text="x", attachments=[], raw_line_no=raw_line_no,
        )

    def test_keeps_only_messages_at_or_after_the_line(self):
        messages = [self._msg(100), self._msg(2535), self._msg(2582)]

        result = filter_from_line(messages, start_at_line=2535)

        assert [m.raw_line_no for m in result] == [2535, 2582]

    def test_none_returns_messages_unchanged(self):
        messages = [self._msg(100), self._msg(2535)]

        result = filter_from_line(messages, start_at_line=None)

        assert result == messages

    def test_line_past_every_message_returns_empty(self):
        messages = [self._msg(100), self._msg(200)]

        result = filter_from_line(messages, start_at_line=9999)

        assert result == []
