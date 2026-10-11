"""bugfix-071 - the full user-level VAT matrix, against the real Morning
sandbox, driven through the real MCP server: the exact API this app exposes
to OpenAI.

Source of truth: the human-approved matrix in
specs/repo/bugfixes/bugfix-071-morning-vat-zero-defect.md §2c. From the
user's perspective there is ONE VAT - the VAT inside the amount paid / to be
paid - and each document type accepts "VAT included", "VAT not included", or
nothing:

| Document                         | "included"   | "not included" | nothing             |
|----------------------------------|--------------|----------------|---------------------|
| 305 tax invoice                  | total = X    | total = X+VAT  | refuse - ask        |
| 300 transaction account          | total = X    | total = X+VAT  | refuse - ask        |
| 320 standalone                   | ignored      | conflict       | total paid = X      |
| 320 closing a 300                | ignored      | conflict       | amount paid         |
| 400 standalone                   | ignored      | conflict       | receipt = X         |
| 400 against a 305                | ignored      | conflict       | 305 total / partial |
| 330 against a taxable original   | ignored      | conflict       | mirrors original    |
| 330 against an exempt original   | conflict     | conflict       | mirrors original    |

"refuse" / "conflict" = MCP isError AND nothing created in Morning (and any
referenced original left without a new linked document). The error TEXT is
never asserted - only the isError flag and the absence of a document.

The user's words reach the tool as the `vat_included` argument (true /
false / omitted). Every stored value is an independent MorningClient
`get_invoice` read of the persisted document (raw fields amount / vat /
amountExcludeVat), never the tool's own reply. Expected numbers use Israeli
standard VAT (18%), confirmed live as this sandbox business's rate
(GET /documents/info: vatRate 0.18).

Scope: VAT only, at full amounts. Amounts relative to the original (partial,
above the open balance, cumulative) are OUT OF SCOPE for bugfix-071 (human
decision, 2026-10-05) - no cell here varies the amount.

A VAT conflict must be OUR refusal, raised before anything reaches Morning -
not Morning rejecting the payload (two cells once "passed" only because
Morning returned errorCode 2422). Conflict cells therefore also require the
error to be the app's own VAT-conflict error (errors.VAT_CONFLICT).

Many cells are EXPECTED RED on current code (METHODOLOGY §VII step 4).

No mocking (CONSTITUTION §I/§V) - real server, real MCP client, real sandbox.
"""
import asyncio
import json
import threading
import time
import uuid
from datetime import date
from pathlib import Path

import pytest
import uvicorn
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from denidin_mcp_morning import errors
from denidin_mcp_morning.config import load_config
from denidin_mcp_morning.morning_client import MorningClient
from denidin_mcp_morning.server import create_server
from denidin_mcp_morning.utils.time_utils import now_local
from tests.integration._seed_helpers import seed_real_client

APP_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = APP_ROOT / "config" / "config.test.json"

TEST_HOST = "127.0.0.1"
TEST_PORT = 8796

PAYMENT_DATE = "2026-07-12"

INCLUDED, NOT_INCLUDED, NOTHING = "included", "not_included", "nothing"

# (total, vat, net) - every figure live-confirmed in the sandbox (spec §2b/§2c)
X = 100.0
X_INCLUDED = (100.0, 15.25, 84.75)       # 100 with VAT inside
X_PLUS_VAT = (118.0, 18.0, 100.0)        # 100 + VAT on top
EXEMPT_100 = (100.0, 0.0, 100.0)


# ----------------------------------------------------------------- fixtures
def _load_config():
    config = load_config(CONFIG_PATH)
    if not (config.api_key_id and config.api_key_secret):
        pytest.skip("No api_key_id/api_key_secret in config.test.json")
    return config


def _new_client(config):
    return MorningClient(
        api_key_id=config.api_key_id,
        api_key_secret=config.api_key_secret,
        base_url=config.api_url,
        auth_url=config.auth_url,
    )


@pytest.fixture(scope="module")
def morning_client():
    """Seeding + independent read-back client (the server under test has its own)."""
    return _new_client(_load_config())


