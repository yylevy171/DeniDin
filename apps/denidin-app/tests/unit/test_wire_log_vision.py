"""Unit tests (2026-10-01): the 'vision' wire-log boundary - the media extractors'
vision-model call, logged apart from the conversational model, with the image's
inline data URL never written to the log."""
import logging

from src.utils.wire_log import audit_wire, debug_wire

DATA_URL = "data:image/jpeg;base64," + "A" * 5000
REQUEST = {
    "model": "vision-model",
    "input": [{"role": "user", "content": [
        {"type": "input_text", "text": "חלץ את הטקסט"},
        {"type": "input_image", "image_url": DATA_URL, "detail": "high"},
    ]}],
}


def _logged(caplog, fn):
    caplog.set_level(logging.DEBUG)
    fn("vision", "out", "ImageExtractor._vision_extract", REQUEST)
    return "\n".join(r.getMessage() for r in caplog.records)


def test_audit_logs_vision_request_with_boundary_and_prompt_but_not_the_image(caplog):
    text = _logged(caplog, audit_wire)
    assert "boundary='vision' direction='out'" in text
    assert "חלץ את הטקסט" in text
    assert "AAAA" not in text
    assert f"<redacted data URL, {len(DATA_URL)} chars>" in text


def test_debug_logs_vision_request_without_the_image(caplog):
    text = _logged(caplog, debug_wire)
    assert "[WIRE-DEBUG] boundary='vision' direction='out'" in text
    assert "AAAA" not in text


def test_redaction_leaves_the_callers_request_untouched(caplog):
    _logged(caplog, audit_wire)
    _logged(caplog, debug_wire)
    assert REQUEST["input"][0]["content"][1]["image_url"] == DATA_URL
