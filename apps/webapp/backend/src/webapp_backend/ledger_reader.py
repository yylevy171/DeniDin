"""Read-only composition of denidin-app's managers into the webapp response shapes.

Reuses ``LedgerEventManager`` as-is (Feature 068 plan) — never a mutating method. The only
denidin-app change this feature makes is the additive ``LedgerEventManager.list_events()``.
"""
import importlib.util
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from utils.time_utils import now_local  # apps/denidin-app/src on path (webapp_backend/__init__)


def _load_ledger_event_manager_class():
    """Load ``LedgerEventManager`` from its file directly, bypassing
    ``denidin-app/src/managers/__init__.py`` — that package ``__init__`` eagerly imports the
    whole manager suite (UserManager/MediaFileManager/MemoryManager → requests, chromadb,
    openai, …), none of which the read-only webapp needs. The module itself only needs
    ``rapidfuzz`` + ``src.utils.time_utils`` (both already satisfied)."""
    denidin_src = Path(__file__).resolve().parents[4] / "denidin-app" / "src"
    module_path = denidin_src / "managers" / "ledger_event_manager.py"
    spec = importlib.util.spec_from_file_location(
        "webapp_backend._vendored_ledger_event_manager", module_path
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.LedgerEventManager


LedgerEventManager = _load_ledger_event_manager_class()

# EventRow fields, right-to-left in the UI (spec.md "Row Fields")
_ROW_FIELDS = ("event_id", "date", "source_type", "event_subtype", "client_name",
               "amount", "description")

DEFAULT_DAYS_BACK = 7


def _flex_date(raw: Any) -> Optional[date]:
    """Parse a date string in any of the shapes this codebase persists: ``DD/MM/YYYY`` and
    ``YYYY-MM-DD`` (with or without a trailing `` HH:MM`` time part)."""
    if not isinstance(raw, str) or not raw.strip():
        return None
    head = raw.strip().split(" ")[0]
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(head, fmt).date()
        except ValueError:
            continue
    return None


def _parse_event_date(record: Dict[str, Any]) -> Optional[date]:
    """The date an event is filtered/sorted by (spec.md: ``txn_date`` where present, else the
    event's own date). ``event_datetime`` is the current-schema field; ``event_date`` is the
    pre-Phase-11 equivalent still on older הסכם/בנק events (which have no ``event_datetime``
    at all — that gap silently dropped every non-Morning event before this)."""
    return (
        _flex_date(record.get("txn_date"))
        or _flex_date(record.get("event_datetime"))
        or _flex_date(record.get("event_date"))
    )


def _fmt_ddmmyyyy(value: Optional[date]) -> Optional[str]:
    return value.strftime("%d/%m/%Y") if value else None


def _collect_strings(value: Any, out: List[str]) -> None:
    if isinstance(value, str):
        if value.strip():
            out.append(value)
    elif isinstance(value, bool):
        return
    elif isinstance(value, (int, float)):
        out.append(str(value))
    elif isinstance(value, dict):
        for v in value.values():
            _collect_strings(v, out)
    elif isinstance(value, (list, tuple)):
        for v in value:
            _collect_strings(v, out)


def _search_blob(record: Dict[str, Any]) -> str:
    """Every human-readable string/number anywhere in the full event record, lowercased and
    space-joined — so the frontend's free-text filter matches text that isn't in the six
    display columns (agreement descriptions, component labels, references, …)."""
    parts: List[str] = []
    _collect_strings(record, parts)
    return " ".join(parts).lower()


def _to_row(record: Dict[str, Any]) -> Dict[str, Any]:
    row = {k: record.get(k) for k in _ROW_FIELDS}
    row["date"] = _fmt_ddmmyyyy(_parse_event_date(record))
    row["search_blob"] = _search_blob(record)
    return row


class LedgerReader:
    def __init__(self, data_root: str) -> None:
        self._manager = LedgerEventManager(str(Path(data_root) / "events"))

    def list_event_rows(self, days_back: int = DEFAULT_DAYS_BACK) -> Dict[str, Any]:
        if days_back < 0:
            days_back = DEFAULT_DAYS_BACK
        cutoff = now_local().date() - timedelta(days=days_back)
        dated: List[tuple] = []
        for record in self._manager.list_events():
            event_date = _parse_event_date(record)
            if event_date is None or event_date < cutoff:
                continue
            dated.append((event_date, record.get("event_id") or "", record))
        # newest-first; same-date tiebreaker = event_id descending (Component 2.1)
        dated.sort(key=lambda t: (t[0], t[1]), reverse=True)
        rows = [_to_row(rec) for _, _, rec in dated]
        return {"events": rows, "days_back": days_back, "count": len(rows)}

    def get_event_detail(self, event_id: str) -> Optional[Dict[str, Any]]:
        for record in self._manager.list_events():
            if record.get("event_id") == event_id:
                return dict(record)
        return None

    def search_client_names(self, prefix: str) -> List[str]:
        needle = prefix.strip().lower()
        if len(needle) < 2:
            return []
        by_key: Dict[str, str] = {}
        for record in self._manager.list_events():
            name = record.get("client_name")
            if isinstance(name, str) and name.lower().startswith(needle):
                by_key.setdefault(name.lower(), name)  # first-seen casing wins
        return sorted(by_key.values(), key=str.lower)
