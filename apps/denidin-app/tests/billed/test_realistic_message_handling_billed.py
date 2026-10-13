"""Feature 067 acceptance scenarios A0-A7 (user-stories.md). `billed`: real OpenAI, text only.

A person types one message at a time, so every scenario sends its messages about a second apart:
the FIRST message must reach the model on its own (processing starts at once), and the later ones
reach it afterwards - at a hand-back together with a tool result, or as their own request. Each test
asserts on what the model's calls actually carried (read from the app's own wire log, nothing mocked)
and on the last reply. Morning-backed scenarios (A3, A4) use the real Morning sandbox through the
live tunnel (the shared `denidin_app` fixture fails fast if it is down).
"""
import pytest

from tests.billed._067_harness import WireCapture, intake_rig
from tests.billed.denidin_mcp_e2e_helpers import ADMIN_ISOLATED_CHAT_ID, GODFATHER_CHAT_ID

pytestmark = pytest.mark.billed


def _normalized(text: str) -> str:
    return (text or "").replace("₪", "").replace(",", "")


def send_spaced(rig, texts, **who):
    """Send the messages one at a time, a second apart (the last one is not followed by a wait)."""
    for index, text in enumerate(texts):
        rig.send_text(text, **who)
        if index < len(texts) - 1:
            rig.pause(1.0)


def assert_first_call_carried_only(rig, first_text, later_texts):
    """The first message reached the model by itself: nothing that was typed later is in the first call."""
    calls = rig.wire.conversation_calls()
    assert calls, "the model was never called"
    seen = WireCapture.user_texts(calls[0])
    assert seen and seen[-1] == first_text, seen
    for later in later_texts:
        assert later not in seen, f"{later!r} reached the model in the FIRST call: {seen}"


def assert_every_later_message_reached_the_model(rig, later_texts):
    """Each later message reaches the model, in a call after the first (a hand-back or its own request)."""
    after_first = rig.wire.conversation_calls()[1:]
    for later in later_texts:
        assert any(later in WireCapture.user_texts(call) for call in after_first), f"{later!r} never reached the model"


@pytest.mark.sanity
def test_a0_count_together_messages_sent_a_second_apart(denidin_app):
    """A0: "let's count to 4, I'll start: 1"; a second later "2"; a second later "3". The model starts on
    the first message alone, gets the others afterwards, and the last answer is 4."""
    first, later = "בוא נספור ביחד עד 4, אני מתחיל: 1", ["2", "3"]
    with intake_rig(denidin_app, ADMIN_ISOLATED_CHAT_ID) as rig:
        send_spaced(rig, [first] + later)
        rig.wait_until_idle()
        assert_first_call_carried_only(rig, first, later)
        assert_every_later_message_reached_the_model(rig, later)
        assert "4" in rig.last_reply(), rig.last_reply()
        assert rig.stored_user_messages() == [first] + later


def test_a1_additive_messages_give_one_coherent_answer(denidin_app):
    texts = ["תפיק לי חשבונית", "ללקוח דנה", "על 500 שקל"]
    with intake_rig(denidin_app, ADMIN_ISOLATED_CHAT_ID) as rig:
        send_spaced(rig, texts)
        rig.wait_until_idle()
        assert_first_call_carried_only(rig, texts[0], texts[1:])
        assert_every_later_message_reached_the_model(rig, texts[1:])
        reply = rig.last_reply()
        assert "דנה" in reply and "500" in _normalized(reply), reply
        assert rig.stored_user_messages() == texts


def test_a2_ten_messages_lose_nothing(denidin_app):
    facts = ["אני רוצה להפיק חשבונית", "ללקוח דנה כהן", "על סך 1200 שקל", "עבור ייעוץ", "כולל מע״מ",
             "לתאריך היום", "שלח במייל", "שמור עותק", "בדוק שהפרטים נכונים", "ובסוף תבקש ממני אישור"]
    with intake_rig(denidin_app, ADMIN_ISOLATED_CHAT_ID) as rig:
        send_spaced(rig, facts)
        rig.wait_until_idle()
        assert_first_call_carried_only(rig, facts[0], facts[1:])
        assert_every_later_message_reached_the_model(rig, facts[1:])
        assert rig.stored_user_messages() == facts
        reply = _normalized(rig.last_reply())
        assert "1200" in reply and "ייעוץ" in reply, reply


def test_a3_stop_after_a_request_creates_nothing(denidin_app):
    with intake_rig(denidin_app, GODFATHER_CHAT_ID) as rig:
        send_spaced(rig, ["תפיק קבלה ללקוח דנה על 300 שקל", "עצור, אל תעשה את זה"])
        rig.wait_until_idle()
        before = len(rig.sent_texts())
        send_spaced(rig, ["כן"])
        rig.wait_until_idle()
        reply = rig.last_reply()
        assert "הופקה" not in reply and "נוצרה" not in reply, reply
        assert len(rig.sent_texts()) > before


def test_a4_message_during_an_approved_action_creates_exactly_one_document(denidin_app):
    with intake_rig(denidin_app, GODFATHER_CHAT_ID) as rig:
        send_spaced(rig, ["תפיק חשבונית ללקוח דנה על 400 שקל כולל מע״מ עבור ייעוץ"])
        rig.wait_until_idle()
        send_spaced(rig, ["כן", "רגע, תבטל"])
        rig.wait_until_idle()
        created = [c for c in (denidin_app.last_response.mcp_calls or []) if c["name"].startswith("create_")]
        text = "\n".join(rig.sent_texts())
        assert len(created) <= 1, text
        assert "תבטל" in text or "ביטול" in text or "לבטל" in text


def test_a5_confusing_sequence_settles_on_dana_or_asks(denidin_app):
    with intake_rig(denidin_app, ADMIN_ISOLATED_CHAT_ID) as rig:
        send_spaced(rig, ["תשלח לדנה", "לא, ליוסי", "בעצם דנה"])
        rig.wait_until_idle()
        reply = rig.last_reply()
        assert "?" in reply or ("דנה" in reply and "יוסי" not in reply), reply


def test_a6_group_second_member_detail_is_accounted_for(denidin_app):
    group = "120363000000000067@g.us"
    with intake_rig(denidin_app, group, sender=GODFATHER_CHAT_ID, sender_name="Avi") as rig:
        rig.send_text("תפיק חשבונית ללקוח דנה")
        rig.pause(1.0)
        rig.send_text("על 700 שקל", sender=ADMIN_ISOLATED_CHAT_ID, sender_name="Bina")
        rig.wait_until_idle()
        assert "700" in _normalized(rig.last_reply())
        assert len(rig.stored_user_messages()) >= 2


def test_a7_button_survives_unrelated_chatter_and_works_once(denidin_app):
    from src.managers.pending_approval_manager import BUTTON_ID_DECLINE
    with intake_rig(denidin_app, GODFATHER_CHAT_ID) as rig:
        send_spaced(rig, ["תוסיף תזכורת מחר בתשע להתקשר לדנה"])
        rig.wait_until_idle()
        button_id = rig.approval_message_id()
        assert button_id, "an approval prompt with buttons was expected"
        send_spaced(rig, ["מה השעה עכשיו?", "תודה"])
        rig.wait_until_idle()
        rig.send_tap(BUTTON_ID_DECLINE, button_id)
        rig.wait_until_idle()
        replies_after_first_tap = len(rig.sent_texts())
        assert replies_after_first_tap > 0
        rig.send_tap(BUTTON_ID_DECLINE, button_id)
        rig.wait_until_idle()
        assert len(rig.sent_texts()) == replies_after_first_tap  # the second tap does nothing
