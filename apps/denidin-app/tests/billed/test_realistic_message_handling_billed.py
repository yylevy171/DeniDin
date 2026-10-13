"""Feature 067 acceptance scenarios A1-A7 (user-stories.md). `billed`: real OpenAI, text only.

AUTHORED, NOT YET RUN. Billed tests were deliberately not executed while writing this feature. Each
scenario asserts on the final state and the last answer, never on an exact number of intermediate
messages. Morning-backed ones (A3, A4) use the real Morning sandbox through the live tunnel, via the
shared `denidin_app` fixture in conftest.py (fails fast if the tunnel is down).
"""
import pytest

from tests.billed._067_harness import intake_rig
from tests.billed.denidin_mcp_e2e_helpers import ADMIN_ISOLATED_CHAT_ID, GODFATHER_CHAT_ID

pytestmark = pytest.mark.billed


def _normalized(text: str) -> str:
    return (text or "").replace("₪", "").replace(",", "")


@pytest.mark.sanity
def test_a0_count_with_me_three_quick_messages_get_the_next_number(denidin_app):
    """A0 - the simplest burst: the owner starts counting and sends 1, 2, 3 at once; DeniDin answers 4."""
    with intake_rig(denidin_app, ADMIN_ISOLATED_CHAT_ID) as rig:
        for text in ("בוא נספור ביחד עד 5, אני מתחיל: 1", "2", "3"):
            rig.send_text(text)
        rig.wait_until_idle()
        reply = rig.last_reply()
        assert "4" in reply, reply
        assert len(rig.stored_user_messages()) >= 3


def test_a1_quick_additive_burst_gives_one_coherent_answer(denidin_app):
    with intake_rig(denidin_app, ADMIN_ISOLATED_CHAT_ID) as rig:
        for text in ("תפיק לי חשבונית", "ללקוח דנה", "על 500 שקל"):
            rig.send_text(text)
        rig.wait_until_idle()
        reply = rig.last_reply()
        assert "דנה" in reply and "500" in _normalized(reply), reply
        assert rig.stored_user_messages()[-3:] == ["תפיק לי חשבונית", "ללקוח דנה", "על 500 שקל"]


def test_a2_long_burst_loses_nothing(denidin_app):
    facts = ["אני רוצה להפיק חשבונית", "ללקוח דנה כהן", "על סך 1200 שקל", "עבור ייעוץ", "כולל מע״מ",
             "לתאריך היום", "שלח במייל", "שמור עותק", "בדוק שהפרטים נכונים", "ובסוף תבקש ממני אישור"]
    with intake_rig(denidin_app, ADMIN_ISOLATED_CHAT_ID) as rig:
        for fact in facts:
            rig.send_text(fact)
        rig.wait_until_idle()
        assert rig.stored_user_messages()[-10:] == facts
        reply = _normalized(rig.last_reply())
        assert "1200" in reply and "ייעוץ" in reply, reply


def test_a3_stop_right_after_a_request_creates_nothing(denidin_app):
    with intake_rig(denidin_app, GODFATHER_CHAT_ID) as rig:
        rig.send_text("תפיק קבלה ללקוח דנה על 300 שקל")
        rig.send_text("עצור, אל תעשה את זה")
        rig.wait_until_idle()
        assert not rig.approval_message_id() or "אישור" not in rig.last_reply()
        before = len(rig.sent_texts())
        rig.send_text("כן")
        rig.wait_until_idle()
        reply = rig.last_reply()
        assert "הופקה" not in reply and "נוצרה" not in reply, reply
        assert len(rig.sent_texts()) > before


def test_a4_message_during_an_approved_action_creates_exactly_one_document(denidin_app):
    with intake_rig(denidin_app, GODFATHER_CHAT_ID) as rig:
        rig.send_text("תפיק חשבונית ללקוח דנה על 400 שקל כולל מע״מ עבור ייעוץ")
        rig.wait_until_idle()
        rig.send_text("כן")
        rig.send_text("רגע, תבטל")
        rig.wait_until_idle()
        created = [c for c in (denidin_app.last_response.mcp_calls or []) if c["name"].startswith("create_")]
        text = "\n".join(rig.sent_texts())
        assert text.count("הופקה") <= 2 and len(created) <= 1, text
        # the final answer deals with the cancel request and never claims a second document
        assert "תבטל" in text or "ביטול" in text or "לבטל" in text


def test_a5_confusing_sequence_settles_on_dana_or_asks(denidin_app):
    with intake_rig(denidin_app, ADMIN_ISOLATED_CHAT_ID) as rig:
        for text in ("תשלח לדנה", "לא, ליוסי", "בעצם דנה"):
            rig.send_text(text)
        rig.wait_until_idle()
        reply = rig.last_reply()
        assert "?" in reply or ("דנה" in reply and "יוסי" not in reply), reply


def test_a6_group_second_member_detail_is_accounted_for(denidin_app):
    group = "120363000000000067@g.us"
    with intake_rig(denidin_app, group, sender=GODFATHER_CHAT_ID, sender_name="Avi") as rig:
        rig.send_text("תפיק חשבונית ללקוח דנה")
        rig.send_text("על 700 שקל", sender=ADMIN_ISOLATED_CHAT_ID, sender_name="Bina")
        rig.wait_until_idle()
        assert "700" in _normalized(rig.last_reply())
        assert len(rig.stored_user_messages()) >= 2


def test_a7_button_survives_unrelated_chatter_and_works_once(denidin_app):
    from src.managers.pending_approval_manager import BUTTON_ID_DECLINE
    with intake_rig(denidin_app, GODFATHER_CHAT_ID) as rig:
        rig.send_text("תוסיף תזכורת מחר בתשע להתקשר לדנה")
        rig.wait_until_idle()
        button_id = rig.approval_message_id()
        assert button_id, "an approval prompt with buttons was expected"
        rig.send_text("מה השעה עכשיו?")
        rig.send_text("תודה")
        rig.wait_until_idle()
        rig.send_tap(BUTTON_ID_DECLINE, button_id)
        rig.wait_until_idle()
        replies_after_first_tap = len(rig.sent_texts())
        assert replies_after_first_tap > 0
        rig.send_tap(BUTTON_ID_DECLINE, button_id)
        rig.wait_until_idle()
        assert len(rig.sent_texts()) == replies_after_first_tap  # the second tap does nothing
