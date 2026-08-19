"""
E2E Tests (Feature 030): Godfather shares a WhatsApp contact card (vCard) and DeniDin
proposes adding that person as a Morning client - real webhook, real OpenAI Responses API,
real Morning MCP server, real Morning sandbox.

Flow (entry point is the real Green API webhook, dispatched through the actual
@bot.router.message-decorated `handle_contact_message` - CONSTITUTION SS V):

    Green API contactMessage webhook (godfather sender)
      -> handle_contact_message (real router handler, not a direct internal call)
      -> WhatsAppMessage.from_notification (vCard framed into text_content)
      -> AIHandler.get_response
           -> client.responses.create (real OpenAI Responses API call)
              with the real Morning MCP server registered as a remote tool
      -> bot replies in Hebrew

This feature introduces NO new confirmation/approval mechanism: `add_client` is already in
AIHandler.APPROVAL_REQUIRED_MCP_TOOLS (Feature 026) - a shared vCard just becomes a new
*source* of the same conversational add_client flow typed text already triggers. Tests here
are genuinely two-turn (ASK then APPROVE), exactly like Feature 026's own add_client tests -
see `_send_turn_and_approve` (imported from denidin_mcp_e2e_helpers).

**Test tier (Feature 029)**: real, text-only OpenAI calls (a vCard is plain text - no vision/
image call involved) -> `billed`, NOT `expensive`. Runs freely, no per-run approval needed, no
one-at-a-time restriction - see CLAUDE.md.

**Assumes the test environment is already up**: apps/morning-mcp-app must already be running
(./run_morning_mcp.sh) - see test_denidin_morning_invoice_creation_e2e.py's module docstring
for the full prerequisite list; `denidin_app`/`live_morning_tunnel` (this directory's
conftest.py fixtures, used below via parameter names) fail loudly, not silently, if it isn't.

(2026-08-04, Feature 038: this import previously pointed at
test_denidin_morning_mcp_e2e.py, which was split by topic into 4 files -
see that feature's task list, T012/T013. Updated to import from the new
shared locations instead of any one of the resulting files.)

NO MOCKING anywhere.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

import pytest

from src.models.message import AIResponse
from tests.billed.denidin_mcp_e2e_helpers import (  # noqa: F401
    GODFATHER_CHAT_ID,
    _calls_for,
    _client_name_exact_match_found,
    create_real_notification,
    get_response,
)

# `denidin_app`/`denidin_config`/`live_morning_tunnel` are no longer imported
# explicitly - they're pytest fixtures auto-discovered from this directory's
# conftest.py (Feature 038 split, T012/T013).

logger = logging.getLogger(__name__)

_CONTACTS_FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "contacts"


def _build_contact_webhook(chat_id: str, sender_name: str, display_name: str, vcard: str, message_id: str) -> dict:
    """Build a real Green API incomingMessageReceived webhook event dict for a contactMessage,
    per contracts/contactMessage.json's confirmed shape (Green API official docs)."""
    return {
        'typeWebhook': 'incomingMessageReceived',
        'timestamp': int(time.time()),
        'idMessage': message_id,
        'instanceData': {
            'idInstance': 7103000000,
            'wid': '972501234567@c.us',
            'typeInstance': 'whatsapp'
        },
        'senderData': {
            'chatId': chat_id,
            'sender': chat_id,
            'senderName': sender_name
        },
        'messageData': {
            'typeMessage': 'contactMessage',
            'contactMessageData': {
                'displayName': display_name,
                'vcard': vcard,
                'forwardingScore': 0,
                'isForwarded': False,
            }
        }
    }


def _send_contact_turn(
    chat_id: str, display_name: str, vcard: str, id_prefix: str
) -> Tuple[Optional[str], Optional[AIResponse]]:
    """Send one real contact-card WhatsApp turn through the real router handler
    (handle_contact_message) and return (reply text, AIResponse with mcp_calls)."""
    from denidin import handle_contact_message

    notification = create_real_notification(_build_contact_webhook(
        chat_id=chat_id,
        sender_name="E2E Godfather",
        display_name=display_name,
        vcard=vcard,
        message_id=f"{id_prefix}_{int(datetime.now(timezone.utc).timestamp())}"
    ))
    handle_contact_message(notification)
    response = get_response(notification)

    import denidin
    ai_response = denidin.denidin_app.ai_handler.last_response

    if ai_response is not None:
        for call in ai_response.mcp_calls:
            logger.info(
                f"mcp_call: name={call['name']} error={call['error']!r} "
                f"arguments={call['arguments']!r} output={call['output']!r}"
            )
    logger.info(f"Bot response: {response}")

    return response, ai_response


