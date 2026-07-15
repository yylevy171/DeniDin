"""
E2E Tests (Feature 018): Godfather manages Morning invoices via natural WhatsApp
conversation - real webhook, real OpenAI Responses API, real Morning MCP server,
real Morning sandbox.

Flow (entry point is the real Green API webhook, dispatched through the actual
@bot.router.message-decorated `handle_text_message` - CONSTITUTION §V):

    Green API textMessage webhook (godfather sender)
      -> handle_text_message (real router handler, not a direct internal call)
      -> WhatsAppHandler.process_notification
      -> AIHandler.get_response
           -> client.responses.create (real OpenAI Responses API call)
              with the real Morning MCP server registered as a remote tool
              (reached over its already-open ngrok tunnel, bearer-authenticated)
      -> bot replies in Hebrew

**Prompts portray a real, non-technical user (2026-07-14 decision)**: the user
never knows about tools, parameter names, or internal ids (Morning documentId
GUIDs) - only casual references a person would actually use (a client's name,
a date, "the invoice for X"). Whatever normalization/resolution this requires
(mapping "88 שח" to amount=88, resolving "the invoice for יוסי" to a real
invoice_id via list_invoices, asking for missing required fields and waiting
for the reply) is the runtime constitution's job, not the test's - see
data/constitution/runtime_constitution.md's "Understanding invoicing requests"
section. Tests do not retry across turns (2026-07-15 decision): each prompt is
a single, natural, non-technical message - the model is expected to call the
right tool immediately (date resolution via the constitution's year anchor,
state-changing confirmation always bypassed per the runtime constitution
itself - no test-only carve-out) rather than being coaxed across a follow-up
turn.

**Invoice amount/description are randomized per run (2026-07-15 decision)**:
a real, observed failure mode is the model fabricating a plausible-looking
"success" reply (invoice number, fake link) instead of actually calling
`create_invoice`, when the conversation history already contains one or more
near-identical prior create_invoice turns (same amount, same description
shape) - see `_random_amount`/`_random_description` below. Varying these
values on every call reduces the repetition that triggers this pattern
completion; `src/handlers/ai_handler.py` also logs a WARNING
("Possible hallucinated invoicing confirmation") whenever a reply reads like
a state-changing confirmation with no matching `mcp_call`, as a production
detection safety net (not a behavior change).

RBAC and the memory system are always on (no feature flags, 2026-07-14) -
session memory is what makes these natural multi-turn conversations work
correctly (the model actually remembers the prior turn, not just an id smuggled
into the prompt text).

**Assumes the test environment is already up**: apps/morning-mcp-app must
already be running (./run_morning_mcp.sh) against sandbox credentials, with
feature_flags.enable_mcp_server=true, mcp.auth_token set to the SAME value as
this app's own config.test.json mcp.morning_auth_token, and its ngrok tunnel
already open. This test does NOT start the Morning server or ngrok - if the
shared status file shows no live tunnel, the test fails immediately with a
clear "NO TUNNEL" message. Whenever apps/morning-mcp-app changes, restart it
(./stop_morning_mcp.sh && ./run_morning_mcp.sh) before retrying - Python does
not hot-reload (see CLAUDE.md).

**Uses config/config.test.json exclusively** (both apps use their own test
config during testing) - never config/config.json.

**App-wall**: this test never reads morning-mcp-app's config or any other file,
and never imports its code. Verification of tool-call success uses the real
OpenAI Responses API's own `mcp_call` output, exposed on
`AIHandler.last_response.mcp_calls` (see src/handlers/ai_handler.py) - not
Morning's raw REST API, and not Morning's credentials.

NO MOCKING anywhere. @pytest.mark.expensive: real OpenAI billing on every run.
Per CLAUDE.md/CONSTITUTION §VII: human approval is required before every single
run of this test, run alone (never as part of a batch), read logs/test_logs/
before re-running, and only re-run after a confident fix. Never re-run a test
yourself once it has actually been billed (reached OpenAI) without fresh
explicit approval - see CLAUDE.md.
"""
from __future__ import annotations

import logging
import random
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

