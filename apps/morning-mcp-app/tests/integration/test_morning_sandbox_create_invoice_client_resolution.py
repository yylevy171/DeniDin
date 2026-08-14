"""Real Morning-sandbox tests for create_invoice's exact-only client
resolution gate (client-name-resolution architecture fix, bugfix-028
sub-piece, 2026-08-12 - representative of the same gate shared by
create_transaction_account/create_combo_document/update_client/
get_client_details/list_invoices).

No mocks: drives denidin_mcp_morning.tools.create_invoice against the live
sandbox and independently verifies the created document's real client.id
via a direct MorningClient.get_invoice call - the tool's own reply text is
never trusted as proof (REQ-INV-009).

Non-exact/ambiguous client-name resolution is no longer this tool's own
concern (that moved entirely to `resolve_client_name` - see
test_morning_sandbox_resolve_client_name_tool.py, including the T1/T2
production-incident-shaped regression cases). This file covers only what's
still create_invoice's own job: accepting an exact match, and refusing
(procedurally, or via ClientNotFoundError) on anything else.

Per CONSTITUTION §V and this app's testing policy (spec.md §Testing Strategy).
"""
from pathlib import Path

import pytest

from denidin_mcp_morning.config import load_config
from denidin_mcp_morning.morning_client import MorningClient
from denidin_mcp_morning.tools import ClientNameNotResolvedError, ClientNotFoundError, create_invoice
from denidin_mcp_morning.utils.time_utils import now_local
from tests.integration._seed_helpers import seed_real_client

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
        auth_url=config.auth_url,
    )


def _extract_id(confirmation_text: str) -> str:
    return confirmation_text.split("מזהה פנימי (internal_morning_id): ")[1].splitlines()[0].strip()


def test_create_invoice_exact_match_attaches_to_the_real_client(morning_client):
    marker = f"DENIDIN_027_RESOLVE_EXACT_{int(now_local().timestamp())}"
    client_id, client_name = seed_real_client(morning_client, marker)

    confirmation = create_invoice(
        morning_client, client_name=client_name, amount=10.0, description=marker, name_resolved=True
    )
    internal_morning_id = _extract_id(confirmation)

    created = morning_client.get_invoice(internal_morning_id)
    assert created.get("client", {}).get("id") == client_id
    assert "מצאתי" not in confirmation  # exact match - no disclosure needed


def test_create_invoice_not_resolved_refuses_without_any_lookup(morning_client):
    """Architecture fix (2026-08-12): omitting name_resolved must refuse
    immediately, without attempting any Morning lookup at all - even for a
    name that would otherwise resolve cleanly, and creates nothing.
    Follow-up (2026-08-12): this is now a real raise, not ordinary refusal
    text - two outcomes only, succeed or raise."""
    marker = f"DENIDIN_027_NOTRESOLVED_{int(now_local().timestamp())}"
    _, client_name = seed_real_client(morning_client, marker)

    with pytest.raises(ClientNameNotResolvedError) as exc_info:
        create_invoice(morning_client, client_name=client_name, amount=10.0, description=marker)

    assert "resolve_client_name" in str(exc_info.value)


def test_create_invoice_zero_matches_raises_and_creates_nothing(morning_client):
    """bugfix-028 B4(c): a client that cannot be found is a FAILURE, not a
    friendly string returned as ordinary output with error=None - that is
    what let one production document be approved eight times and created
    zero times. Requires name_resolved=True (architecture fix, 2026-08-12) -
    the caller must have already gone through resolve_client_name."""
    marker = f"DENIDIN_027_RESOLVE_NOTFOUND_{int(now_local().timestamp())}"
    nonexistent_name = f"Test Client {marker}"  # deliberately never seeded

    with pytest.raises(ClientNotFoundError) as exc_info:
        create_invoice(
            morning_client, client_name=nonexistent_name, amount=12.0, description=marker, name_resolved=True
        )

    assert "לא נמצא" in str(exc_info.value)
    assert "מזהה פנימי" not in str(exc_info.value)  # no document confirmation shape at all


def test_create_invoice_non_exact_match_with_name_resolved_raises_not_found(morning_client):
    """Architecture fix (2026-08-12): a non-exact match (a real client
    exists, but the name given isn't its literal stored spelling) is no
    longer a "did you mean X?" disclosure from create_invoice itself - that
    disclosure now lives entirely in resolve_client_name. Asserting
    name_resolved=True against a name that's still non-exact is a contract
    violation and raises ClientNotFoundError; nothing is created."""
    marker = f"DENIDIN_027_RESOLVE_FUZZY_{int(now_local().timestamp())}"
    real_name = f"Test Client {marker} International"
    seed_real_client(morning_client, marker, name=real_name)

    # Query by a prefix, not the full stored name - forces a non-exact match.
    with pytest.raises(ClientNotFoundError):
        create_invoice(
            morning_client, client_name=f"Test Client {marker}", amount=11.0, description=marker,
            name_resolved=True,
        )


def test_create_invoice_ambiguous_match_with_name_resolved_raises_not_found(morning_client):
    """Architecture fix (2026-08-12): create_invoice no longer discloses
    ambiguous candidates itself - that's resolve_client_name's job now.
    Asserting name_resolved=True against a name that's still ambiguous is a
    contract violation and raises ClientNotFoundError; nothing is created."""
    marker = f"DENIDIN_027_RESOLVE_AMBIG_{int(now_local().timestamp())}"
    seed_real_client(morning_client, marker, name=f"Test Client {marker} Alpha")
    seed_real_client(morning_client, f"{marker}_B", name=f"Test Client {marker} Beta")

    with pytest.raises(ClientNotFoundError):
        create_invoice(
            morning_client, client_name=f"Test Client {marker}", amount=13.0, description=marker,
            name_resolved=True,
        )
