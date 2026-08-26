"""
Loads the real `LedgerEventManager` class directly from
apps/denidin-app/src/managers/ledger_event_manager.py, without triggering
`src/managers/__init__.py`'s eager imports of sibling managers.

**Real gap discovered during implementation (2026-08-25), not anticipated by research.md R5**:
`LedgerEventManager` itself is genuinely decoupled (plain-string `storage_dir`, no
`AppConfiguration`, no other manager as a dependency) — but Python always executes a package's
`__init__.py` when importing *any* submodule of that package, and
`apps/denidin-app/src/managers/__init__.py` eagerly imports `SessionManager` (needs `tiktoken`),
`MemoryManager` (needs `chromadb`/`openai` embeddings), `UserManager`, and `MediaFileManager` —
none of which `LedgerEventManager` itself needs, but all of which a plain
`from src.managers.ledger_event_manager import LedgerEventManager` would drag in.

Rather than pip-installing denidin-app's entire heavy `requirements.txt` into this lightweight
app just to satisfy an unrelated sibling import, this module loads the one file directly via
`importlib`, under a synthetic module name outside the `src.managers` package hierarchy — so
`src/managers/__init__.py` is never executed. `src.utils.time_utils` (the one thing
`ledger_event_manager.py` itself actually imports) is loaded first, normally — `src/__init__.py`
and `src/utils/__init__.py` are both trivial (docstring-only, confirmed by reading them), so that
half of the import is genuinely lightweight, exactly as research.md R5 described.

No change to any file under apps/denidin-app/ — this is a read-only, external loading trick.
"""
import importlib.util
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent.parent
_DENIDIN_APP_ROOT = _REPO_ROOT / "apps" / "denidin-app"
_LEDGER_EVENT_MANAGER_PATH = _DENIDIN_APP_ROOT / "src" / "managers" / "ledger_event_manager.py"

_cached_module = None


def _get_ledger_event_manager_module():
    """Loads apps/denidin-app/.../ledger_event_manager.py exactly once, caching the module
    object itself so both accessors below (class + private function) share one load."""
    global _cached_module
    if _cached_module is not None:
        return _cached_module

    denidin_app_root_str = str(_DENIDIN_APP_ROOT)
    if denidin_app_root_str not in sys.path:
        sys.path.insert(0, denidin_app_root_str)

    # Populates sys.modules['src.utils.time_utils'] normally — lightweight (see module docstring).
    import src.utils.time_utils  # noqa: F401

    spec = importlib.util.spec_from_file_location(
        "_denidin_ledger_event_manager", _LEDGER_EVENT_MANAGER_PATH
    )
    module = importlib.util.module_from_spec(spec)
    # Registered in sys.modules BEFORE exec, matching Python's own import-machinery convention —
    # without this, a second, independent load attempt elsewhere would re-exec the file instead
    # of reusing this one (harmless here since everything goes through this one cache, but doing
    # it properly costs nothing and avoids a subtle surprise later).
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    _cached_module = module
    return _cached_module


def get_ledger_event_manager_class():
    """
    Returns the real `LedgerEventManager` class, loaded without triggering
    `src/managers/__init__.py`'s unrelated heavy imports (tiktoken/chromadb/openai).
    """
    return _get_ledger_event_manager_module().LedgerEventManager


def get_expand_accounting_document_json_function():
    """
    Returns `ledger_event_manager._expand_accounting_document_json` — the exact code-derived
    field-expansion logic `LedgerEventManager.add_ledger_event` itself calls for every
    `source_type="חשבונית"` event. Reused directly by both method_a.py and method_b.py so
    neither hand-rolls a second mapping (reaching into a "private", underscore-prefixed
    module-level function this way mirrors this repo's own established precedent — see
    `accounting_reconciliation_service.py`'s documented reach into `AIHandler`'s private
    methods, same class of internal reuse).
    """
    module = _get_ledger_event_manager_module()
    return module._expand_accounting_document_json  # pylint: disable=protected-access