import pytest

from src.models.config import AppConfiguration
from src.models.message import AIResponse
from .denidin_mcp_e2e_helpers import (
    DENIDIN_APP_DIR,
    NoMorningTunnelError,
    build_text_webhook,
    create_real_notification,
    get_response,
    require_live_morning_tunnel,
)

logger = logging.getLogger(__name__)

_DESCRIPTIONS = ("ייעוץ", "עיצוב", "פיתוח", "תחזוקה", "הדרכה", "ליווי עסקי")
_CLIENT_STEMS = ("אלפא", "בטא", "גמא", "דלתא", "אומגא", "סיגמא", "נובה", "אוריון")


def _random_amount() -> int:
    """A varied, non-round amount - avoids the exact repeated shape
    (same amount every call) that has been observed to trigger the model
    fabricating a plausible-looking success reply instead of actually
    calling create_invoice."""
    return random.randint(40, 950)


def _random_description() -> str:
    return random.choice(_DESCRIPTIONS)


def _unique_client_name() -> str:
    """A unique, operation-NEUTRAL client name for a freshly-seeded invoice.

    Critical (2026-07-15): earlier markers embedded the operation word into
    the client name/description (e.g. "Test Corp DENIDIN_E2E_CANCEL_...").
    The model reads that data and the literal "CANCEL"/"PAID" leaked intent
    into it - a real, billed failure had the model call
    update_invoice_status(status="cancelled") in response to a plain *create*
    request, purely because "CANCEL" appeared in the client name (the
    constitution maps "בטל"/cancel-words to status="cancelled"). Real client
    names never encode the operation, so neither do these: just a neutral
    stem + a short random hex token for uniqueness/traceability.
    """
    return f"חברת {random.choice(_CLIENT_STEMS)} {random.randbytes(3).hex()}"

GODFATHER_CHAT_ID = "972500000018@c.us"  # Feature 018 E2E test godfather identity


@pytest.fixture(scope="module")
def denidin_config():
    """Load denidin-app's own TEST config (real secrets, gitignored) - never
    config.json. Isolated to test_data, this test's godfather identity."""
    config_path = DENIDIN_APP_DIR / "config" / "config.test.json"
    if not config_path.exists():
        pytest.skip("config/config.test.json not found")

    config = AppConfiguration.from_file(str(config_path))
    config.validate()

    if not config.ai_api_key or config.ai_api_key.startswith("sk-test"):
        pytest.skip("No real ai_api_key configured in config/config.test.json")
    if not config.mcp or not config.mcp.get('morning_auth_token'):
        pytest.skip(
            "config/config.test.json has no mcp.morning_auth_token configured - "
            "it must match the already-running Morning server's own mcp.auth_token"
        )

    test_data_root = DENIDIN_APP_DIR / "test_data"
    config.data_root = str(test_data_root)
    sessions_dir = test_data_root / "sessions"
    config.memory['session']['storage_dir'] = str(sessions_dir)
    config.memory['longterm']['storage_dir'] = str(test_data_root / "memory")

    # Start every pytest invocation from a CLEAN session store (2026-07-15).
    # The godfather session is persisted to disk and is NOT reset between
    # separate `pytest` runs, so it accumulated dozens of turns across every
    # run today - a real, billed failure had the model load a 7400-token
    # history full of earlier "couldn't find" failures and just imitate that
    # pattern (replying "couldn't find" without even calling a tool) instead
    # of acting on the invoice it had just created one turn earlier. A real
    # user's conversation never carries a different run's history; clearing
    # here makes each invocation an independent conversation. Tests WITHIN one
    # invocation still share the session (the intended multi-turn "one long
    # chat" - create -> mark paid, etc. - is preserved); only cross-run
    # carryover is dropped.
    if sessions_dir.exists():
        shutil.rmtree(sessions_dir)

    # AIHandler._load_constitution() reads from <data_root>/constitution/<file>,
    # so overriding data_root above means it would otherwise find nothing here
    # (empty constitution -> no Morning-tool scope/confirmation guidance, no
    # role-context sections). Mirror the real constitution into test_data so
    # this test exercises the actual guidance, kept in sync automatically.
    real_constitution_dir = DENIDIN_APP_DIR / "data" / "constitution"
    test_constitution_dir = test_data_root / "constitution"
    constitution_filename = config.constitution_config.get('file', 'runtime_constitution.md')
    real_constitution_file = real_constitution_dir / constitution_filename
    if real_constitution_file.exists():
        test_constitution_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(real_constitution_file, test_constitution_dir / constitution_filename)

    config.godfather_phone = GODFATHER_CHAT_ID
    config.user_roles = {'admin_phones': [], 'blocked_phones': []}

    return config