def _send_text_turn(chat_id: str, text: str, id_prefix: str) -> Tuple[Optional[str], Optional[AIResponse]]:
    """Send a plain typed-text follow-up turn (e.g. supplying a missing email, or an
    affirmative approval) through the normal text router."""
    from denidin import handle_text_message
    from tests.billed.denidin_mcp_e2e_helpers import build_text_webhook

    notification = create_real_notification(build_text_webhook(
        chat_id=chat_id,
        sender_name="E2E Godfather",
        text=text,
        message_id=f"{id_prefix}_{int(datetime.now(timezone.utc).timestamp())}"
    ))
    handle_text_message(notification)
    response = get_response(notification)

    import denidin
    ai_response = denidin.denidin_app.ai_handler.last_response
    return response, ai_response


def _load_vcard(filename: str) -> str:
    return (_CONTACTS_FIXTURES_DIR / filename).read_text(encoding="utf-8")


def _ledger_event_count_for_chat(denidin_app, chat_id: str) -> int:
    """Counts real persisted LedgerEvent files (data/events/*.json, Feature 033) for this
    chat_id - used as a before/after false-positive guard: a shared vCard's raw text goes
    through the exact same conversational AIHandler pipeline (and the same always-attached
    LEDGER_EVENT_TOOL) as any text message, so nothing structurally prevents the model from
    misreading contact-card fields as fee-agreement/bank-deposit content. Same
    before/after-count pattern as test_ledger_event_capture_e2e.py's ordinary-chatter guard.

    2026-08-20 (billed/expensive test sweep for Feature 043's Phase 11 schema
    revision): was filtering by `data.get("whatsapp_chat") == chat_id`, but
    whatsapp_chat was removed from the persisted schema (2026-08-19, redundant
    with session_id) - the condition was silently always False, so this guard's
    before/after counts were always 0 == 0, a vacuous pass that could never have
    caught a real false positive. Fixed to resolve session_id via SessionManager
    and filter by that instead, matching the same fix already applied to every
    other ledger-event helper in this schema revision."""
    session_id = denidin_app.ai_handler.session_manager.get_session(chat_id).session_id
    storage_dir = denidin_app.ai_handler.ledger_event_manager.storage_dir
    count = 0
    for f in storage_dir.glob("*.json"):
        with open(f, encoding="utf-8") as fh:
            data = json.load(fh)
        if data.get("session_id") == session_id:
            count += 1
    return count


@pytest.mark.billed
def test_godfather_shares_contact_card_complete_requires_approval(denidin_app):
    """US1: a shared contact card with name+phone+email all present is resolved via the
    exact same resolve_client_name-first flow (client-name-resolution architecture,
    2026-08-12) a typed add_client request would use.

    "Dana Cohen" (the complete_card_dana_cohen.vcf fixture's name) is a PERMANENT
    ground-truth sandbox fixture (created 2026-07-30, real client id
    2c4f7b86-07c1-44c6-b119-f8f0249958e1 - see GROUND_TRUTH_CLIENTS.md) - the first time
    this test ever ran successfully it created a real "Dana Cohen" client, and every run
    since is therefore a genuine EXACT-match duplicate, not a fresh creation (found live,
    2026-08-12, when this test started failing post the "offer to update instead" removal
    - see runtime_constitution.md's "Do NOT offer... update" note). Adapted (2026-08-12,
    user decision) to assert that real behavior directly instead of assuming a fresh
    create every time: resolve_client_name reports the genuine exact match, add_client is
    correctly never called (no duplicate, and no silent update either), and the
    ledger-event false-positive guard still holds. No APPROVE turn - there is nothing
    pending to approve when the client already exists.
    """
    vcard = _load_vcard("complete_card_dana_cohen.vcf")
    ledger_count_before = _ledger_event_count_for_chat(denidin_app, GODFATHER_CHAT_ID)

    ask_response, ask_ai_response = _send_contact_turn(
        chat_id=GODFATHER_CHAT_ID,
        display_name="Dana Cohen",
        vcard=vcard,
        id_prefix="E2E_VCF_COMPLETE_ASK",
    )

    assert ask_response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert not _calls_for(ask_ai_response, "add_client"), (
        f"add_client executed for a client that already exists (real, permanent "
        f"'Dana Cohen' fixture) - should have refused plainly, never silently "
        f"duplicated or updated: {ask_ai_response.mcp_calls if ask_ai_response else None!r}"
    )
    assert _client_name_exact_match_found(ask_ai_response), (
        f"Expected resolve_client_name to report a genuine EXACT match for the "
        f"permanent 'Dana Cohen' fixture: {ask_ai_response.mcp_calls if ask_ai_response else None!r}"
    )
    assert _ledger_event_count_for_chat(denidin_app, GODFATHER_CHAT_ID) == ledger_count_before, (
        "capture_ledger_event was called on a raw vCard - contact-card fields "
        "(name/phone/email) must never be misread as fee-agreement/bank-deposit content"
    )


