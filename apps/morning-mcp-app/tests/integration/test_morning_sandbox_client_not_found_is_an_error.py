"""bugfix-028 B4(c) — "client not found" must be an ERROR, not ordinary output.

Root cause approved 2026-08-09: a Group A document-creation tool whose client
can't be resolved returns `לא נמצא לקוח בשם הזה.` as a normal return value with
`error=None`, indistinguishable from success at every layer above it. In
production this let the same ₪40,000 document be approved eight times, created
zero times, with nothing anywhere reporting a failure.

The distinction that matters (user's framing of the three B4 causes): the tool
was asked to create a document and did not create one. That is a failure
whatever the reason, and it has to be typed as one so the layers above can see
it - `_call_with_error_boundary` in server.py maps a raised exception to a
friendly message AND marks the call as failed, which a plain `return` does not.

RED ON CURRENT CODE: all three tools return the friendly string instead of
raising, so `pytest.raises` sees nothing.

No mocking - the "not found" is real: a genuinely unused client name checked
against the real sandbox first.
"""
from datetime import datetime, timezone
from pathlib import Path

import pytest

from denidin_mcp_morning.config import load_config
from denidin_mcp_morning.morning_client import MorningClient
from denidin_mcp_morning.tools import (
    create_combo_document,
    create_invoice,
    create_transaction_account,
)

APP_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = APP_ROOT / "config" / "config.test.json"


@pytest.fixture(scope="module")
def morning_client():
    config = load_config(CONFIG_PATH)
    if not (config.api_key_id and config.api_key_secret):
        pytest.skip("No api_key_id/api_key_secret in config.test.json")
    return MorningClient(
        api_key_id=config.api_key_id,
        api_key_secret=config.api_key_secret,
        base_url=config.api_url,
    )


@pytest.fixture(scope="module")
def nonexistent_client_name(morning_client):
    """A name confirmed against the real sandbox to match zero clients."""
    name = f"לקוח שלא קיים DENIDIN_028_{int(datetime.now(timezone.utc).timestamp())}"
    found = morning_client.search_clients({"name": name}).get("items") or []
    assert not found, f"fixture precondition failed - {name!r} unexpectedly matched {found!r}"
    return name


def _assert_is_a_real_failure(exc):
    """The exception must be about the unresolvable client - not a TypeError from
    a signature that doesn't exist yet, which would let these pass for entirely
    the wrong reason."""
    assert not isinstance(exc, TypeError), f"signature mismatch, not the behaviour under test: {exc}"
    assert not isinstance(exc, AssertionError)


def test_create_invoice_raises_when_the_client_cannot_be_resolved(
    morning_client, nonexistent_client_name
):
    with pytest.raises(Exception) as exc_info:  # noqa: PT011 - the type IS the fix's choice
        create_invoice(
            morning_client,
            client_name=nonexistent_client_name,
            amount=47.0,
            description="bugfix-028 B4c",
        )
    _assert_is_a_real_failure(exc_info.value)


def test_create_transaction_account_raises_when_the_client_cannot_be_resolved(
    morning_client, nonexistent_client_name
):
    with pytest.raises(Exception) as exc_info:  # noqa: PT011
        create_transaction_account(
            morning_client,
            client_name=nonexistent_client_name,
            amount=47.0,
            description="bugfix-028 B4c",
            vat_included=True,
        )
    _assert_is_a_real_failure(exc_info.value)


def test_create_combo_document_raises_when_the_client_cannot_be_resolved(
    morning_client, nonexistent_client_name
):
    with pytest.raises(Exception) as exc_info:  # noqa: PT011
        create_combo_document(
            morning_client,
            client_name=nonexistent_client_name,
            amount=47.0,
            description="bugfix-028 B4c",
            vat_included=True,
            payment_date="2026-07-12",
        )
    _assert_is_a_real_failure(exc_info.value)


def test_a_decorated_client_name_is_still_resolvable(morning_client):
    """B4(a): Morning's search is a word-aligned PREFIX match of the whole stored
    name (live-probed 2026-08-09), so appending anything - a ח.פ, a phone -
    takes a name from 1 match to 0. The model appended the ח.פ it had learned
    from the client listing, and that composite is what failed in production.

    The tools must tolerate their own output being fed back to them: a name
    carrying the `(ח.פ …)` decoration this app itself printed must resolve to
    the same client the bare name resolves to.
    """
    from tests.integration._seed_helpers import seed_real_client
    from denidin_mcp_morning.tools import _resolve_client_for_document_creation

    marker = f"DENIDIN_028_B4A_{int(datetime.now(timezone.utc).timestamp())}"
    tax_id = "512345679"  # check-digit valid; Morning rejects invalid ones (errorCode 1111)
    _, client_name = seed_real_client(morning_client, marker)
    morning_client.update_client(
        _resolve_client_for_document_creation(morning_client, client_name).client_id,
        {"taxId": tax_id},
    )

    bare = _resolve_client_for_document_creation(morning_client, client_name)
    assert bare.client_id, f"precondition: the bare name must resolve - {bare.refusal_message!r}"

    decorated = _resolve_client_for_document_creation(
        morning_client, f"{client_name} (ח.פ {tax_id})"
    )
    assert decorated.client_id == bare.client_id, (
        f"the decorated name resolved to {decorated.client_id!r} "
        f"(refusal: {decorated.refusal_message!r}) instead of {bare.client_id!r} - "
        f"this app's own display label is not valid input to its own create tools"
    )