@pytest.fixture(scope="module")
def live_morning_tunnel(denidin_config):
    """Fail immediately (not skip) if the Morning MCP server/tunnel isn't live."""
    status_file_path = Path(denidin_config.mcp['morning_status_file'])
    max_age = denidin_config.mcp.get('url_max_age_seconds', 0) or 0
    try:
        server_url = require_live_morning_tunnel(status_file_path, max_age)
    except NoMorningTunnelError as exc:
        pytest.fail(str(exc), pytrace=False)
    return server_url


@pytest.fixture(scope="module")
def denidin_app(denidin_config, live_morning_tunnel):
    """Initialize the full DeniDin app - NO MOCKING - against the live Morning tunnel."""
    import denidin

    config_dict = {
        'green_api_instance_id': denidin_config.green_api_instance_id,
        'green_api_token': denidin_config.green_api_token,
        'ai_api_key': denidin_config.ai_api_key,
        'ai_model': denidin_config.ai_model,
        'ai_vision_model': denidin_config.ai_vision_model,
        'ai_embedding_model': denidin_config.ai_embedding_model,
        'ai_reply_max_tokens': denidin_config.ai_reply_max_tokens,
        'temperature': denidin_config.temperature,
        'log_level': denidin_config.log_level,
        'data_root': denidin_config.data_root,
        'feature_flags': denidin_config.feature_flags,
        'godfather_phone': denidin_config.godfather_phone,
        'memory': denidin_config.memory,
        'constitution_config': denidin_config.constitution_config,
        'user_roles': denidin_config.user_roles,
        'mcp': denidin_config.mcp,
    }
    # handle_text_message (the real @bot.router.message-decorated handler)
    # checks the module-level denidin.denidin_app global, not a local variable
    # - must assign it here, matching tests/expensive/test_simple_text_e2e.py's
    # existing pattern, or the router handler treats the app as uninitialized.
    denidin.denidin_app = denidin.initialize_app(config_dict)
    return denidin.denidin_app


def _send_turn(chat_id: str, text: str, id_prefix: str) -> Tuple[Optional[str], Optional[AIResponse]]:
    """Send one real WhatsApp turn through the real router handler and return
    (reply text, AIResponse with mcp_calls) for inspection."""
    from denidin import handle_text_message

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

    if ai_response is not None:
        for call in ai_response.mcp_calls:
            logger.info(
                f"mcp_call: name={call['name']} error={call['error']!r} "
                f"arguments={call['arguments']!r} output={call['output']!r}"
            )
    logger.info(f"Bot response: {response}")

    return response, ai_response


def _calls_for(ai_response: Optional[AIResponse], tool_name: str) -> List[dict]:
    if ai_response is None:
        return []
    return [c for c in ai_response.mcp_calls if c["name"] == tool_name]


# Tests do not retry: each prompt is a single, natural, non-technical
# message, and the model is expected to call the right tool immediately.
# Ambiguity that a real production conversation would resolve across turns
# (date year) is instead resolved by the runtime constitution's own
# date-anchor guidance - not by scripting a follow-up turn here. State-changing
# actions also proceed immediately in a single turn: the constitution no
# longer asks the model to pause for a confirmation reply from anyone.


# ============================================================================
# create_invoice
# ============================================================================