@pytest.fixture(scope="module")
def server_url():
    config = _load_config()
    mcp = create_server(config, client=_new_client(config))
    mcp.settings.host = TEST_HOST
    mcp.settings.port = TEST_PORT

    uv_server = uvicorn.Server(
        uvicorn.Config(mcp.streamable_http_app(), host=TEST_HOST, port=TEST_PORT, log_level="warning")
    )
    thread = threading.Thread(target=uv_server.run, daemon=True)
    thread.start()
    for _ in range(50):
        if uv_server.started:
            break
        time.sleep(0.1)
    else:
        pytest.fail("FastMCP server did not start in time")

    yield f"http://{TEST_HOST}:{TEST_PORT}{mcp.settings.streamable_http_path}"

    uv_server.should_exit = True
    thread.join(timeout=5)


# ------------------------------------------------------------------ helpers
def _call_tool(server_url, name, arguments):
    """One real MCP tool call. Returns (is_error, text)."""

    async def _run():
        async with streamable_http_client(server_url) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await session.call_tool(name, arguments)

    result = asyncio.run(_run())
    text = "".join(block.text for block in result.content if hasattr(block, "text"))
    return bool(result.isError), text


def _with_vat(arguments, vat):
    """The user's words, as they reach the tool: true / false / omitted."""
    if vat == INCLUDED:
        return {**arguments, "vat_included": True}
    if vat == NOT_INCLUDED:
        return {**arguments, "vat_included": False}
    return dict(arguments)


def _created_id(is_error, text):
    assert not is_error, f"tool refused instead of creating a document: {text}"
    return json.loads(text)["internal_morning_id"]


def _marker(label):
    return f"DENIDIN_071_{label}_{int(now_local().timestamp())}_{uuid.uuid4().hex[:6]}"


def _new_client_name(morning_client, label):
    _, client_name = seed_real_client(morning_client, _marker(label))
    return client_name


def _summary(stored):
    out = {k: stored.get(k) for k in ("type", "vatType", "vat", "amount", "amountExcludeVat")}
    out["rows"] = [{k: r.get(k) for k in ("vatType", "vat", "price")} for r in (stored.get("income") or [])]
    out["payment"] = [p.get("price") for p in (stored.get("payment") or [])]
    return out


def _assert_stored(stored, expected):
    total, vat, net = expected
    s = _summary(stored)
    assert abs(stored.get("amount") or 0) == pytest.approx(total), f"wrong total (expected {expected}): {s}"
    assert abs(stored.get("vat") or 0) == pytest.approx(vat), f"wrong VAT (expected {expected}): {s}"
    assert abs(stored.get("amountExcludeVat") or 0) == pytest.approx(net), f"wrong net (expected {expected}): {s}"


def _assert_paid(stored, amount):
    s = _summary(stored)
    paid = sum(float(p.get("price") or 0) for p in (stored.get("payment") or []))
    assert paid == pytest.approx(amount), f"payment line is {paid}, expected {amount}: {s}"


def _assert_receipt(stored, amount):
    """A receipt records the money and carries no VAT of its own."""
    s = _summary(stored)
    assert stored.get("amount") == pytest.approx(amount), f"wrong receipt total: {s}"
    assert not stored.get("vat"), f"a receipt must not carry VAT: {s}"
    _assert_paid(stored, amount)


def _assert_refused_nothing_created(morning_client, client_name, is_error, text):
    assert is_error, f"expected a refusal, but the tool succeeded: {text}"
    # Positive absence: give the sandbox's lagging search index time to show
    # anything that was created anyway.
    for _ in range(4):
        found = morning_client.list_invoices({"clientName": client_name})
        items = found if isinstance(found, list) else (found.get("items") or [])
        assert not items, f"refused, but documents exist anyway: {items}"
        time.sleep(1.5)