@pytest.mark.billed
def test_godfather_shares_contact_card_missing_email_is_asked_for(denidin_app):
    """US2: the real fixture (00005372-גיל ברטל .vcf) has no EMAIL field at all - the common
    case for real WhatsApp contact shares (per its own README). The bot must ask for the
    missing email before any add_client call or pending-approval state - inherits Feature
    026's REQ-CLIENT-012 "ask for what's missing" behavior unchanged.

    Once the email is supplied in a follow-up turn, the flow proceeds exactly as US1
    (confirmation -> approve -> creation) - UNLESS "גיל ברטל" is (as of 2026-08-12) a
    PERMANENT ground-truth sandbox fixture, same situation as "Dana Cohen" in the test
    above (created 2026-07-30, same original seeding session, real Morning `client_id`
    04d1c153-6d9c-467f-9eb1-a9661b4df4b6 - see GROUND_TRUTH_CLIENTS.md). Every run after
    the first successful one is therefore a genuine exact-match duplicate. Unlike "Dana
    Cohen", the model does not always refuse pre-emptively here - found live, 2026-08-12:
    it called add_client anyway, and Morning's own API rejected the duplicate directly
    (a real `mcp_tool_execution_error`, "❌ הבקשה נדחתה על ידי Morning"). Both outcomes
    (a clean pre-emptive refusal, or an attempted call Morning itself rejects) are
    accepted as correct below - what matters is that no duplicate client resulted, not
    which of the two ways that got enforced. Only accepted as a "pass" when a genuine
    EXACT match was actually seen in this flow - any OTHER add_client failure reason
    still fails the test normally.
    """
    vcard = _load_vcard("00005372-גיל ברטל .vcf")
    assert "EMAIL" not in vcard  # sanity: this fixture genuinely has no email
    ledger_count_before = _ledger_event_count_for_chat(denidin_app, GODFATHER_CHAT_ID)

    ask_response, ask_ai_response = _send_contact_turn(
        chat_id=GODFATHER_CHAT_ID,
        display_name="גיל ברטל",
        vcard=vcard,
        id_prefix="E2E_VCF_NOEMAIL_ASK",
    )

    assert ask_response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert not _calls_for(ask_ai_response, "add_client"), (
        f"add_client executed despite a missing email on the shared contact card: "
        f"{ask_ai_response.mcp_calls if ask_ai_response else None!r}"
    )
    # "דוא"ל" (the formal Hebrew abbreviation for "דואר אלקטרוני") is an equally
    # correct answer the model gave for real (2026-08-02) that "מייל"/"אימייל"
    # alone didn't catch - "דוא" as a substring covers "דוא״ל"/"דואל"/"דוא'ל"
    # regardless of which quote-character renders the geresh.
    assert "מייל" in ask_response or "אימייל" in ask_response or "דוא" in ask_response, (
        f"Expected the bot to ask for the missing email, got: {ask_response!r}"
    )
    assert _ledger_event_count_for_chat(denidin_app, GODFATHER_CHAT_ID) == ledger_count_before, (
        "capture_ledger_event was called on a raw vCard - contact-card fields "
        "(name/phone/email) must never be misread as fee-agreement/bank-deposit content"
    )

    supply_response, supply_ai_response = _send_text_turn(
        chat_id=GODFATHER_CHAT_ID,
        text="gil.bartal.qs@example.com",
        id_prefix="E2E_VCF_NOEMAIL_SUPPLY",
    )
    assert not _calls_for(supply_ai_response, "add_client"), (
        f"add_client executed immediately after supplying the email, without a confirmation "
        f"turn: {supply_ai_response.mcp_calls if supply_ai_response else None!r}"
    )

    approve_response, approve_ai_response = _send_text_turn(
        chat_id=GODFATHER_CHAT_ID,
        text="כן",
        id_prefix="E2E_VCF_NOEMAIL_APPROVE",
    )
    add_calls = _calls_for(approve_ai_response, "add_client")
    add_succeeded = bool(add_calls) and all(c["error"] is None for c in add_calls)

    # "גיל ברטל" is a permanent fixture (see docstring) - a failure here is only
    # acceptable when it's genuinely caused by that real exact-match duplicate,
    # never for any other reason. Check every turn's resolve_client_name calls,
    # not just the approve turn's - the exact match may have surfaced earlier.
    exact_match_found = any(
        _client_name_exact_match_found(r) for r in (ask_ai_response, supply_ai_response, approve_ai_response)
    )
    add_failed_as_known_duplicate = bool(add_calls) and not add_succeeded and exact_match_found

    assert add_succeeded or add_failed_as_known_duplicate, (
        f"add_client neither succeeded nor failed as the expected duplicate of the "
        f"permanent 'גיל ברטל' fixture: add_calls={add_calls!r}, "
        f"exact_match_found={exact_match_found!r}"
    )
