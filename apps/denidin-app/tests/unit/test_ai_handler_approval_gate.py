"""
Unit tests for Feature 022's `_is_affirmative_reply` helper (explicit
approval before Morning document creation). Pure function, no API calls -
covers the clarified Hebrew/English affirmative examples plus negatives.
"""
import pytest

from src.handlers.ai_handler import _is_affirmative_reply


@pytest.mark.parametrize("text", [
    "yes", "Yes", "YES", "yep", "yeah", "sure", "ok", "okay", "go ahead",
    "כן", "אישור", "בסדר", "אוקיי", "אוקי",
    "  כן  ",
    "כן.", "כן!", "אישור,",
    "כן, תודה",
    "ok, please proceed",
])
def test_recognized_affirmatives(text):
    assert _is_affirmative_reply(text) is True


@pytest.mark.parametrize("text", [
    "לא", "no", "wait", "רגע",
    "מה השעה עכשיו?",
    "",
    "   ",
    "לקוחה בשם זהבית - בדוק לי כמה שילמה ומתי",
    "אני לא בטוח",  # contains "לא" but is not itself an affirmative
])
def test_non_affirmatives(text):
    assert _is_affirmative_reply(text) is False
