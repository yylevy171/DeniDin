"""Feature 064 - structural guard on the deposit flow's 320 offer.

The behaviour itself is model-driven and proven by the approved `expensive`
acceptance scenarios; this unit test only pins the written contract in the
flow prompt (the offer step exists, is image-only, is a separate final
approval-buttons message after a separate report, never uses the reserved
write-approval string, and lets the user win)."""
from pathlib import Path

CONFIG = Path(__file__).resolve().parents[2] / "config" / "prompts"
FLOW = (CONFIG / "flows" / "flow_deposit_provided_by_user.md").read_text(encoding="utf-8")
APPROVAL_CAP = (CONFIG / "capabilities" / "cap_approval_with_buttons.md").read_text(encoding="utf-8")


def _offer_step() -> str:
    start = FLOW.index("4. 🚨 **The document")
    return FLOW[start:FLOW.index("5. The user's next message")]


def test_offer_step_exists_and_is_scoped_to_images_with_a_resolved_client():
    step = _offer_step()
    assert "came as an **image**" in step
    assert "not a PDF or DOCX" in step
    assert "client is resolved" in step


def test_offer_is_the_last_message_and_nothing_follows_it():
    step = _offer_step()
    assert "send nothing more and wait" in step
    assert "approval_with_yes_no_buttons" in step


def test_offer_carries_no_details():
    step = _offer_step()
    assert "carries no amounts, names or dates" in step


def test_user_instruction_wins_over_the_offer():
    assert "the user's explicit instruction always wins" in FLOW
    assert "make no offer" in FLOW


def test_reply_handling_covers_yes_no_and_anything_else():
    reply = FLOW[FLOW.index("5. The user's next message"):FLOW.index("6. End.")]
    assert "A yes" in reply and "A no" in reply and "Anything else" in reply
    assert "do not ask again" in reply


def test_flow_loads_the_approval_capability_and_unloads_it_at_the_end():
    assert "`cap_approval_with_buttons`" in FLOW.split("Follow these steps")[0]
    assert "unload `cap_media_analysis`, `cap_client_read`, `cap_approval_with_buttons`" in FLOW


def test_approval_capability_is_a_plain_yes_no_on_whatever_was_asked():
    assert "about a write, an offer" in APPROVAL_CAP
    assert "not a write approval" not in APPROVAL_CAP


def test_the_client_step_does_not_stop_before_the_offer():
    """64-1: after resolving the client the model must go on to the ledger recording and the offer. There is
    no 'end of turn' any more; the report goes out with cap_send_to_user and the flow continues."""
    assert "end_turn" not in FLOW
    assert "cap_send_progress_update" not in FLOW
    assert "Load `cap_approval_with_buttons` now" in _offer_step()


def test_the_slips_date_always_wins_and_is_never_asked_about():
    """64-1 (2026-10-12): a caption saying "today" over a slip dated earlier made the model
    ask which date to use and record nothing."""
    assert "ALWAYS the date on the slip" in FLOW
    assert "Never ask the user which date to use" in FLOW
    ledger = (CONFIG / "capabilities" / "cap_ledger_capture.md").read_text(encoding="utf-8")
    assert "the slip's date is ALWAYS `txn_date`" in ledger
