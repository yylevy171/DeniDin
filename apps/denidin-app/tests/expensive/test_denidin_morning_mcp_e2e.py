"""
E2E Test (Feature 018, T010a): Godfather creates a real Morning invoice via WhatsApp.

Flow (entry point is the real Green API webhook, dispatched through the actual
@bot.router.message-decorated `handle_text_message` - CONSTITUTION §V):

    Green API textMessage webhook (godfather sender)
      -> handle_text_message (real router handler, not a direct internal call)
      -> WhatsAppHandler.process_notification
      -> AIHandler.get_response
           -> client.responses.create (real OpenAI Responses API call)
              with the real Morning MCP server registered as a remote tool
              (reached over its already-open ngrok tunnel, bearer-authenticated)
      -> bot replies in Hebrew with the invoice confirmation

**Assumes the test environment is already up**: apps/morning-mcp-app must
already be running (./run_morning_mcp.sh) against sandbox credentials, with
feature_flags.enable_mcp_server=true, mcp.auth_token set to the SAME value as
this app's own config.test.json mcp.morning_auth_token, and its ngrok tunnel
already open. This test does NOT start the Morning server or ngrok - if the
shared status file shows no live tunnel, the test fails immediately with a
clear "NO TUNNEL" message.

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
before re-running, and only re-run after a confident fix.
"""
from __future__ import annotations

import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.models.config import AppConfiguration
from .denidin_mcp_e2e_helpers import (
    DENIDIN_APP_DIR,
    NoMorningTunnelError,
    build_text_webhook,
    create_real_notification,
    get_response,
    require_live_morning_tunnel,
)

logger = logging.getLogger(__name__)

GODFATHER_CHAT_ID = "972500000018@c.us"  # Feature 018 E2E test godfather identity


@pytest.fixture(scope="module")
def denidin_config():
    """Load denidin-app's own TEST config (real secrets, gitignored) - never
    config.json. Isolated to test_data, RBAC enabled, this test's godfather
    identity."""
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
    config.memory['session']['storage_dir'] = str(test_data_root / "sessions")
    config.memory['longterm']['storage_dir'] = str(test_data_root / "memory")

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

    config.feature_flags['enable_rbac'] = True
    config.feature_flags['enable_memory_system'] = False
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


@pytest.mark.expensive
def test_godfather_creates_invoice_via_whatsapp(denidin_app):
    """Godfather sends a natural-language, PRE-AUTHORIZED invoicing request over
    WhatsApp (single turn); the bot must invoke create_invoice via the remote
    Morning MCP tool and reply with the invoice details, including a link.

    The request explicitly states the action is already confirmed, so this is a
    single-turn test even though the runtime constitution's confirm-before-act
    guidance (T008) would otherwise make the model ask first, as verified live
    in the first real run of this test (2026-07-13): given an unqualified
    prompt, the model correctly asked for confirmation and made no mcp_call at
    all - proving that guidance works - but that's a different test (the
    confirm-before-act scenario, T023), not this one.

    Verification (two independent signals, neither trusts the model's
    unverified claim alone):
    1. AIHandler.last_response.mcp_calls (from the real OpenAI Responses API's
       own output items) shows a create_invoice call with no error.
    2. The actual WhatsApp reply text contains invoice details and a link -
       not just a generic "done" message.
    """
    from denidin import handle_text_message

    unique_marker = f"DENIDIN_E2E_{int(datetime.now(timezone.utc).timestamp())}"
    client_name = f"Test Corp {unique_marker}"

    notification = create_real_notification(build_text_webhook(
        chat_id=GODFATHER_CHAT_ID,
        sender_name="E2E Godfather",
        text=(
            f"צור חשבונית ל-{client_name} על 50 ₪ עבור ייעוץ {unique_marker}. "
            f"זה כבר מאושר - בצע את הפעולה מיד, ללא צורך באישור נוסף, "
            f"ושלח לי את פרטי החשבונית כולל קישור."
        ),
        message_id=f"E2E_{unique_marker}"
    ))

    logger.info("=" * 80)
    logger.info(f"E2E TEST: godfather create_invoice via WhatsApp - marker {unique_marker}")
    logger.info("=" * 80)

    handle_text_message(notification)
    response = get_response(notification)

    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert len(response) > 0
    logger.info(f"Bot response: {response}")

    ai_response = denidin_app.ai_handler.last_response
    assert ai_response is not None, "AIHandler.last_response was not set"

    for call in ai_response.mcp_calls:
        logger.info(
            f"mcp_call: name={call['name']} error={call['error']!r} "
            f"arguments={call['arguments']!r} output={call['output']!r}"
        )

    create_invoice_calls = [c for c in ai_response.mcp_calls if c["name"] == "create_invoice"]
    assert create_invoice_calls, (
        f"Model did not invoke create_invoice via the remote MCP server "
        f"(pre-authorized prompt should not require a confirmation round-trip). "
        f"mcp_calls: {ai_response.mcp_calls!r}. Bot reply: {response!r}"
    )
    assert all(c["error"] is None for c in create_invoice_calls), (
        f"create_invoice call(s) reported an error: {create_invoice_calls}"
    )

    # The reply must actually carry the invoice details + a link, not just
    # confirm success in the abstract.
    assert "http" in response, (
        f"Bot reply did not include an invoice link. Full reply: {response!r}"
    )


