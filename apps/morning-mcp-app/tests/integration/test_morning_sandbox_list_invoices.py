import json
from pathlib import Path

import pytest

from denidin_mcp_morning.morning_client import MorningClient

APP_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = APP_ROOT / "config" / "config.test.json"


def _load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def test_list_invoices_sandbox():
    """Integration test: list invoices from Morning sandbox.

    IMPORTANT:
    - This test uses the sandbox environment only.
    - No non-read calls are made.
    - No mocking. Provide a real sandbox API key id/secret in `config/config.test.json`.
    """
    cfg = _load_config()
    # For tests, require `api_key_id` and `api_key_secret` (exact two fields).
    morning_cfg = cfg if isinstance(cfg, dict) else {}
    api_key_id = morning_cfg.get("api_key_id")
    api_key_secret = morning_cfg.get("api_key_secret")
    if not (api_key_id and api_key_secret):
        pytest.skip(
            "No `api_key_id`/`api_key_secret` in `config.test.json`. Set sandbox API key id+secret to run this test."
        )

    # Basic safety: skip if keys look like placeholders
    if api_key_id.startswith("PASTE_") or api_key_secret.startswith("PASTE_"):
        pytest.skip("`api_key_id`/`api_key_secret` look like placeholders. Provide real sandbox credentials to run this test.")

    base_url = morning_cfg.get("api_url", "https://sandbox.d.greeninvoice.co.il/api/v1/")
    # MorningClient accepts api_key_id and api_key_secret and will exchange them for a JWT.
    client = MorningClient(api_key_id=api_key_id, api_key_secret=api_key_secret, base_url=base_url)

    # This is a read-only call; it may return an empty list/dict which is acceptable.
    resp = client.list_invoices(params={})

    assert isinstance(resp, (dict, list)), "Expected JSON response (dict or list)"
