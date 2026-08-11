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


def test_create_invoice_non_exact_match_asks_for_confirmation_and_creates_nothing(morning_client):
    """bugfix-039 (expanded 2026-08-11): a non-exact single match must
    refuse with a closed yes/no confirmation question and create NOTHING -
    never silently create-then-disclose, since by the time a disclosure is
    shown the real Morning document already exists under a possibly-wrong
    client, too late for the user to catch a bad guess."""
    marker = f"DENIDIN_027_RESOLVE_FUZZY_{int(datetime.now(timezone.utc).timestamp())}"
    real_name = f"Test Client {marker} International"
    seed_real_client(morning_client, marker, name=real_name)

    # Query by a prefix, not the full stored name - forces a non-exact match.
    result = create_invoice(morning_client, client_name=f"Test Client {marker}", amount=11.0, description=marker)

    assert "מזהה פנימי" not in result  # no document confirmation shape at all - nothing created
    assert real_name in result  # names the real candidate so the user can confirm
    assert "כן" in result and "לא" in result  # closed yes/no question, not open-ended


def test_create_invoice_confirmed_non_exact_match_then_creates_with_exact_name(morning_client):
    """The intended follow-up half of the flow above: once the model
    re-invokes create_invoice with the now-confirmed EXACT real name (what
    a "כן" reply to the confirmation question leads to), the document is
    created normally, attached to the real client."""
    marker = f"DENIDIN_027_RESOLVE_FUZZY_CONFIRMED_{int(datetime.now(timezone.utc).timestamp())}"
    real_name = f"Test Client {marker} International"
    client_id, _ = seed_real_client(morning_client, marker, name=real_name)

    confirmation = create_invoice(morning_client, client_name=real_name, amount=11.0, description=marker)
    invoice_id = _extract_id(confirmation)

    created = morning_client.get_invoice(invoice_id)
    assert created.get("client", {}).get("id") == client_id
    assert "כן" not in confirmation.split("\n")[0]  # no leftover confirmation-question phrasing


def test_create_invoice_single_letter_added_to_stored_name_asks_for_confirmation(morning_client):
    """T1 (user-specified regression case, 2026-08-11): the STORED client's
    surname is missing a trailing letter relative to what's typed - the
    mirror direction of T2 below, and the one Morning's native prefix search
    cannot cover on its own (a longer query can never be a prefix of a
    shorter stored word) - this is exactly what _search_word_with_truncation
    closes. The uniqueness marker sits in the UNEDITED first-name word so
    the single-letter-edit relationship on the surname stays clean
    (stored "צור" vs typed "צורן" - one letter added at the end, not the
    first letter)."""
    marker = f"DENIDIN_039_T1_{int(datetime.now(timezone.utc).timestamp())}"
    real_name = f"זהבית{marker} צור"
    typed_name = f"זהבית{marker} צורן"
    seed_real_client(morning_client, marker, name=real_name)

    result = create_invoice(morning_client, client_name=typed_name, amount=14.0, description=marker)

    assert "מזהה פנימי" not in result  # nothing created
    assert real_name in result  # names the real candidate
    assert "כן" in result and "לא" in result


def test_create_invoice_single_letter_removed_from_stored_name_asks_for_confirmation(morning_client):
    """T2 (user-specified regression case, 2026-08-11): the STORED client's
    first name has one extra trailing letter relative to what's typed - the
    exact production incident shape (stored "דודי" vs typed "דוד"). Already
    coverable by Morning's native whole-string prefix search alone (typed is
    a literal prefix of stored) - kept as its own explicit regression test
    per the user's request, not just folded into the general FUZZY test
    above. Marker sits in the UNEDITED surname."""
    marker = f"DENIDIN_039_T2_{int(datetime.now(timezone.utc).timestamp())}"
    real_name = f"אדלר{marker} דודי"
    typed_name = f"אדלר{marker} דוד"
    seed_real_client(morning_client, marker, name=real_name)

    result = create_invoice(morning_client, client_name=typed_name, amount=15.0, description=marker)

    assert "מזהה פנימי" not in result  # nothing created
    assert real_name in result  # names the real candidate
    assert "כן" in result and "לא" in result


def test_create_invoice_zero_matches_raises_and_creates_nothing(morning_client):
    """bugfix-028 B4(c) - CHANGED 2026-08-09: this asserted the refusal was
    RETURNED as ordinary output. Returning it is the defect - with `error=None`
    it was indistinguishable from success to every layer above, which is how one
    ₪40,000 document was approved eight times and created zero times. Feature
    027's requirement that nothing be created is unchanged and still asserted.
    """
    import pytest as _pytest
    from denidin_mcp_morning.tools import ClientNotFoundError

    marker = f"DENIDIN_027_RESOLVE_NOTFOUND_{int(datetime.now(timezone.utc).timestamp())}"
    nonexistent_name = f"Test Client {marker}"  # deliberately never seeded

    with _pytest.raises(ClientNotFoundError) as exc_info:
        create_invoice(morning_client, client_name=nonexistent_name, amount=12.0, description=marker)

    assert "לא נמצא" in str(exc_info.value)
    assert "מזהה פנימי" not in str(exc_info.value)  # no document confirmation shape at all


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
