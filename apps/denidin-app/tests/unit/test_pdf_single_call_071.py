"""Feature 071 - a PDF is read in ONE model call as an `input_file`.

Only the OpenAI client is faked (third-party boundary); the extractor classes,
prompt building and JSON parsing are the real code."""
import json
from unittest.mock import Mock

import pytest

from src.constants.error_messages import FILE_TOO_LARGE_REFUSAL
from src.handlers.extractors import pdf_extractor as pdf_module
from src.handlers.extractors.image_extractor import ImageExtractor
from src.handlers.extractors.pdf_extractor import PDFExtractor
from src.models.media import Media
from tests.extractor_test_support import make_extractor_ai_manager


def _denidin():
    denidin = Mock()
    denidin.ai_manager = make_extractor_ai_manager()
    denidin.config = Mock()
    denidin.config.ai_vision_model = "gpt-4o"
    denidin.config.ai_reply_max_tokens = 1000
    return denidin


def _reply(doc_type="agreement", **extra):
    payload = {"doc_type": doc_type, "extracted_text": "טקסט מהמסמך", "fields": extra.get("fields", {}),
               "missing_required_fields": extra.get("missing", [])}
    response = Mock()
    response.output_text = json.dumps(payload, ensure_ascii=False)
    response.output = []
    return response


def _pdf(size=100):
    return Media.from_bytes(b"%PDF-" + b"x" * (size - 5), "application/pdf", "הסכם.pdf")


def test_pdf_extractor_is_an_image_extractor():
    assert issubclass(PDFExtractor, ImageExtractor)


def test_whole_pdf_goes_in_one_call_as_an_input_file():
    denidin = _denidin()
    denidin.ai_manager.client.responses.create.return_value = _reply()
    media = _pdf()

    PDFExtractor(denidin).analyze_media(media)

    create = denidin.ai_manager.client.responses.create
    assert create.call_count == 1
    content = create.call_args.kwargs["input"][0]["content"]
    file_parts = [c for c in content if c["type"] == "input_file"]
    assert len(file_parts) == 1
    assert file_parts[0]["filename"] == "הסכם.pdf"
    assert file_parts[0]["file_data"] == media.get_data_url()
    assert file_parts[0]["file_data"].startswith("data:application/pdf;base64,")
    assert not [c for c in content if c["type"] == "input_image"]
    assert create.call_args.kwargs["model"] == "gpt-4o"


def test_image_extraction_still_sends_an_input_image():
    denidin = _denidin()
    denidin.ai_manager.client.responses.create.return_value = _reply("unknown")

    ImageExtractor(denidin).analyze_media(Media.from_bytes(b"img", "image/jpeg", "a.jpg"))

    content = denidin.ai_manager.client.responses.create.call_args.kwargs["input"][0]["content"]
    assert [c["type"] for c in content] == ["input_text", "input_image"]
    assert content[1]["detail"] == "high"


def test_agreement_pdf_keeps_its_classification_and_fields():
    denidin = _denidin()
    fields = {"client_name": "לקוח", "components": [{"amount": 5000, "description": "ייעוץ", "vat_status": "כולל"}]}
    denidin.ai_manager.client.responses.create.return_value = _reply("agreement", fields=fields)

    result = PDFExtractor(denidin).analyze_media(_pdf())

    assert result["doc_type"] == "agreement"
    assert result["fields"] == fields
    assert result["extracted_text"] == "טקסט מהמסמך"


def test_a_pdf_is_never_a_deposit_even_if_the_model_says_so():
    denidin = _denidin()
    denidin.ai_manager.client.responses.create.return_value = _reply(
        "bank", fields={"payer_name": "x", "amount": 1})

    result = PDFExtractor(denidin).analyze_media(_pdf())

    assert result["doc_type"] == "unknown"
    assert result["fields"] == {}
    assert result["ledger_events"] == []


def test_the_refusal_message_is_friendly_hebrew_with_a_next_step():
    assert FILE_TOO_LARGE_REFUSAL.startswith("📄")
    assert "?" in FILE_TOO_LARGE_REFUSAL or "אפשר" in FILE_TOO_LARGE_REFUSAL


def test_a_pdf_agreement_is_stashed_as_a_document_not_an_image():
    from src.capabilities.media_analysis.handler import build_media_stash_text

    result = {"doc_type": "agreement", "extracted_text": "הסכם שכר טרחה",
              "fields": {"client_name": "לקוח", "components": [{"amount": 5000, "description": "ייעוץ", "vat_status": "כולל"}]}}

    pdf_text = build_media_stash_text(result, "pdf")
    image_text = build_media_stash_text(result, "image")

    assert pdf_text and pdf_text != image_text