def _assert_refused_original_untouched(morning_client, original_id, is_error, text):
    assert is_error, f"expected a refusal, but the tool succeeded: {text}"
    linked = morning_client.get_invoice(original_id).get("linkedDocuments") or []
    assert not linked, f"refused, but a document was linked to the original anyway: {linked}"


def _assert_is_our_vat_conflict(is_error, text):
    """The refusal must be the app's own VAT-conflict error - never Morning
    rejecting the payload after it was sent (e.g. errorCode 2422)."""
    assert is_error, f"expected a VAT-conflict refusal, but the tool succeeded: {text}"
    expected = getattr(errors, "VAT_CONFLICT", None)
    assert expected is not None and text == expected, (
        f"refused, but not by the app's own VAT-conflict error: {text}"
    )


def _assert_conflict_nothing_created(morning_client, client_name, is_error, text):
    _assert_is_our_vat_conflict(is_error, text)
    _assert_refused_nothing_created(morning_client, client_name, is_error, text)


def _assert_conflict_original_untouched(morning_client, original_id, is_error, text):
    _assert_is_our_vat_conflict(is_error, text)
    _assert_refused_original_untouched(morning_client, original_id, is_error, text)


# --- seeding originals through the real tools (the production path) ------
def _seed_305(morning_client, server_url, label, vat):
    return _created_id(*_call_tool(server_url, "create_invoice", _with_vat({
        "client_name": _new_client_name(morning_client, label),
        "amount": X,
        "description": f"bugfix-071 seed 305 {label}",
        "name_resolved": True,
    }, vat)))


def _seed_300(morning_client, server_url, label, vat):
    return _created_id(*_call_tool(server_url, "create_transaction_account", _with_vat({
        "client_name": _new_client_name(morning_client, label),
        "amount": X,
        "description": f"bugfix-071 seed 300 {label}",
        "name_resolved": True,
    }, vat)))


def _seed_320(morning_client, server_url, label):
    return _created_id(*_call_tool(server_url, "create_combo_document", {
        "client_name": _new_client_name(morning_client, label),
        "amount": X,
        "description": f"bugfix-071 seed 320 {label}",
        "payment_date": PAYMENT_DATE,
        "name_resolved": True,
    }))


def _seed_exempt_305(morning_client, label):
    """An exempt 305 exactly as the production bug stored the 37 documents
    (document vatType 1). No tool can produce this shape once fixed, so it
    is seeded with a raw payload, deliberately bypassing every tool."""
    client_id, _ = seed_real_client(morning_client, _marker(label))
    payload = {
        "type": 305, "date": date.today().isoformat(), "lang": "he", "vatType": 1,
        "currency": "ILS", "rounding": False, "signed": True,
        "description": f"bugfix-071 seed exempt 305 {label}",
        "client": {"self": False, "id": client_id},
        "income": [{"catalogNum": "", "description": f"bugfix-071 seed exempt 305 {label}",
                    "quantity": 1, "price": X, "currency": "ILS", "currencyRate": 1, "vatType": 1}],
    }
    doc_id = str(morning_client.create_invoice(payload)["id"])
    _assert_stored(morning_client.get_invoice(doc_id), EXEMPT_100)  # the seed itself must be exempt
    return doc_id


# ================================================================ 305 / 300
@pytest.mark.parametrize("tool, doc_type", [
    ("create_invoice", 305),
    ("create_transaction_account", 300),
])
@pytest.mark.parametrize("vat, expected", [
    (INCLUDED, X_INCLUDED),
    (NOT_INCLUDED, X_PLUS_VAT),
])
def test_305_300_explicit_vat(morning_client, server_url, tool, doc_type, vat, expected):
    """305/300: "included" -> total X, VAT inside; "not included" -> X + VAT."""
    doc_id = _created_id(*_call_tool(server_url, tool, _with_vat({
        "client_name": _new_client_name(morning_client, f"{doc_type}_{vat}"),
        "amount": X,
        "description": f"bugfix-071 {doc_type} {vat}",
        "name_resolved": True,
    }, vat)))
    _assert_stored(morning_client.get_invoice(doc_id), expected)


