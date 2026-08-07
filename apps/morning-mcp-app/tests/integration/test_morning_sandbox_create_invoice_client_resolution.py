"""Real Morning-sandbox tests for feature 027's Group A client resolution
(create_invoice as the representative tool - REQ-INV-001/002/003/005/009/011).

No mocks: drives denidin_mcp_morning.tools.create_invoice against the live
sandbox and independently verifies the created document's real client.id
via a direct MorningClient.get_invoice call - the tool's own reply text is
never trusted as proof (REQ-INV-009).

Per CONSTITUTION §V and this app's testing policy (spec.md §Testing Strategy).
"""
from datetime import datetime, timezone
from pathlib import Path

import pytest

from denidin_mcp_morning.config import load_config
from denidin_mcp_morning.morning_client import MorningClient
from denidin_mcp_morning.tools import create_invoice
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
    )


def _extract_id(confirmation_text: str) -> str:
    return confirmation_text.split("מזהה פנימי (invoice_id): ")[1].splitlines()[0].strip()


def test_create_invoice_exact_match_attaches_to_the_real_client(morning_client):
    marker = f"DENIDIN_027_RESOLVE_EXACT_{int(datetime.now(timezone.utc).timestamp())}"
    client_id, client_name = seed_real_client(morning_client, marker)

    confirmation = create_invoice(morning_client, client_name=client_name, amount=10.0, description=marker)
    invoice_id = _extract_id(confirmation)

    created = morning_client.get_invoice(invoice_id)
    assert created.get("client", {}).get("id") == client_id
    assert "מצאתי" not in confirmation  # exact match - no disclosure needed


def test_create_invoice_non_exact_match_discloses_and_attaches_to_the_real_client(morning_client):
    marker = f"DENIDIN_027_RESOLVE_FUZZY_{int(datetime.now(timezone.utc).timestamp())}"
    real_name = f"Test Client {marker} International"
    client_id, _ = seed_real_client(morning_client, marker, name=real_name)

    # Query by a prefix, not the full stored name - forces a non-exact match.
    confirmation = create_invoice(
        morning_client, client_name=f"Test Client {marker}", amount=11.0, description=marker
    )
    invoice_id = _extract_id(confirmation)

    created = morning_client.get_invoice(invoice_id)
    assert created.get("client", {}).get("id") == client_id
    assert real_name in confirmation  # disclosed the real matched name


def test_create_invoice_zero_matches_refuses_and_creates_nothing(morning_client):
    marker = f"DENIDIN_027_RESOLVE_NOTFOUND_{int(datetime.now(timezone.utc).timestamp())}"
    nonexistent_name = f"Test Client {marker}"  # deliberately never seeded

    result = create_invoice(morning_client, client_name=nonexistent_name, amount=12.0, description=marker)

    assert "לא נמצא" in result
    assert "מזהה פנימי" not in result  # no document confirmation shape at all


def test_create_invoice_ambiguous_match_refuses_and_lists_real_candidates(morning_client):
    marker = f"DENIDIN_027_RESOLVE_AMBIG_{int(datetime.now(timezone.utc).timestamp())}"
    _, name_a = seed_real_client(morning_client, marker, name=f"Test Client {marker} Alpha")
    _, name_b = seed_real_client(morning_client, f"{marker}_B", name=f"Test Client {marker} Beta")

    result = create_invoice(
        morning_client, client_name=f"Test Client {marker}", amount=13.0, description=marker
    )

    assert "מזהה פנימי" not in result  # no document confirmation shape at all
    assert name_a in result
    assert name_b in result
