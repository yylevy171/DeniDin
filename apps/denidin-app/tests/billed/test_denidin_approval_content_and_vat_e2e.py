"""bugfix-028 (A2, B3, B4) billed E2E — what the user is asked to approve, and
what actually gets created.

Real webhook -> real OpenAI Responses API -> real Morning MCP server over its
real ngrok tunnel -> real Morning sandbox. Same entry point and helpers as this
directory's other Morning-MCP billed modules.

The unifying finding behind all of these (production review, 7-9 Aug 2026):
**DeniDin reports intent as outcome.** It told the user ₪2,360 for a document
Morning had stored at ₪2,784.80, and re-asked the same approval question eight
times without once saying the previous attempt had failed.

RED ON CURRENT CODE:
  - A2: `create_transaction_account` takes no VAT argument and its payload
    omits `vatType` entirely, which Morning treats as "price EXCLUDES vat"
    (live-probed 2026-08-09: 11 -> 12.98). The approval says one number and
    Morning stores another.
  - B3: the approval text is either the model's free narration or a string
    built from tool arguments alone; neither is guaranteed to state the
    document date, the VAT treatment, or (for a type 300) the purpose.
  - B4: Morning's client search is a word-aligned PREFIX match of the whole
    stored name, so the `(ח.פ …)` this app itself appends to a display label
    takes it from 1 match to 0.

Amounts stay under 100, per this suite's sandbox convention.
NO MOCKING anywhere. @pytest.mark.billed: real OpenAI billing on every run.
"""
import re

import pytest

from tests.billed.denidin_mcp_e2e_helpers import (  # noqa: F401
    GODFATHER_CHAT_ID,
    _calls_for,
    _is_genuine_document_creation,
    _seed_fresh_client,
    _send_turn,
    _send_turn_and_approve,
    require_live_morning_tunnel,
)

pytestmark = pytest.mark.billed

AMOUNT = 47


def _approval_text(ask_result):
    """The message the user is actually asked to approve."""
    reply, _ = ask_result
    assert reply, "the ASK turn produced no message at all - nothing to approve (B5)"
    return reply


# --------------------------------------------------------------------- A2
def test_vat_included_transaction_account_is_stored_at_the_approved_amount(denidin_app):
    """A2-T1: 'חשבון עסקה על סך 47 ₪ כולל מע״מ' must exist in Morning as 47.

    Production: ₪2,360 approved, ₪2,784.80 stored (document 90195), and the
    ₪424.80 difference surfaced only from the Morning UI two days later - never
    from our own logs or data.
    """
    client_name, _, _ = _seed_fresh_client(GODFATHER_CHAT_ID, id_prefix="B028_A2T1")

    _, (reply, ai_response) = _send_turn_and_approve(
        GODFATHER_CHAT_ID,
        f"תפיק חשבון עסקה ל{client_name} על סך {AMOUNT} ₪ כולל מע״מ, עבור ייעוץ משפטי",
        id_prefix="B028_A2T1",
    )

    calls = _calls_for(ai_response, "create_transaction_account")
    assert calls and calls[0]["error"] is None, f"document was not created: {ai_response.mcp_calls if ai_response else None!r}"

    assert "55.46" not in (reply or ""), (
        f"Morning inflated the approved 47 by 18% and the reply admits it: {reply!r}"
    )
    output = calls[0]["output"] or ""
    assert "55.46" not in output and "55" not in re.sub(r"[^\d.]", " ", output).split(), (
        f"the created document is not the {AMOUNT} that was approved: {output!r}"
    )
    assert str(AMOUNT) in output, f"the approved amount {AMOUNT} is absent from the result: {output!r}"


def test_unstated_vat_is_asked_about_rather_than_assumed(denidin_app):
    """A2-T2: VAT unstated must produce a QUESTION, not a document.

    A2 requirement 1 (user, 2026-08-09): VAT is mandatory at creation and
    "unknown" is not a permitted state - the model must be able to say
    definitively with-or-without before anything is created. The constitution
    already demands exactly this question for `close_transaction_account`
    (:253-256) and demands nothing for `create_transaction_account`.
    """
    client_name, _, _ = _seed_fresh_client(GODFATHER_CHAT_ID, id_prefix="B028_A2T2")

    reply, ai_response = _send_turn(
        GODFATHER_CHAT_ID,
        f"תפיק חשבון עסקה ל{client_name} על סך {AMOUNT} ₪, עבור ייעוץ משפטי",
        id_prefix="B028_A2T2",
    )

    assert not _calls_for(ai_response, "create_transaction_account"), (
        "a document-creation call was made with the VAT treatment undecided"
    )
    assert reply and "מע" in reply, (
        f"expected DeniDin to ask whether the amount includes VAT; it said: {reply!r}"
    )