@pytest.mark.expensive
def test_godfather_creates_invoice_via_whatsapp(denidin_app):
    """Godfather asks for a new invoice the way a real, non-technical person
    would - client name, amount, and what it's for, all in one message - and
    the constitution now calls tools immediately with no confirmation wait,
    so the single turn is expected to actually call the tool (tests do not
    retry across turns).

    Verification (independent signals, not the model's unverified claim alone):
    1. mcp_calls shows a create_invoice call with no error.
    2. The final reply contains an invoice link - the runtime constitution now
       says create_invoice confirmations must always include one, unprompted,
       so this isn't a special ask in the test prompt.
    """
    client_name = "יוסי שמואלי"
    amount = _random_amount()
    description = _random_description()

    response, ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=f"תפיק חשבונית חדשה עבור {client_name} על סך {amount} שח עבור {description}",
        id_prefix="E2E_CREATE",
    )
    create_calls = _calls_for(ai_response, "create_invoice")

    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert len(response) > 0

    assert create_calls, (
        f"Model never invoked create_invoice via the remote MCP server, even "
        f"after a natural follow-up. mcp_calls: {ai_response.mcp_calls!r}. "
        f"Final reply: {response!r}"
    )
    assert all(c["error"] is None for c in create_calls), (
        f"create_invoice call(s) reported an error: {create_calls}"
    )
    assert any(client_name in (c["arguments"] or "") for c in create_calls), (
        f"create_invoice was not called with the client name {client_name!r}: {create_calls!r}"
    )

    # The reply must actually carry a link, not just confirm success in the abstract.
    assert "http" in response, (
        f"Bot reply did not include an invoice link. Full reply: {response!r}"
    )


# ============================================================================
# list_invoices
# ============================================================================

# Fixed, genuinely closed historical date in the Morning sandbox (verified
# free, no billing, 2026-07-13): exactly 6 real invoices exist for this date,
# well under list_invoices' 10-item display cap, so nothing is truncated, and
# being months in the past it will never gain more invoices (unlike "today").
KNOWN_FIXED_DATE = "2026-02-07"
KNOWN_INVOICE_NUMBERS_ON_FIXED_DATE = ("60001", "60006")  # first and last of the 6


@pytest.mark.expensive
def test_godfather_lists_invoices_via_whatsapp(denidin_app):
    """Godfather asks to see invoices from a specific day, the way a real
    person would - no year given (a real user rarely bothers), no format or
    field instructions, no mention of "internal ids" or any technical detail.
    Tests do not retry across turns, so the runtime constitution's date
    guidance must resolve the year correctly on this single shot - that's
    exactly what this test verifies.

    Verification is split two ways:
    1. Tool correctness: the mcp_call's own output (not the model's casual
       reply) must show the real, known ground truth - multiple distinct
       known invoice numbers, all 5 fields present (name, amount, date, id,
       status) - proving list_invoices itself returned complete, correct data
       for the right date.
    2. User experience: the actual reply the user received must exist and
       plausibly reflect that invoices were found (not required to repeat
       internal ids - a real user wouldn't want that, and the runtime
       constitution doesn't ask the model to include it in a casual reply).
    """
    response, ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text="תראה לי את כל החשבוניות מיום 7 בפברואר",
        id_prefix="E2E_LIST",
    )
    list_calls = _calls_for(ai_response, "list_invoices")

    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert len(response) > 0

    assert list_calls, (
        f"Model never invoked list_invoices via the remote MCP server, even "
        f"after confirming the year. mcp_calls: {ai_response.mcp_calls!r}. "
        f"Final reply: {response!r}"
    )
    assert all(c["error"] is None for c in list_calls), (
        f"list_invoices call(s) reported an error: {list_calls}"
    )
    assert any(KNOWN_FIXED_DATE in (c["arguments"] or "") for c in list_calls), (
        f"list_invoices was not called with the resolved date ({KNOWN_FIXED_DATE}) "
        f"in its arguments: {list_calls!r}"
    )

    # Tool correctness: real, known ground truth in the tool's own output.
    combined_output = "\n".join(c["output"] or "" for c in list_calls)
    found_numbers = [n for n in KNOWN_INVOICE_NUMBERS_ON_FIXED_DATE if n in combined_output]
    assert len(found_numbers) >= 2, (
        f"Expected at least 2 known invoice numbers {KNOWN_INVOICE_NUMBERS_ON_FIXED_DATE} "
        f"in the tool output, found {found_numbers}. Tool output: {combined_output!r}"
    )
    assert "₪" in combined_output, f"Tool output missing amount field: {combined_output!r}"
    assert "מזהה" in combined_output, f"Tool output missing invoice id field: {combined_output!r}"
    assert "שולם" in combined_output, f"Tool output missing status field: {combined_output!r}"


