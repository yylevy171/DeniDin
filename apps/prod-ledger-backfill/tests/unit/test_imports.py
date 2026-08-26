"""
Foundational import-boundary checks (tasks.md T005/T006).

Nothing in this feature's pipeline is testable until both external-app imports work — this file
proves the sys.path bootstrap in conftest.py actually resolves both boundaries, before any
pipeline logic is written against them. No live network call anywhere in this file.
"""


def test_morning_client_and_auth_import_cleanly():
    """T005: MorningClient/MorningAuth import from apps/morning-mcp-app's package."""
    from denidin_mcp_morning.morning_client import MorningClient
    from denidin_mcp_morning.auth import MorningAuth

    # Real constructors, no network call — just prove the shapes match research.md R1/R2.
    assert MorningClient.__init__.__code__.co_varnames[:5] == (
        "self", "api_key_id", "api_key_secret", "auth_url", "base_url",
    )
    assert MorningAuth.__init__.__code__.co_varnames[:4] == (
        "self", "api_key_id", "api_key_secret", "auth_url",
    )


def test_ledger_event_manager_imports_cleanly():
    """
    T006: LedgerEventManager loads from apps/denidin-app's own module tree, via the
    _ledger_event_manager_loader helper (see that module's docstring for why a plain
    `from src.managers.ledger_event_manager import ...` doesn't work here — a real
    src/managers/__init__.py gotcha found during implementation).
    """
    from _ledger_event_manager_loader import get_ledger_event_manager_class

    LedgerEventManager = get_ledger_event_manager_class()

    # Real constructor, no filesystem access beyond a plain string path — just prove the shape
    # matches research.md R5 (storage_dir-only, fully decoupled from AppConfiguration).
    assert LedgerEventManager.__init__.__code__.co_varnames[:2] == ("self", "storage_dir")


def test_ledger_event_manager_does_not_drag_in_heavy_siblings():
    """
    Confirms the loader actually avoids the tiktoken/chromadb/openai import chain that a plain
    package-level import would trigger (src/managers/__init__.py eagerly imports SessionManager,
    MemoryManager, etc.) — the whole reason the loader exists.
    """
    import sys

    from _ledger_event_manager_loader import get_ledger_event_manager_class

    get_ledger_event_manager_class()

    assert "src.managers" not in sys.modules
    assert "tiktoken" not in sys.modules