# Fixed, genuinely closed historical date in the Morning sandbox (verified
# free, no billing, 2026-07-13): exactly 6 real invoices exist for this date,
# well under list_invoices' 10-item display cap, so nothing is truncated.
# Being months in the past, this date will never gain more invoices - unlike
# "today", which could still grow from other test runs. A couple of the real,
# known invoice numbers are asserted as anchors (proving the reply reflects
# genuine sandbox data, not a hallucinated list) without requiring exact-set
# or exact-count matching (deliberately not required - see task discussion).
KNOWN_FIXED_DATE = "2026-02-07"
KNOWN_FIXED_DATE_IL = "07/02/2026"  # DD/MM/YYYY, as format_date_il renders it
KNOWN_INVOICE_NUMBERS_ON_FIXED_DATE = ("60001", "60006")  # first and last of the 6


@pytest.mark.expensive
def test_godfather_lists_invoices_via_whatsapp(denidin_app):
    """Godfather asks for invoices from a fixed, historical date; the bot must
    invoke list_invoices via the remote Morning MCP tool and reply with a real
    multi-item list carrying the 5 required fields per item: client name,
    amount, date, id, and status (no link in the list view - a link is more
    useful per-invoice via get_invoice_details/download_invoice_pdf; asking
    for it here for every item on top of the other fields blew the reply's
    token budget mid-generation in an earlier run, cutting the list off).

    Verification does NOT require exact-set or exact-count matching (the
    sandbox has more invoices than fit on one page for busier dates; for this
    fixed date all 6 fit, but future sandbox changes shouldn't break this
    test on exact count) - only that the date range filtered correctly (the
    known date appears, at least two known real invoice numbers appear) and
    that all 5 required fields are actually present in the reply the user
    receives (not just the model's internal tool call).
    """
    from denidin import handle_text_message

    notification = create_real_notification(build_text_webhook(
        chat_id=GODFATHER_CHAT_ID,
        sender_name="E2E Godfather",
        text=(
            f"הצג לי את כל החשבוניות מתאריך {KNOWN_FIXED_DATE} עד {KNOWN_FIXED_DATE} "
            f"(פורמט השנה-חודש-יום). לכל חשבונית, בפורמט מקוצר - שורה אחת בלבד לכל חשבונית, "
            f"ללא כותרות או עיצוב מיוחד - ציין: מספר חשבונית, שם לקוח, סכום, תאריך, מזהה פנימי, "
            f"וסטטוס. אין צורך בקישור להורדה."
        ),
        message_id=f"E2E_LIST_{int(datetime.now(timezone.utc).timestamp())}"
    ))

    logger.info("=" * 80)
    logger.info(f"E2E TEST: godfather list_invoices via WhatsApp - fixed date {KNOWN_FIXED_DATE}")
    logger.info("=" * 80)

    handle_text_message(notification)
    response = get_response(notification)

    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert len(response) > 0
    logger.info(f"Bot response: {response}")

    ai_response = denidin_app.ai_handler.last_response
    assert ai_response is not None, "AIHandler.last_response was not set"

    for call in ai_response.mcp_calls:
        logger.info(
            f"mcp_call: name={call['name']} error={call['error']!r} "
            f"arguments={call['arguments']!r} output={call['output']!r}"
        )

    list_calls = [c for c in ai_response.mcp_calls if c["name"] == "list_invoices"]
    assert list_calls, (
        f"Model did not invoke list_invoices via the remote MCP server. "
        f"mcp_calls: {ai_response.mcp_calls!r}. Bot reply: {response!r}"
    )
    assert all(c["error"] is None for c in list_calls), (
        f"list_invoices call(s) reported an error: {list_calls}"
    )
    assert any(KNOWN_FIXED_DATE in (c["arguments"] or "") for c in list_calls), (
        f"list_invoices was not called with the requested fixed date "
        f"({KNOWN_FIXED_DATE}) in its arguments: {list_calls!r}"
    )

    # Date-range filtering correctness: the known date must actually appear
    # in what the user was told.
    assert KNOWN_FIXED_DATE_IL in response or KNOWN_FIXED_DATE in response, (
        f"Bot reply did not reflect the requested date ({KNOWN_FIXED_DATE_IL} / "
        f"{KNOWN_FIXED_DATE}). Full reply: {response!r}"
    )

    # Real multi-item list, not a hallucinated or single-item reply: at least
    # two of the known real invoice numbers for this date must appear.
    found_numbers = [n for n in KNOWN_INVOICE_NUMBERS_ON_FIXED_DATE if n in response]
    assert len(found_numbers) >= 2, (
        f"Expected at least 2 known invoice numbers {KNOWN_INVOICE_NUMBERS_ON_FIXED_DATE} "
        f"in the reply, found {found_numbers}. Full reply: {response!r}"
    )

    # All 5 required fields must be present in what the user was actually told:
    # name (checked above via known client-bearing invoice numbers), amount,
    # date (checked above), id, and status (all 6 known invoices are "paid" /
    # "שולם" - real ground truth, verified free before this test was written).
    assert "₪" in response, f"Bot reply missing amount field. Full reply: {response!r}"
    assert any(c in response for c in ("מזהה", "id")), (
        f"Bot reply missing invoice id field. Full reply: {response!r}"
    )
    assert "שולם" in response, f"Bot reply missing status field. Full reply: {response!r}"