# ============================================================================
# get_invoice_details
# ============================================================================

# One fully-known invoice from the fixed 2026-02-07 set (verified free, no
# billing) - referenced here by client name + date only, the way a real user
# would; the model must resolve the actual invoice_id itself.
KNOWN_INVOICE_NUMBER = "60006"
KNOWN_INVOICE_CLIENT = "Test Client DENIDIN_TEST_1770474207"
KNOWN_INVOICE_AMOUNT_IL = "123.45"
KNOWN_INVOICE_STATUS_HE = "שולם"  # paid


@pytest.mark.expensive
def test_godfather_gets_invoice_details_via_whatsapp(denidin_app):
    """Godfather asks about a specific invoice by client name and date only -
    never an id. The model must resolve which invoice this is itself (via
    list_invoices and/or get_invoice_details) and reply with the real details.

    Verification checks the FINAL reply (what the user actually saw) against
    known ground truth - this is the tightest test in the suite (one specific,
    fully-known invoice, no pagination/date-range ambiguity) - and does not
    require a specific tool name to have been used, since a real user has no
    way to know or care which tool satisfies their request.
    """
    response, ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=(
            f"מה הסטטוס והפרטים המלאים של החשבונית של {KNOWN_INVOICE_CLIENT} "
            f"מהשבעה בפברואר?"
        ),
        id_prefix="E2E_DETAILS",
    )

    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert len(response) > 0

    relevant_calls = _calls_for(ai_response, "list_invoices") + _calls_for(ai_response, "get_invoice_details")
    assert relevant_calls, (
        f"Model did not look up the invoice via any Morning MCP tool. "
        f"mcp_calls: {ai_response.mcp_calls!r}. Bot reply: {response!r}"
    )
    assert all(c["error"] is None for c in relevant_calls), (
        f"Invoice lookup call(s) reported an error: {relevant_calls}"
    )

    # Exact-match verification against the one fully-known invoice.
    assert KNOWN_INVOICE_NUMBER in response, (
        f"Bot reply missing invoice number {KNOWN_INVOICE_NUMBER}. Full reply: {response!r}"
    )
    assert KNOWN_INVOICE_AMOUNT_IL in response, (
        f"Bot reply missing amount {KNOWN_INVOICE_AMOUNT_IL}. Full reply: {response!r}"
    )
    assert KNOWN_INVOICE_STATUS_HE in response, (
        f"Bot reply missing status {KNOWN_INVOICE_STATUS_HE!r}. Full reply: {response!r}"
    )


# ============================================================================
# update_invoice_status - paid / cancelled flows
# ============================================================================

def _seed_fresh_invoice(client_name: str, amount: int, description: str) -> None:
    """Seed a fresh invoice via a real, single WhatsApp turn (the constitution
    calls create_invoice immediately, no confirmation wait) so the paid/cancel
    flow tests below mutate a fresh invoice
    each run, never the reusable 2026-02-07 fixed set. The seeded client name
    is what later turns use to reference the invoice - never an id."""
    response, ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=f"צור חשבונית ל-{client_name} על {amount} ₪ עבור {description}",
        id_prefix="E2E_SEED",
    )
    create_calls = _calls_for(ai_response, "create_invoice")
    assert create_calls and create_calls[0]["error"] is None, (
        f"Seed create_invoice failed or was not called: {ai_response.mcp_calls!r}"
    )
    logger.info(f"Seeded fresh invoice for client {client_name!r}")


