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
*source* of the same conversational add_client flow typed text already triggers.

**Client-seeding goes through the ONE shared helper** (2026-09-02, Feature 059): the vCard's
fields are parsed up front (`_parse_vcard`) and handed to `_seed_client`, exactly like a typed
add-client request. `_seed_client` owns the full 4-way resolve_client_name mapping (EXACT ->
already exists; SINGLE/MULTI -> a clarifying question answered with "create the new one I
asked for"; NONE -> create) and the approval loop - this file never re-implements any part of
it. Both fixture names ("Dana Cohen", "גיל ברטל") are PERMANENT ground-truth sandbox clients
(GROUND_TRUTH_CLIENTS.md), so `_seed_client` classifies them EXACT and raises
`ClientAlreadyExistsError` - the deterministic proof that no duplicate was created, regardless
of whether the model refuses pre-emptively or Morning's API rejects the duplicate.

**Test tier (Feature 029)**: real, text-only OpenAI calls (a vCard is plain text - no vision/
image call involved) -> `billed`, NOT `expensive`. Runs freely, no per-run approval needed, no
one-at-a-time restriction - see CLAUDE.md.

**Assumes the test environment is already up**: apps/morning-mcp-app must already be running
(./run_morning_mcp.sh) - see test_denidin_morning_invoice_creation_e2e.py's module docstring
for the full prerequisite list; `denidin_app`/`live_morning_tunnel` (this directory's
conftest.py fixtures, used below via parameter names) fail loudly, not silently, if it isn't.

NO MOCKING anywhere.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tests.billed.denidin_mcp_e2e_helpers import (
    GODFATHER_CHAT_ID,
    ClientAlreadyExistsError,
    _calls_for,
    _seed_client,
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


def _send_contact_card(chat_id: str, display_name: str, vcard: str, id_prefix: str):
    """Send ONE real contact-card WhatsApp turn through the real router handler
    (handle_contact_message) - the Feature 030 entry point. Returns
    (reply text, AIResponse). This is the ONLY thing this file does directly; the
    add-client conversation that follows is `_seed_client`'s job."""
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
    logger.info(f"contact-card turn reply: {response!r}")
    return response, ai_response


def _load_vcard(filename: str) -> str:
    return (_CONTACTS_FIXTURES_DIR / filename).read_text(encoding="utf-8")


def _parse_vcard(vcard: str) -> dict:
    """Pull name / phone / email out of a raw vCard, up front, so the parsed
    fields can be handed to `_seed_client` exactly like a typed request. Pure
    text parsing - no client-resolution logic here (that is `_seed_client`'s /
    `_resolve_client_name`'s single responsibility)."""
    name = phone = email = None
    for raw in vcard.splitlines():
        line = raw.strip()
        if line.startswith("FN:"):
            name = line[3:].strip() or name
        elif line.startswith("N:") and name is None:
            parts = line[2:].split(";")
            name = (parts[1] if len(parts) > 1 else parts[0]).strip() or None
        elif line.startswith("TEL") and ":" in line:
            phone = line.split(":", 1)[1].strip() or phone
        elif line.startswith("EMAIL") and ":" in line:
            email = line.split(":", 1)[1].strip() or email
    return {"name": name, "phone": phone, "email": email}


def _ledger_event_count_for_chat(denidin_app, chat_id: str) -> int:
    """Counts real persisted LedgerEvent files (data/events/*.json, Feature 033) for this
    chat_id - used as a before/after false-positive guard: a shared vCard's raw text goes
    through the exact same conversational AIHandler pipeline (and the same always-attached
    LEDGER_EVENT_TOOL) as any text message, so nothing structurally prevents the model from
    misreading contact-card fields as fee-agreement/bank-deposit content. Asserted after
    EVERY step below, not just the first (2026-09-02: a real run fired
    capture_ledger_event on the plain email-supply turn, invisible to a first-turn-only
    guard).

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
    """US1: a shared contact card with name+phone+email all present becomes a source of the
    same conversational add_client flow a typed request triggers.

    "Dana Cohen" is a PERMANENT ground-truth sandbox fixture (created 2026-07-30, real client
    id 2c4f7b86-07c1-44c6-b119-f8f0249958e1 - see GROUND_TRUTH_CLIENTS.md). Handing its parsed
    vCard fields to `_seed_client` therefore classifies EXACT and raises
    `ClientAlreadyExistsError` - the deterministic proof that no duplicate client resulted
    (whether the model refused pre-emptively or Morning's own API rejected the duplicate).
    The ledger-event false-positive guard holds after every step.
    """
    fields = _parse_vcard(_load_vcard("complete_card_dana_cohen.vcf"))
    assert fields["name"] == "Dana Cohen" and fields["email"] and fields["phone"]
    ledger_count_before = _ledger_event_count_for_chat(denidin_app, GODFATHER_CHAT_ID)

    card_response, card_ai_response = _send_contact_card(
        chat_id=GODFATHER_CHAT_ID,
        display_name="Dana Cohen",
        vcard=_load_vcard("complete_card_dana_cohen.vcf"),
        id_prefix="E2E_VCF_COMPLETE_CARD",
    )
    assert card_response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert not _calls_for(card_ai_response, "add_client"), (
        f"add_client executed for a client that already exists (real, permanent "
        f"'Dana Cohen' fixture) - should have refused plainly, never silently "
        f"duplicated or updated: {card_ai_response.mcp_calls if card_ai_response else None!r}"
    )
    assert _ledger_event_count_for_chat(denidin_app, GODFATHER_CHAT_ID) == ledger_count_before, (
        "capture_ledger_event was called on a raw vCard - contact-card fields "
        "(name/phone/email) must never be misread as fee-agreement/bank-deposit content"
    )

    with pytest.raises(ClientAlreadyExistsError):
        _seed_client(
            GODFATHER_CHAT_ID,
            "E2E_VCF_COMPLETE_SEED",
            name=fields["name"],
            email=fields["email"],
            phone=fields["phone"],
        )

    assert _ledger_event_count_for_chat(denidin_app, GODFATHER_CHAT_ID) == ledger_count_before, (
        "capture_ledger_event was called somewhere in the add_client flow - "
        "contact-card fields must never be misread as ledger content"
    )


@pytest.mark.billed
def test_godfather_shares_contact_card_missing_email_is_asked_for(denidin_app):
    """US2: the real fixture (00005372-גיל ברטל .vcf) has no EMAIL field at all - the common
    case for real WhatsApp contact shares. The bot must ask for the missing email before any
    add_client call or pending-approval state (Feature 026's REQ-CLIENT-012).

    Once the email is known, the add-client flow proceeds via `_seed_client` (its `text=` first
    turn IS the email-supply reply). "גיל ברטל" is a PERMANENT ground-truth sandbox fixture
    (created 2026-07-30, real client_id 04d1c153-6d9c-467f-9eb1-a9661b4df4b6 -
    GROUND_TRUTH_CLIENTS.md), so `_seed_client` classifies EXACT and raises
    `ClientAlreadyExistsError` - deterministic proof no duplicate resulted. The ledger-event
    false-positive guard holds after every step.

    KNOWN FAILURE - BLOCKED ON FEATURE 069 (do not "fix" here). Observed live
    (2026-09-02 billed sweep, and again during Feature 059 triage 2026-09-03):
    on the bare contact card the model resolves "גיל ברטל" -> EXACT and replies
    "לקוח כבר קיים ... לא אוסיף לקוח כפול" instead of first asking for the
    missing email (REQ-CLIENT-012 ordering). `capture_ledger_event` fires in the
    same turn's tool activity - the misfire that reroutes the model past the
    ordered resolve/ask flow. Feature 069
    (`specs/backlog/069-mandatory-client-resolution-before-ledger-event`) is the
    gate that makes client resolution run first and deterministically around any
    ledger-relevant recognition; this test is expected to go green with it. Left
    red on purpose until then - see
    `specs/done/059-stabilize-tests-sanity-suite/sanity-failures.md` (N5) and
    that spec's own `spec.md`.
    """
    vcard = _load_vcard("00005372-גיל ברטל .vcf")
    assert "EMAIL" not in vcard  # sanity: this fixture genuinely has no email
    fields = _parse_vcard(vcard)
    assert fields["name"] == "גיל ברטל" and fields["phone"] and fields["email"] is None
    known_email = "gil.bartal.qs@example.com"  # the fixture's real email (GROUND_TRUTH_CLIENTS.md)
    ledger_count_before = _ledger_event_count_for_chat(denidin_app, GODFATHER_CHAT_ID)

    card_response, card_ai_response = _send_contact_card(
        chat_id=GODFATHER_CHAT_ID,
        display_name="גיל ברטל",
        vcard=vcard,
        id_prefix="E2E_VCF_NOEMAIL_CARD",
    )
    assert card_response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert not _calls_for(card_ai_response, "add_client"), (
        f"add_client executed despite a missing email on the shared contact card: "
        f"{card_ai_response.mcp_calls if card_ai_response else None!r}"
    )
    # "דוא"ל" (the formal Hebrew abbreviation for "דואר אלקטרוני") is an equally
    # correct answer the model gave for real (2026-08-02) that "מייל"/"אימייל"
    # alone didn't catch - "דוא" as a substring covers "דוא״ל"/"דואל"/"דוא'ל"
    # regardless of which quote-character renders the geresh.
    assert "מייל" in card_response or "אימייל" in card_response or "דוא" in card_response, (
        f"Expected the bot to ask for the missing email, got: {card_response!r}"
    )
    assert _ledger_event_count_for_chat(denidin_app, GODFATHER_CHAT_ID) == ledger_count_before, (
        "capture_ledger_event was called on a raw vCard - contact-card fields "
        "(name/phone/email) must never be misread as fee-agreement/bank-deposit content"
    )

    with pytest.raises(ClientAlreadyExistsError):
        _seed_client(
            GODFATHER_CHAT_ID,
            "E2E_VCF_NOEMAIL_SEED",
            name=fields["name"],
            text=known_email,  # first turn = the email-supply reply the bot just asked for
            email=known_email,
            phone=fields["phone"],
        )

    assert _ledger_event_count_for_chat(denidin_app, GODFATHER_CHAT_ID) == ledger_count_before, (
        "capture_ledger_event was called somewhere in the add_client flow (e.g. on the "
        "plain email-supply turn) - contact-card fields must never be misread as ledger content"
    )
