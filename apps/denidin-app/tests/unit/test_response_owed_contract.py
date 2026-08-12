"""bugfix-028 B5 — the response-owed contract.

Root cause approved 2026-08-09: the constitution's "never leave the user with
no signal" rule is not enforced anywhere. A send that doesn't raise is logged
as "Response sent successfully ... 0 chars", so a zero-character message
counts as a reply; the one guard that exists sits inside the pending-approval
branch (`ai_handler.py:1333`) and `send_response` validates nothing.

Design decision at the same gate (user): KEEP Feature 039's `[[NO_REPLY]]`
sentinel and add a turn-level contract around it. "No reply" becomes an
explicitly declared outcome, so empty-by-intent and empty-by-failure stop
being indistinguishable. `should_reply` is that declaration - what is missing
is anything enforcing it.

Two-sided, because "always non-empty" would be wrong: a group message aimed
at someone else legitimately owes no reply (Feature 039, covered live by
tests/billed/test_group_etiquette_billed.py).

RED ON CURRENT CODE: an AIResponse that owes a reply but carries none is
constructed happily today, and send_response ships it.
"""
import time

import pytest

from src.models.message import AIResponse


def _response(text, should_reply=True):
    return AIResponse(
        request_id="bugfix-028-b5",
        response_text=text,
        tokens_used=0,
        prompt_tokens=0,
        completion_tokens=0,
        model="gpt-4o-mini",
        finish_reason="stop",
        timestamp=int(time.time()),
        should_reply=should_reply,
    )


@pytest.mark.parametrize("empty_text", ["", "   ", "\n", "\t\n  "])
def test_a_turn_that_owes_a_reply_cannot_carry_an_empty_one(empty_text):
    """B5 side 1: should_reply=True is a promise that a reply exists. An empty
    or whitespace-only body breaks it, and must be impossible to construct
    rather than something discovered when the user gets a blank WhatsApp
    message (sessions 047cacb7 turn 22, 12e158e2 turn 16).
    """
    with pytest.raises(ValueError):
        _response(empty_text, should_reply=True)


def test_a_turn_that_owes_no_reply_may_legitimately_be_empty():
    """B5 side 2: the opposite must stay possible. Feature 039's whole point is
    that some turns correctly send nothing - a group message clearly addressed
    to someone else. This is why "assert non-empty" is the wrong rule.
    """
    response = _response("", should_reply=False)
    assert response.should_reply is False
    assert response.response_text == ""


def test_a_no_reply_turn_may_carry_the_sentinel_it_was_built_from():
    """The other half of the contract - "no reply owed => nothing reaches the
    user" - is enforced at the SEND boundary, not on the object.

    Feature 039 keeps the model's own `[[NO_REPLY]]` text on the response, and
    the existing dispatch tests (tests/unit/test_denidin_no_reply_dispatch.py)
    build a populated no-reply response deliberately. Forbidding that here would
    have broken two approved tests to enforce something in the wrong place: what
    must never happen is the text being SENT, which is
    WhatsAppHandler.send_response's job.
    """
    response = _response("[[NO_REPLY]]", should_reply=False)
    assert response.should_reply is False


def test_a_normal_reply_is_unaffected():
    """Guard: the overwhelmingly common case must not become harder to build."""
    response = _response("הופקה חשבונית מספר 12345.")
    assert response.should_reply is True
    assert response.response_text
