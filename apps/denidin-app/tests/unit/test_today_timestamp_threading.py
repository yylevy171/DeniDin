"""
Unit tests for the today_timestamp threading chain (Feature 043, tasks.md T007a).

Written BEFORE implementation, per TDD workflow (METHODOLOGY.md SS VI).

research.md R4 found the image-path ledger-classification call
(AIHandler.capture_ledger_events_from_text) has NO way to override wall-clock
"today" at all - test_ai_handler_instructions.py (T006) already covers
_build_instructions itself; this file covers the 4-hop threading a real replay
needs: MediaHandler.process_media_message's existing `timestamp` argument ->
_extract_text -> the extractor's analyze_media -> (image/PDF path only)
AIHandler.capture_ledger_events_from_text. Omitted/None at any hop must
preserve current behavior exactly (matches T006's "None preserves wall-clock"
guarantee at the bottom of the chain).
"""
from unittest.mock import Mock

import pytest

from src.handlers.extractors.image_extractor import ImageExtractor
from src.handlers.extractors.pdf_extractor import PDFExtractor
from src.handlers.media_handler import MediaHandler
from src.models.media import Media


class TestCaptureLedgerEventsFromTextThreadsReferenceTimestamp:
    def test_passes_today_timestamp_into_build_instructions(self, tmp_path):
        from unittest.mock import MagicMock
        from src.handlers.ai_handler import AIHandler
        from src.models.config import AppConfiguration

        config = AppConfiguration(
            green_api_instance_id="test", green_api_token="test", ai_api_key="test-key",
            ai_model="gpt-4o-mini", ai_reply_max_tokens=1000, log_level="INFO",
            data_root=str(tmp_path),
            constitution_config={"file": "runtime_constitution.md", "base_dir": str(tmp_path)},
        )
        (tmp_path / "runtime_constitution.md").write_text("# Constitution", encoding="utf-8")
        client = MagicMock()
        mock_response = Mock()
        mock_response.output = []
        mock_response.id = "resp_1"
        client.responses.create.return_value = mock_response
        handler = AIHandler(client, config)

        handler.capture_ledger_events_from_text("some extracted text", today_timestamp=1706600034)

        sent_kwargs = client.responses.create.call_args.kwargs
        assert "2024-01-30" in sent_kwargs["instructions"]

    def test_omitted_today_timestamp_still_works(self, tmp_path):
        """No TypeError, no behavior change, when the caller doesn't pass it."""
        from unittest.mock import MagicMock
        from src.handlers.ai_handler import AIHandler
        from src.models.config import AppConfiguration

        config = AppConfiguration(
            green_api_instance_id="test", green_api_token="test", ai_api_key="test-key",
            ai_model="gpt-4o-mini", ai_reply_max_tokens=1000, log_level="INFO",
            data_root=str(tmp_path),
            constitution_config={"file": "runtime_constitution.md", "base_dir": str(tmp_path)},
        )
        (tmp_path / "runtime_constitution.md").write_text("# Constitution", encoding="utf-8")
        client = MagicMock()
        mock_response = Mock()
        mock_response.output = []
        mock_response.id = "resp_1"
        client.responses.create.return_value = mock_response
        handler = AIHandler(client, config)

        result = handler.capture_ledger_events_from_text("some extracted text")

        assert result == []


class TestImageExtractorThreadsReferenceTimestamp:
    @pytest.fixture
    def mock_denidin(self):
        denidin = Mock()
        denidin.ai_handler = Mock()
        denidin.ai_handler._load_constitution.return_value = ""
        denidin.ai_handler.capture_ledger_events_from_text.return_value = []
        denidin.config = Mock()
        denidin.config.ai_vision_model = "gpt-4o"
        denidin.config.ai_reply_max_tokens = 1000
        return denidin

    @pytest.fixture
    def test_media(self):
        return Media.from_bytes(b"fake image data", "image/jpeg", "test.jpg")

    def test_today_timestamp_passed_through_to_capture_ledger_events(self, mock_denidin, test_media):
        mock_response = Mock()
        mock_response.output_text = "TEXT:\nsome text\nCONFIDENCE: high\nNOTES: none"
        mock_response.output = []
        mock_denidin.ai_handler.client.responses.create.return_value = mock_response
        extractor = ImageExtractor(mock_denidin)

        extractor.analyze_media(test_media, today_timestamp=1706600034)

        mock_denidin.ai_handler.capture_ledger_events_from_text.assert_called_once_with(
            mock_response.output_text, today_timestamp=1706600034
        )

    def test_omitted_today_timestamp_defaults_to_none(self, mock_denidin, test_media):
        mock_response = Mock()
        mock_response.output_text = "TEXT:\nsome text\nCONFIDENCE: high\nNOTES: none"
        mock_response.output = []
        mock_denidin.ai_handler.client.responses.create.return_value = mock_response
        extractor = ImageExtractor(mock_denidin)

        extractor.analyze_media(test_media)

        mock_denidin.ai_handler.capture_ledger_events_from_text.assert_called_once_with(
            mock_response.output_text, today_timestamp=None
        )