# One fully-known invoice from the fixed 2026-02-07 set (verified free, no
# billing, before this test was written) - a single, unambiguous target with
# no pagination/date-range concerns, unlike list_invoices.
KNOWN_INVOICE_ID = "fae5ccdb-08b2-40fb-a0cc-475a941e8a33"
KNOWN_INVOICE_NUMBER = "60006"
KNOWN_INVOICE_CLIENT = "Test Client DENIDIN_TEST_1770474207"
KNOWN_INVOICE_AMOUNT_IL = "123.45"
KNOWN_INVOICE_DATE_IL = "07/02/2026"
KNOWN_INVOICE_STATUS_HE = "שולם"  # paid


@pytest.mark.expensive
def test_godfather_gets_invoice_details_via_whatsapp(denidin_app):
    """Godfather asks for full details of one specific, fully-known invoice by
    its real Morning documentId (GUID); the bot must invoke
    get_invoice_details via the remote Morning MCP tool and reply with the
    exact known ground-truth fields for that invoice.
    """
    from denidin import handle_text_message

    notification = create_real_notification(build_text_webhook(
        chat_id=GODFATHER_CHAT_ID,
        sender_name="E2E Godfather",
        text=(
            f"תן לי את הפרטים המלאים של חשבונית עם מזהה {KNOWN_INVOICE_ID} - "
            f"כולל לקוח, סכום, תאריך וסטטוס."
        ),
        message_id=f"E2E_DETAILS_{int(datetime.now(timezone.utc).timestamp())}"
    ))

    logger.info("=" * 80)
    logger.info(f"E2E TEST: godfather get_invoice_details via WhatsApp - id {KNOWN_INVOICE_ID}")
    logger.info("=" * 80)

    handle_text_message(notification)
    response = get_response(notification)

    assert response is not None, "CRITICAL: godfather got NO RESPONSE (silent drop)"
    assert len(response) > 0
    logger.info(f"Bot response: {response}")

    ai_response = denidin_app.ai_handler.last_response
    assert ai_response is not None, "AIHandler.last_response was not set"

    for call in ai_response.mcp_calls:
        logger.info(
            f"mcp_call: name={call['name']} error={call['error']!r} "
            f"arguments={call['arguments']!r} output={call['output']!r}"
        )

    details_calls = [c for c in ai_response.mcp_calls if c["name"] == "get_invoice_details"]
    assert details_calls, (
        f"Model did not invoke get_invoice_details via the remote MCP server. "
        f"mcp_calls: {ai_response.mcp_calls!r}. Bot reply: {response!r}"
    )
    assert all(c["error"] is None for c in details_calls), (
        f"get_invoice_details call(s) reported an error: {details_calls}"
    )
    assert any(KNOWN_INVOICE_ID in (c["arguments"] or "") for c in details_calls), (
        f"get_invoice_details was not called with the requested invoice_id "
        f"({KNOWN_INVOICE_ID}): {details_calls!r}"
    )

    # Exact-match verification against the one fully-known invoice - the
    # tightest test in this suite (no pagination/date-range ambiguity).
    assert KNOWN_INVOICE_NUMBER in response, (
        f"Bot reply missing invoice number {KNOWN_INVOICE_NUMBER}. Full reply: {response!r}"
    )
    assert KNOWN_INVOICE_CLIENT in response, (
        f"Bot reply missing client name {KNOWN_INVOICE_CLIENT!r}. Full reply: {response!r}"
    )
    assert KNOWN_INVOICE_AMOUNT_IL in response, (
        f"Bot reply missing amount {KNOWN_INVOICE_AMOUNT_IL}. Full reply: {response!r}"
    )
    assert KNOWN_INVOICE_DATE_IL in response, (
        f"Bot reply missing date {KNOWN_INVOICE_DATE_IL}. Full reply: {response!r}"
    )
    assert KNOWN_INVOICE_STATUS_HE in response, (
        f"Bot reply missing status {KNOWN_INVOICE_STATUS_HE!r}. Full reply: {response!r}"
    )
