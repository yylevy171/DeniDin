"""Loads the real Feature 070 components from ``apps/denidin-app`` by ``sys.path``
insertion — the established sibling-app pattern (see ``apps/prod-ledger-backfill``
and ``requirements.txt``'s note). Neither sibling app is pip-installable.

Unlike ``prod-ledger-backfill`` (whose ``LedgerEventManager`` was genuinely light
and needed an ``importlib`` trick to dodge ``src/managers/__init__.py``'s eager
imports), this pipeline *deliberately* imports ``SessionManager`` +
``MemoryManager`` — so it needs their heavy transitive deps (``tiktoken``,
``chromadb``, ``openai``) anyway, and a plain package import is correct here.

The migration reuses the **exact** nightly roll code path
(``daily_summary_roll_service._roll_one_chat_day``) rather than re-deriving the
summary/embedding/marker logic — a backfilled ``daily_summary`` is byte-for-byte
what the 02:00 job would have produced, differing only by ``source="migration"``.
"""
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_DENIDIN_APP_ROOT = _REPO_ROOT / "apps" / "denidin-app"

_app_root_str = str(_DENIDIN_APP_ROOT)
if _app_root_str not in sys.path:
    sys.path.insert(0, _app_root_str)

# pylint: disable=wrong-import-position
from src.handlers.summarizer import summarize_conversation  # noqa: E402,F401
from src.managers.memory_collections import collection_name_for_chat  # noqa: E402,F401
from src.managers.memory_manager import MemoryManager  # noqa: E402,F401
from src.managers.message_integrity import assert_message_integrity  # noqa: E402,F401
from src.managers.roll_marker_store import RollMarkerStore  # noqa: E402,F401
from src.managers.session_manager import SessionManager  # noqa: E402,F401
from src.models.config import AppConfiguration  # noqa: E402,F401
from src.services import daily_summary_roll_service as roll_service  # noqa: E402,F401
from src.utils.time_utils import local_calendar_date, now_local  # noqa: E402,F401

DENIDIN_APP_ROOT = _DENIDIN_APP_ROOT

__all__ = [
    "AppConfiguration",
    "MemoryManager",
    "RollMarkerStore",
    "SessionManager",
    "assert_message_integrity",
    "collection_name_for_chat",
    "local_calendar_date",
    "now_local",
    "roll_service",
    "summarize_conversation",
    "DENIDIN_APP_ROOT",
]