class TestPDFExtractorThreadsReferenceTimestamp:
    @pytest.fixture
    def mock_denidin(self):
        denidin = Mock()
        denidin.ai_handler = Mock()
        denidin.ai_handler._load_constitution.return_value = ""
        denidin.ai_handler.capture_ledger_events_from_text.return_value = []
        denidin.config = Mock()
        denidin.config.ai_vision_model = "gpt-4o"
        denidin.config.ai_model = "gpt-4o-mini"
        denidin.config.ai_reply_max_tokens = 1000
        return denidin

    def test_today_timestamp_passed_through_to_image_extractor(self, mock_denidin):
        pdf_extractor = PDFExtractor(mock_denidin)
        pdf_extractor.image_extractor = Mock()
        pdf_extractor.image_extractor.analyze_media.return_value = {
            "raw_response": "page text", "extraction_quality": "high",
            "warnings": [], "model_used": "gpt-4o", "ledger_events": [],
        }
        # A minimal real PDF (single blank page) so PyMuPDF can open it.
        import fitz
        doc = fitz.open()
        doc.new_page()
        pdf_bytes = doc.tobytes()
        doc.close()
        media = Media.from_bytes(pdf_bytes, "application/pdf", "test.pdf")

        pdf_extractor.analyze_media(media, today_timestamp=1706600034)

        _args, kwargs = pdf_extractor.image_extractor.analyze_media.call_args
        assert kwargs.get("today_timestamp") == 1706600034


class TestMediaHandlerThreadsTimestampAsReferenceTimestamp:
    def test_timestamp_argument_threads_into_extractor_as_today_timestamp(self):
        mock_denidin = Mock()
        mock_denidin.config.data_root = "/tmp/test_data"

        handler = MediaHandler(mock_denidin)
        handler.image_extractor = Mock()
        handler.image_extractor.analyze_media = Mock(return_value={
            "raw_response": "some analysis", "extraction_quality": "high",
            "warnings": [], "model_used": "gpt-4o",
        })
        handler.media_file_manager = Mock()
        handler.media_file_manager.download_file = Mock(return_value=(b"data", True))
        handler.media_file_manager.validate_file_size = Mock(return_value=None)
        handler.media_file_manager.validate_format = Mock(return_value="image")
        handler.media_file_manager.create_storage_path = Mock(return_value="/tmp/test_data/media")
        handler.media_file_manager.save_file = Mock(return_value="/tmp/test_data/media/f.jpg")
        handler.media_file_manager.save_rawtext = Mock(return_value="/tmp/test_data/media/f.jpg.rawtext")

        handler.process_media_message(
            file_url="https://example.com/image.jpg", filename="doc.jpg", mime_type="image/jpeg",
            file_size=100, sender_phone="972501234567", chat_id="972501234567@c.us",
            timestamp=1706600034,
        )

        _args, kwargs = handler.image_extractor.analyze_media.call_args
        assert kwargs.get("today_timestamp") == 1706600034

    def test_omitted_timestamp_passes_none_through(self):
        mock_denidin = Mock()
        mock_denidin.config.data_root = "/tmp/test_data"

        handler = MediaHandler(mock_denidin)
        handler.image_extractor = Mock()
        handler.image_extractor.analyze_media = Mock(return_value={
            "raw_response": "some analysis", "extraction_quality": "high",
            "warnings": [], "model_used": "gpt-4o",
        })
        handler.media_file_manager = Mock()
        handler.media_file_manager.download_file = Mock(return_value=(b"data", True))
        handler.media_file_manager.validate_file_size = Mock(return_value=None)
        handler.media_file_manager.validate_format = Mock(return_value="image")
        handler.media_file_manager.create_storage_path = Mock(return_value="/tmp/test_data/media")
        handler.media_file_manager.save_file = Mock(return_value="/tmp/test_data/media/f.jpg")
        handler.media_file_manager.save_rawtext = Mock(return_value="/tmp/test_data/media/f.jpg.rawtext")

        handler.process_media_message(
            file_url="https://example.com/image.jpg", filename="doc.jpg", mime_type="image/jpeg",
            file_size=100, sender_phone="972501234567", chat_id="972501234567@c.us",
        )

        _args, kwargs = handler.image_extractor.analyze_media.call_args
        assert kwargs.get("today_timestamp") is None
