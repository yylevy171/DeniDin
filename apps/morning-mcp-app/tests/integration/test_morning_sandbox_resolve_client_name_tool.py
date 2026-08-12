"""Real Morning-sandbox test for the resolve_client_name MCP tool
(client-name-resolution architecture fix, bugfix-028 sub-piece, 2026-08-12).

No mocks: drives denidin_mcp_morning.tools.resolve_client_name against the
live sandbox, per CONSTITUTION §V and this app's testing policy.
"""
import time
from pathlib import Path

import pytest

from denidin_mcp_morning.config import load_config
from denidin_mcp_morning.morning_client import MorningClient
from denidin_mcp_morning.utils.time_utils import now_local
from tests.integration._seed_helpers import seed_real_client

APP_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = APP_ROOT / "config" / "config.test.json"

# Search-index eventual-consistency lag (research.md Decision 8) - poll up to
# 12x/1.5s (18s) before giving up, same pattern as the other sandbox tests.
_POLL_ATTEMPTS = 12
_POLL_INTERVAL_SECONDS = 1.5


def _poll_until(predicate, action):
    result = None
    for _ in range(_POLL_ATTEMPTS):
        result = action()
        if predicate(result):
            return result
        time.sleep(_POLL_INTERVAL_SECONDS)
    return result


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


def _unique_marker(prefix: str) -> str:
    return f"{prefix}_{int(now_local().timestamp())}"


def test_resolve_client_name_exact_match_discloses_the_stored_name(morning_client):
    """Polls for the EXACT-match message shape specifically (starts with
    "שם הלקוח המדויק"), not just "name appears somewhere in the reply" - a
    naive substring check can't distinguish an exact match from a "did you
    mean" confirmation question, since both legitimately contain the client's
    name. A real run right after add_client can transiently observe a
    non-exact/discovery-only response before Morning's search index settles
    (this file's own documented eventual-consistency lag) - retrying is the
    correct response to that, not accepting whatever comes back first."""
    from denidin_mcp_morning.tools import add_client, resolve_client_name

    marker = _unique_marker("DENIDIN_RESOLVE_EXACT_TEST")
    name = f"Test Client {marker}"

    add_client(morning_client, name=name, email=f"{marker}@example.com", phone="050-1234567")

    result = _poll_until(
        lambda r: r.startswith("שם הלקוח המדויק"), lambda: resolve_client_name(morning_client, name)
    )

    assert name in result
    assert "כן" not in result and "לא" not in result  # not a confirmation question


def test_resolve_client_name_never_includes_raw_client_id(morning_client):
    from denidin_mcp_morning.tools import add_client, resolve_client_name

    marker = _unique_marker("DENIDIN_RESOLVE_ID_TEST")
    name = f"Test Client {marker}"

    add_client(morning_client, name=name, email=f"{marker}@example.com", phone="050-1234567")

    items = _poll_until(
        lambda items: bool(items),
        lambda: (morning_client.search_clients({"name": name}).get("items") or []),
    )
    assert items, "expected the just-created client to be found via search_clients"
    client_id = items[0]["id"]

    result = resolve_client_name(morning_client, name)

    assert client_id not in result


def test_resolve_client_name_non_exact_single_match_asks_for_confirmation(morning_client):
    from denidin_mcp_morning.tools import add_client, resolve_client_name

    marker = _unique_marker("DENIDIN_RESOLVE_NONEXACT_TEST")
    real_name = f"Test Client International {marker}"
    typed_name = f"Test Client {marker}"  # a real prefix/partial reference, not the exact stored name

    add_client(morning_client, name=real_name, email=f"{marker}@example.com", phone="050-1234567")

    result = _poll_until(
        lambda r: real_name in r, lambda: resolve_client_name(morning_client, typed_name)
    )

    assert real_name in result
    assert "כן" in result and "לא" in result


def test_resolve_client_name_single_letter_added_to_stored_name_asks_for_confirmation(morning_client):
    """T1 (user-specified regression case, 2026-08-11; relocated here from
    create_invoice's own test file 2026-08-12, since resolution is no longer
    that tool's job): the STORED client's surname is missing a trailing
    letter relative to what's typed - the mirror direction of T2 below, and
    the one Morning's native prefix search cannot cover on its own (a longer
    query can never be a prefix of a shorter stored word). The uniqueness
    marker sits in the UNEDITED first-name word so the single-letter-edit
    relationship on the surname stays clean (stored "צור" vs typed "צורן" -
    one letter added at the end, not the first letter)."""
    from denidin_mcp_morning.tools import resolve_client_name

    marker = _unique_marker("DENIDIN_039_T1")
    real_name = f"זהבית{marker} צור"
    typed_name = f"זהבית{marker} צורן"
    seed_real_client(morning_client, marker, name=real_name)

    result = _poll_until(lambda r: real_name in r, lambda: resolve_client_name(morning_client, typed_name))

    assert real_name in result  # names the real candidate
    assert "כן" in result and "לא" in result


def test_resolve_client_name_single_letter_removed_from_stored_name_asks_for_confirmation(morning_client):
    """T2 (user-specified regression case, 2026-08-11; relocated here
    2026-08-12): the STORED client's first name has one extra trailing
    letter relative to what's typed - the exact production incident shape
    (stored "דודי" vs typed "דוד"). Already coverable by Morning's native
    whole-string prefix search alone (typed is a literal prefix of stored) -
    kept as its own explicit regression test per the user's original
    request, not just folded into the general non-exact-match test above.
    Marker sits in the UNEDITED surname."""
    from denidin_mcp_morning.tools import resolve_client_name

    marker = _unique_marker("DENIDIN_039_T2")
    real_name = f"אדלר{marker} דודי"
    typed_name = f"אדלר{marker} דוד"
    seed_real_client(morning_client, marker, name=real_name)

    result = _poll_until(lambda r: real_name in r, lambda: resolve_client_name(morning_client, typed_name))

    assert real_name in result  # names the real candidate
    assert "כן" in result and "לא" in result


def test_resolve_client_name_zero_matches_returns_a_not_found_string_never_raises(morning_client):
    """The query must share no word-prefix with anything this file's other
    tests seed ("Test"/"Client") - the discovery algorithm never
    relevance-filters candidates (resolve_client_by_name's own documented,
    intentional behavior), so even a short shared prefix can surface an
    unrelated real client as a "did you mean" candidate. Two deliberately
    unusual, mutually-unrelated words avoid any such collision."""
    from denidin_mcp_morning.tools import resolve_client_name

    marker = _unique_marker("Zzqxvrmplk_Wyfjhbtng")
    name = f"Zzqxvrmplk Wyfjhbtng {marker}"

    result = resolve_client_name(morning_client, name)

    assert isinstance(result, str)
    assert "לא נמצא" in result
