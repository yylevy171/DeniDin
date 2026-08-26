"""
Pytest configuration for the prod-ledger-backfill test suite (Feature 061).

Sys.path bootstrap follows the exact pattern already established by
apps/morning-mcp-app/conftest.py and apps/denidin-app/conftest.py — neither sibling app is
pip-installable (no setup.py/pyproject.toml in either), so both are reached via sys.path
insertion, not a package "path dependency" (see requirements.txt's own note).

Two distinct insertions are needed here, for two distinct reasons:
- apps/morning-mcp-app/src is inserted so `denidin_mcp_morning.morning_client` (MorningClient/
  MorningAuth) imports the same way morning-mcp-app's own tests import it.
- apps/denidin-app itself (its *root*, not its src/ subdirectory) is inserted so `src.utils.
  time_utils` (a genuinely lightweight, docstring-only-`__init__.py` package chain) is importable
  as `LedgerEventManager` itself needs. `LedgerEventManager` is NOT imported via a plain
  `from src.managers.ledger_event_manager import ...` here, though — see
  `_ledger_event_manager_loader.py` for why (that module's own docstring has the full story: a
  package `__init__.py` gotcha discovered during implementation, unrelated to
  `LedgerEventManager`'s own genuinely-decoupled design).
"""
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent
REPO_ROOT = PROJECT_ROOT.parent.parent

MORNING_MCP_SRC = REPO_ROOT / "apps" / "morning-mcp-app" / "src"
DENIDIN_APP_ROOT = REPO_ROOT / "apps" / "denidin-app"

for path in (MORNING_MCP_SRC, DENIDIN_APP_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "billed: real, text-only OpenAI/Morning API calls (see pytest.ini)"
    )


@pytest.fixture
def tmp_output_dir(tmp_path):
    """A stable, empty local directory for a single test's --output-dir / --input-dir."""
    d = tmp_path / "output"
    d.mkdir()
    return d


@pytest.fixture
def fixture_creds_dict():
    """
    A syntactically valid (fake, never real) backfill_prod_creds.local.json-shaped dict —
    contracts/backfill-creds-file.md's exact four-field shape.
    """
    return {
        "api_key_id": "fixture-api-key-id",
        "api_key_secret": "fixture-api-key-secret",
        "auth_url": "https://fixture-auth.example.invalid",
        "base_url": "https://fixture-api.example.invalid/api/v1",
    }


@pytest.fixture
def fixture_creds_file(tmp_path, fixture_creds_dict):
    """A real file on disk holding fixture_creds_dict, for tests exercising file-loading logic."""
    import json
    path = tmp_path / "backfill_prod_creds.local.json"
    path.write_text(json.dumps(fixture_creds_dict), encoding="utf-8")
    return path


@pytest.fixture
def fixture_raw_document():
    """
    One fixture Morning document, in the shape MorningClient.get_invoice() returns — the minimal
    fields Method A / transform.py / validate.py all key off.
    """
    return {
        "id": "fixture-doc-001",
        "number": "INV-2025-001",
        "type": 320,  # Morning's invoice type code
        "client": {"id": "fixture-client-001", "name": "Fixture Client Ltd."},
        "creationDate": "2025-01-15T09:30:00.000Z",
    }


@pytest.fixture
def fixture_search_page_1():
    """
    Page 1 of a fixture multi-page /documents/search response — used by pagination tests
    (research.md R3/R4) to prove no artificial 100-item cap exists.
    """
    return {
        "items": [{"id": f"fixture-doc-{i:03d}"} for i in range(1, 101)],
        "total": 150,
        "page": 1,
        "pages": 2,
    }


@pytest.fixture
def fixture_search_page_2():
    """Page 2 of the same fixture multi-page response — the remaining 50 of 150 total."""
    return {
        "items": [{"id": f"fixture-doc-{i:03d}"} for i in range(101, 151)],
        "total": 150,
        "page": 2,
        "pages": 2,
    }