@pytest.mark.parametrize("tool, doc_type", [
    ("create_invoice", 305),
    ("create_transaction_account", 300),
])
def test_305_300_vat_not_stated_is_refused(morning_client, server_url, tool, doc_type):
    """305/300: the user said nothing about VAT -> refuse, ask, create nothing."""
    client_name = _new_client_name(morning_client, f"{doc_type}_nothing")
    is_error, text = _call_tool(server_url, tool, {
        "client_name": client_name,
        "amount": X,
        "description": f"bugfix-071 {doc_type} nothing",
        "name_resolved": True,
    })
    _assert_refused_nothing_created(morning_client, client_name, is_error, text)


# ========================================================== 320 standalone
@pytest.mark.parametrize("vat", [NOTHING, INCLUDED])
def test_320_standalone_amount_paid_has_vat_inside(morning_client, server_url, vat):
    """320 standalone: X paid -> total X = payment X, VAT inside. An explicit
    "included" is consistent with that and ignored."""
    doc_id = _created_id(*_call_tool(server_url, "create_combo_document", _with_vat({
        "client_name": _new_client_name(morning_client, f"320_{vat}"),
        "amount": X,
        "description": f"bugfix-071 320 {vat}",
        "payment_date": PAYMENT_DATE,
        "name_resolved": True,
    }, vat)))
    stored = morning_client.get_invoice(doc_id)
    _assert_stored(stored, X_INCLUDED)
    _assert_paid(stored, X)


def test_320_standalone_vat_not_included_is_a_conflict(morning_client, server_url):
    client_name = _new_client_name(morning_client, "320_not_included")
    is_error, text = _call_tool(server_url, "create_combo_document", _with_vat({
        "client_name": client_name,
        "amount": X,
        "description": "bugfix-071 320 not included",
        "payment_date": PAYMENT_DATE,
        "name_resolved": True,
    }, NOT_INCLUDED))
    _assert_conflict_nothing_created(morning_client, client_name, is_error, text)


# ======================================================= 320 closing a 300
@pytest.mark.parametrize("vat, seed_vat, expected, paid", [
    # full close: the amount paid is the 300's total, VAT inside
    (NOTHING, INCLUDED, X_INCLUDED, 100.0),
    (NOTHING, NOT_INCLUDED, X_PLUS_VAT, 118.0),
    # explicit "included" is consistent and ignored - even on a 300 created as "not included"
    (INCLUDED, NOT_INCLUDED, X_PLUS_VAT, 118.0),
])
def test_320_closing_a_300(morning_client, server_url, vat, seed_vat, expected, paid):
    original_id = _seed_300(morning_client, server_url, f"320REF_{vat}_{seed_vat}", seed_vat)
    arguments = {"original_internal_morning_id": original_id, "payment_date": PAYMENT_DATE}
    doc_id = _created_id(*_call_tool(server_url, "create_combo_document_as_reference", _with_vat(arguments, vat)))
    stored = morning_client.get_invoice(doc_id)
    _assert_stored(stored, expected)
    _assert_paid(stored, paid)


def test_320_closing_a_300_vat_not_included_is_a_conflict(morning_client, server_url):
    original_id = _seed_300(morning_client, server_url, "320REF_not_included", INCLUDED)
    is_error, text = _call_tool(server_url, "create_combo_document_as_reference", _with_vat({
        "original_internal_morning_id": original_id,
        "payment_date": PAYMENT_DATE,
    }, NOT_INCLUDED))
    _assert_conflict_original_untouched(morning_client, original_id, is_error, text)


# ========================================================== 400 standalone
@pytest.mark.parametrize("vat", [NOTHING, INCLUDED])
def test_400_standalone_records_the_amount(morning_client, server_url, vat):
    doc_id = _created_id(*_call_tool(server_url, "create_receipt", _with_vat({
        "client_name": _new_client_name(morning_client, f"400_{vat}"),
        "amount": X,
        "description": f"פיקדון bugfix-071 {vat}",
        "payment_date": PAYMENT_DATE,
        "name_resolved": True,
    }, vat)))
    _assert_receipt(morning_client.get_invoice(doc_id), X)


