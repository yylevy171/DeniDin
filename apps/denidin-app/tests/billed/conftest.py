"""Shared pytest fixtures for the Morning-MCP billed E2E test modules
(Feature 018 and successors) - `denidin_config`, `live_morning_tunnel`,
`denidin_app`.

Feature 038 (2026-08-04): moved here from the former single
test_denidin_morning_mcp_e2e.py (2094 lines, ~40 tests) when that file was
split by topic - human-approved reorganization (T012/T013), no fixture
logic changed, only location. pytest auto-discovers fixtures defined in a
directory's conftest.py for every test module in that directory, so none of
the split test modules (test_denidin_morning_invoice_creation_e2e.py,
test_denidin_morning_client_management_e2e.py,
test_denidin_morning_list_invoices_e2e.py,
test_denidin_morning_invoice_lifecycle_e2e.py) need to import these by
name - they just declare `denidin_app` (etc.) as a test parameter.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from src.models.config import AppConfiguration

from .denidin_mcp_e2e_helpers import (
    DENIDIN_APP_DIR,
    BLOCKED_ROLE_CHAT_ID,
    GODFATHER_CHAT_ID,
    NoMorningTunnelError,
    require_live_morning_tunnel,
)


@pytest.fixture(scope="module")
def denidin_config():
    """Load denidin-app's own TEST config (real secrets, gitignored) - never
    config.json. Isolated to test_data, this test's godfather identity."""
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
    sessions_dir = test_data_root / "sessions"
    config.memory['session']['storage_dir'] = str(sessions_dir)
    config.memory['longterm']['storage_dir'] = str(test_data_root / "memory")

    # Start every pytest invocation from a CLEAN session store (2026-07-15).
    # The godfather session is persisted to disk and is NOT reset between
    # separate `pytest` runs, so it accumulated dozens of turns across every
    # run today - a real, billed failure had the model load a 7400-token
    # history full of earlier "couldn't find" failures and just imitate that
    # pattern (replying "couldn't find" without even calling a tool) instead
    # of acting on the invoice it had just created one turn earlier. A real
    # user's conversation never carries a different run's history; clearing
    # here makes each invocation an independent conversation. Tests WITHIN one
    # invocation still share the session (the intended multi-turn "one long
    # chat" - create -> mark paid, etc. - is preserved); only cross-run
    # carryover is dropped.
    if sessions_dir.exists():
        shutil.rmtree(sessions_dir)

    # AIHandler._load_constitution() now resolves against
    # constitution_config.base_dir (default 'config'), not data_root - the
    # constitution is shared config content, not per-environment data, so
    # config.test.json's un-overridden default already points straight at
    # the real apps/denidin-app/config/runtime_constitution.md. No mirroring
    # into test_data needed anymore (previously required because the old
    # data_root-relative resolution meant overriding data_root above would
    # otherwise find nothing here).

    config.godfather_phone = GODFATHER_CHAT_ID
    config.user_roles = {'admin_phones': [], 'blocked_phones': [BLOCKED_ROLE_CHAT_ID]}

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
    # - must assign it here, matching tests/billed/test_simple_text_e2e.py's
    # existing pattern, or the router handler treats the app as uninitialized.
    denidin.denidin_app = denidin.initialize_app(config_dict)
    return denidin.denidin_app
