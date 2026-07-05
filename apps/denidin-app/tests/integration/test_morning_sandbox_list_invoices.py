import json
from pathlib import Path

import pytest

# Ensure repository root is on sys.path so `src.*` packages import correctly when running tests
import sys
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import importlib

# Import by package name to allow relative imports inside the package (auth.py)
mc_mod = importlib.import_module("src.denidin_mcp_morning.morning_client")
MorningClient = mc_mod.MorningClient


# Prefer repository-level config (`config/config.test.json`) if present, otherwise
# fall back to the original location under `denidin-app/config/config.test.json`.
CONFIG_PATH = ROOT / "denidin-app" / "config" / "config.test.json"


def _load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def test_list_invoices_sandbox():
    """Integration test: list invoices from Morning sandbox.

    IMPORTANT:
    - This test uses the sandbox environment only.
    - No non-read calls are made.
    - No mocking. Provide a real sandbox API token in `denidin-app/config/config.test.json` under `green_api_token`.
    """
    cfg = _load_config()
    # For tests, require `morning.api_key_id` and `morning.api_key_secret` (exact two fields).
    morning_cfg = cfg.get("morning", {}) if isinstance(cfg, dict) else {}
    api_key_id = morning_cfg.get("api_key_id")
    api_key_secret = morning_cfg.get("api_key_secret")
    if not (api_key_id and api_key_secret):
        pytest.skip(
            "No `morning.api_key_id`/`morning.api_key_secret` in `config.test.json`. Set sandbox API key id+secret to run this test."
        )

    # Basic safety: skip if keys look like placeholders
    if api_key_id.startswith("PASTE_") or api_key_secret.startswith("PASTE_"):
        pytest.skip("`morning.api_key_id`/`morning.api_key_secret` look like placeholders. Provide real sandbox credentials to run this test.")

    base_url = morning_cfg.get("api_url", "https://sandbox.d.greeninvoice.co.il/api/v1/")
    # MorningClient accepts api_key_id and api_key_secret and will exchange them for a JWT.
    client = MorningClient(api_key_id=api_key_id, api_key_secret=api_key_secret, base_url=base_url)

    # This is a read-only call; it may return an empty list/dict which is acceptable.
    resp = client.list_invoices(params={})

    assert isinstance(resp, (dict, list)), "Expected JSON response (dict or list)"