def test_400_standalone_vat_not_included_is_a_conflict(morning_client, server_url):
    client_name = _new_client_name(morning_client, "400_not_included")
    is_error, text = _call_tool(server_url, "create_receipt", _with_vat({
        "client_name": client_name,
        "amount": X,
        "description": "פיקדון bugfix-071 not included",
        "payment_date": PAYMENT_DATE,
        "name_resolved": True,
    }, NOT_INCLUDED))
    _assert_conflict_nothing_created(morning_client, client_name, is_error, text)


# ======================================================== 400 against a 305
@pytest.mark.parametrize("vat", [
    NOTHING,   # full: the 305's total
    INCLUDED,  # explicit "included" - consistent, ignored
])
def test_400_against_a_305(morning_client, server_url, vat):
    original_id = _seed_305(morning_client, server_url, f"400REF_{vat}", INCLUDED)
    arguments = {"original_internal_morning_id": original_id, "payment_date": PAYMENT_DATE}
    expected = X
    doc_id = _created_id(*_call_tool(server_url, "create_receipt", _with_vat(arguments, vat)))
    _assert_receipt(morning_client.get_invoice(doc_id), expected)


def test_400_against_a_305_vat_not_included_is_a_conflict(morning_client, server_url):
    original_id = _seed_305(morning_client, server_url, "400REF_not_included", INCLUDED)
    is_error, text = _call_tool(server_url, "create_receipt", _with_vat({
        "original_internal_morning_id": original_id,
        "payment_date": PAYMENT_DATE,
    }, NOT_INCLUDED))
    _assert_conflict_original_untouched(morning_client, original_id, is_error, text)


# ============================================ 330 against a taxable original
@pytest.mark.parametrize("original, vat", [
    ("305", NOTHING),   # mirrors the original
    ("305", INCLUDED),  # explicit "included" - consistent, ignored
    ("320", NOTHING),   # a 320 can be credited too
])
def test_330_against_a_taxable_original(morning_client, server_url, original, vat):
    if original == "305":
        original_id = _seed_305(morning_client, server_url, f"330_305_{vat}", INCLUDED)
    else:
        original_id = _seed_320(morning_client, server_url, f"330_320_{vat}")
    arguments = {"original_internal_morning_id": original_id}
    doc_id = _created_id(*_call_tool(server_url, "create_credit_note", _with_vat(arguments, vat)))
    _assert_stored(morning_client.get_invoice(doc_id), X_INCLUDED)


def test_330_against_a_taxable_original_vat_not_included_is_a_conflict(morning_client, server_url):
    original_id = _seed_305(morning_client, server_url, "330_not_included", INCLUDED)
    is_error, text = _call_tool(server_url, "create_credit_note", _with_vat({
        "original_internal_morning_id": original_id,
    }, NOT_INCLUDED))
    _assert_conflict_original_untouched(morning_client, original_id, is_error, text)


# ============================================ 330 against an exempt original
def test_330_against_an_exempt_original_mirrors_it(morning_client, server_url):
    """The 37 production documents: a credit note against an exempt original
    must itself be exempt - it reverses exactly what was booked."""
    original_id = _seed_exempt_305(morning_client, "330EX_mirror")
    doc_id = _created_id(*_call_tool(server_url, "create_credit_note", {
        "original_internal_morning_id": original_id,
    }))
    _assert_stored(morning_client.get_invoice(doc_id), EXEMPT_100)


@pytest.mark.parametrize("vat", [INCLUDED, NOT_INCLUDED])
def test_330_against_an_exempt_original_any_vat_statement_is_a_conflict(morning_client, server_url, vat):
    original_id = _seed_exempt_305(morning_client, f"330EX_{vat}")
    is_error, text = _call_tool(server_url, "create_credit_note", _with_vat({
        "original_internal_morning_id": original_id,
    }, vat))
    _assert_conflict_original_untouched(morning_client, original_id, is_error, text)
