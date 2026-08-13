"""Real Morning-sandbox test for the OAuth2 client_credentials auth flow
(feature 053) - no mocks, per CONSTITUTION §V and this app's testing policy.

Proves the full real round-trip already manually verified during this
feature's research: a real POST to https://api.sandbox.morning.dev/idp/v1/
oauth/token succeeds with the existing test/dev sandbox credentials, and the
resulting access token actually works for a real API call against the main
API host (a different host entirely - see auth.py's docstring).
"""
import json
from pathlib import Path

import pytest

from denidin_mcp_morning.config import load_config
from denidin_mcp_morning.morning_client import MorningClient

APP_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = APP_ROOT / "config" / "config.test.json"


@pytest.fixture(scope="module")
def config():
    if not CONFIG_PATH.exists():
        pytest.skip("config/config.test.json not found")
    cfg = load_config(CONFIG_PATH)
    if not (cfg.api_key_id and cfg.api_key_secret):
        pytest.skip("No api_key_id/api_key_secret in config.test.json")
    return cfg


def test_real_oauth2_token_request_succeeds(config):
    """Step 1 of the real flow: a real client_credentials request against the
    real sandbox token host succeeds and returns a well-shaped token."""
    from denidin_mcp_morning.auth import MorningAuth

    auth = MorningAuth(
        api_key_id=config.api_key_id,
        api_key_secret=config.api_key_secret,
        auth_url=config.auth_url,
    )

    token = auth.get_token()

    assert isinstance(token, str)
    assert len(token) > 20  # a real JWT, not a placeholder
    assert auth._token_expiry > 0  # a real expiry timestamp was captured


def test_real_token_works_for_a_real_api_call(config):
    """Step 2: the token obtained from the NEW auth host actually works
    against the (different) main API host - proves the two hosts are
    correctly wired together, not just independently reachable."""
    client = MorningClient(
        api_key_id=config.api_key_id,
        api_key_secret=config.api_key_secret,
        base_url=config.api_url,
        auth_url=config.auth_url,
    )

    result = client.list_invoices(params={})

    assert isinstance(result, dict)
    # A real sandbox with real prior test data should have at least one document.
    items = result.get("items") if isinstance(result.get("items"), list) else None
    assert result.get("total", 0) > 0 or (items and len(items) > 0), (
        f"expected real data back from the sandbox, got: {json.dumps(result)[:300]}"
    )


def test_token_is_cached_across_multiple_real_calls(config):
    """A second real API call within the token's lifetime must reuse the
    cached token, not make a second real auth request."""
    from denidin_mcp_morning.auth import MorningAuth

    auth = MorningAuth(
        api_key_id=config.api_key_id,
        api_key_secret=config.api_key_secret,
        auth_url=config.auth_url,
    )

    first_token = auth.get_token()
    second_token = auth.get_token()

    assert first_token == second_token