# --------------------------------------------------------------------- B3
def test_the_approval_states_every_mandatory_element(denidin_app):
    """B3-T1: the six mandatory elements of any document-creation approval
    (user, 2026-08-09): document type, document date, client, amount, VAT
    treatment, purpose.

    Live counter-example (session 12e158e2, turns 16/18) - the user's own
    qualifiers vanished between what she wrote and what she was asked to
    approve:
        16 DENIDIN … על סך 40,000 ₪ לפני מע״מ, עבור צו מניעה תומר מרסיאנו …
        18 DENIDIN להפיק חשבון עסקה להסתדרות הכללית החדשה על סך 40000 ₪ — לאשר?
    """
    from datetime import datetime, timezone

    client_name, _, _ = _seed_fresh_client(GODFATHER_CHAT_ID, id_prefix="B028_B3T1")

    ask_result, _ = _send_turn_and_approve(
        GODFATHER_CHAT_ID,
        f"תפיק חשבון עסקה ל{client_name} על סך {AMOUNT} ₪ לפני מע״מ, עבור ייעוץ משפטי",
        id_prefix="B028_B3T1",
    )
    approval = _approval_text(ask_result)

    today = datetime.now(timezone.utc).date()
    missing = []
    if "חשבון עסקה" not in approval:
        missing.append("document type (חשבון עסקה)")
    if not any(form in approval for form in (
        today.strftime("%d/%m/%Y"), today.strftime("%d.%m.%Y"),
        today.strftime("%d/%m/%y"), today.isoformat(), "היום",
    )):
        missing.append("document date")
    if client_name.split()[0] not in approval:
        missing.append(f"client name ({client_name})")
    if str(AMOUNT) not in approval:
        missing.append(f"amount ({AMOUNT})")
    if "מע" not in approval:
        missing.append("VAT treatment (כולל/לא כולל מע״מ)")
    if "ייעוץ" not in approval:
        missing.append("purpose (ייעוץ משפטי)")

    assert not missing, (
        f"the approval request omits {missing} - the user cannot approve what "
        f"was never stated. Approval text was: {approval!r}"
    )


# --------------------------------------------------------------------- B4
# bugfix-028 B4-T1: pre-existing sandbox clients, used instead of seeding fresh
# ones (user decision, 2026-08-09: "dont need any more seeding - whats there we
# can treat as a one-time hack"). They are also the only usable ones: three share
# the leading words `הסתדרות כללית חדשה` so the name is genuinely ambiguous, and
# they carry REAL tax IDs - `_seed_client_via_conversation` never passes
# `tax_id`, and a client with no ח.פ cannot be qualified BY its ח.פ, which is
# this test's entire premise.
# _B4_CLIENT carries 589103852 - the real ח.פ from the production incident.
_B4_CLIENT = "הסתדרות כללית חדשה DENIDIN_028_PROBE_1786284958"


def test_a_client_qualified_by_its_tax_id_still_resolves(denidin_app):
    """B4-T1: two clients sharing their first name-word force the model to
    qualify which one it means - and the natural qualifier is the ח.פ it
    learned from the client listing. That composite is exactly what failed in
    production, eight times, on a ₪40,000 document that was never created.

    The stored name was clean (`הסתדרות כללית חדשה`); the model added the ח.פ
    itself. Morning's search is a word-aligned prefix match of the whole stored
    name (live-probed), so anything appended takes it from 1 match to 0.

    **The document type is a חשבון עסקה because that is what production
    actually failed on** - the ₪40,000 document for הסתדרות כללית חדשה that was
    approved eight times and created zero times. An earlier draft of this test
    asked for a חשבונית מס קבלה instead, which was simply a misreproduction of
    the incident: a 320 records money already received and now requires a
    payment date, so that draft dragged an unrelated date question into a test
    about client-name resolution.

    The request is otherwise deliberately what a user would actually type - it
    does NOT pre-supply the client's exact stored form or anything else the
    system should work out or ask about. Padding the request until it passes
    would be testing a scenario nobody has.
    """
    _send_turn(GODFATHER_CHAT_ID, "אילו לקוחות יש לי ששמם מתחיל בהסתדרות?",
               id_prefix="B028_B4T1_LIST")

    _, (reply, ai_response) = _send_turn_and_approve(
        GODFATHER_CHAT_ID,
        f"תפיק חשבון עסקה ל{_B4_CLIENT} על סך {AMOUNT} ₪ כולל מע״מ, עבור ייעוץ משפטי",
        id_prefix="B028_B4T1",
    )

    calls = _calls_for(ai_response, "create_transaction_account")
    assert calls, (
        f"no document-creation call executed at all - in production this exact "
        f"shape looped silently: {ai_response.mcp_calls if ai_response else None!r}"
    )
    # bugfix-039 (caught in a post-merge sweep 2026-08-12): error is None on its
    # own no longer implies success - a non-exact match (e.g. the model
    # decorating the name with the ח.פ it just learned, exactly what this test
    # is probing for) now refuses with a "did you mean" confirmation question,
    # which is ALSO error=None and does NOT contain "לא נמצא לקוח" either. Both
    # of this test's original checks would have silently passed on that
    # refusal. _is_genuine_document_creation checks the output's own shape
    # instead (format_invoice_confirmation always starts with "חשבונית #").
    assert _is_genuine_document_creation(calls[0]), f"creation failed or was refused: {calls[0]!r}"
    assert "לא נמצא לקוח" not in (calls[0]["output"] or ""), (
        f"the client this app itself listed was not resolvable when fed back to "
        f"the create tool: arguments={calls[0]['arguments']!r} output={calls[0]['output']!r}"
    )
    assert "כללית חדשה" in (calls[0]["output"] or reply or ""), (
        "the document must be attached to the client that was actually asked for"
    )
