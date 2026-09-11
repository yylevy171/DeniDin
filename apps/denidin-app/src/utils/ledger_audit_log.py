"""
Ledger Event Audit Log (Feature 069, 2026-09-03).

INFO-level, one line per `LedgerEvent` that is actually persisted to disk,
carrying the event's COMPLETE JSON record verbatim.

Added after the post-turn recognition mechanism moved ledger writes off the
conversational reply path entirely (Feature 069). Without this there was no
single, greppable record of exactly what was written to the ledger and when -
which made "why did this turn capture an event?" / "why didn't it?" questions
during testing unanswerable without diffing the events directory by hand.

The single call site is `LedgerEventManager.add_ledger_event`, the one
chokepoint every persistence path funnels through - the Feature 069 post-turn
ledgerer (`persist_recognized_event`) AND the Feature 025 reconciliation
sweep alike. Every field of the record is plain metadata/text (no binary, no
secrets) and is logged in full, unredacted - mirroring `whatsapp_audit_log`'s
"the raw wire-level record, verbatim" intent for the ledger boundary.
"""
import json
from typing import Any, Dict

from src.utils.logger import get_logger

logger = get_logger(__name__)

AUDIT_PREFIX = "[AUDIT-LEDGER]"


def log_ledger_event_created(record: Dict[str, Any]) -> None:
    """Log one INFO line for a freshly-persisted `LedgerEvent`, including its
    entire JSON record (`json=<...>`, keys sorted for stable diffing)."""
    try:
        payload = json.dumps(record, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):
        payload = repr(record)
    logger.info(
        f"{AUDIT_PREFIX} event_id={record.get('event_id')!r} "
        f"source_type={record.get('source_type')!r} "
        f"session_id={record.get('session_id')!r} json={payload}"
    )