@pytest.mark.expensive
def test_godfather_marks_invoice_paid_via_whatsapp(denidin_app):
    """Full invoice_paid flow: godfather creates a fresh invoice, then - in a
    separate, later turn - asks to mark IT as paid by client name only (never
    an id). The model must resolve the invoice itself (via list_invoices
    and/or session memory) before calling update_invoice_status.

    Verifies the resulting status - not just that the tool call didn't error
    - via update_invoice_status's own returned confirmation (which re-fetches
    the invoice after marking it paid) showing status=שולם.

    Uses a freshly-created invoice (not the reusable 2026-02-07 fixed set)
    since marking paid is a real, effectively irreversible state change in
    the sandbox (Morning has no supported reversal for a receipt-closed
    invoice).
    """
    client_name = _unique_client_name()
    _seed_fresh_invoice(client_name, _random_amount(), _random_description())

    response, ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=f"סמן את החשבונית של {client_name} כשולמה",
        id_prefix="E2E_PAID",
    )
    status_calls = _calls_for(ai_response, "update_invoice_status")

    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert len(response) > 0

    assert status_calls, (
        f"Model never invoked update_invoice_status via the remote MCP server. "
        f"mcp_calls: {ai_response.mcp_calls!r}. Final reply: {response!r}"
    )
    assert all(c["error"] is None for c in status_calls), (
        f"update_invoice_status call(s) reported an error: {status_calls}"
    )
    assert any('"status":"paid"' in (c["arguments"] or "") for c in status_calls), (
        f"update_invoice_status was not called with status=paid: {status_calls!r}"
    )

    # The resulting status, not just call success, is what this flow proves:
    # update_invoice_status re-fetches the invoice after marking it paid and
    # returns the standard confirmation - it must now say שולם (paid).
    assert any("שולם" in (c["output"] or "") for c in status_calls), (
        f"update_invoice_status output did not reflect paid status: {status_calls!r}"
    )
    assert "שולם" in response, f"Bot reply did not reflect paid status. Full reply: {response!r}"


@pytest.mark.expensive
def test_godfather_cancels_invoice_via_whatsapp(denidin_app):
    """Full cancel_invoice flow: godfather creates a fresh invoice, then - in a
    separate, later turn - asks to cancel it by client name only (never an
    id, never the word "update_invoice_status", never the English status
    value). The model must resolve the invoice itself before acting.

    Verifies the resulting status via update_invoice_status's own returned
    confirmation ("חשבונית מספר X בוטלה... הופקה חשבונית זיכוי...") - Israeli
    law forbids voiding a tax invoice outright, so Morning's real mechanism is
    a linked Credit Invoice, not a status flag flip. The runtime constitution
    now states explicitly that this is a fully legitimate, ordinary action.

    Uses a freshly-created invoice (not the reusable 2026-02-07 fixed set)
    since cancelling is a real, permanent action (issues a real linked credit
    invoice in the sandbox).
    """
    client_name = _unique_client_name()
    _seed_fresh_invoice(client_name, _random_amount(), _random_description())

    response, ai_response = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=f"בטל את החשבונית של {client_name}",
        id_prefix="E2E_CANCEL",
    )
    status_calls = _calls_for(ai_response, "update_invoice_status")

    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert len(response) > 0

    assert status_calls, (
        f"Model never invoked update_invoice_status via the remote MCP server. "
        f"mcp_calls: {ai_response.mcp_calls!r}. Final reply: {response!r}"
    )
    assert all(c["error"] is None for c in status_calls), (
        f"update_invoice_status call(s) reported an error: {status_calls}"
    )
    assert any('"status":"cancelled"' in (c["arguments"] or "") for c in status_calls), (
        f"update_invoice_status was not called with status=cancelled: {status_calls!r}"
    )

    # The resulting status, not just call success: the cancellation message
    # explicitly says "בוטלה" (cancelled) and mentions the linked credit
    # invoice issued to offset the amount.
    assert any("בוטל" in (c["output"] or "") for c in status_calls), (
        f"update_invoice_status output did not reflect cancelled status: {status_calls!r}"
    )
    assert "בוטל" in response, f"Bot reply did not reflect cancelled status. Full reply: {response!r}"
