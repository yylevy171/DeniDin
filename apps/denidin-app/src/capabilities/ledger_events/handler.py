"""
Ledger Query capability (Feature 063) - a real, directly-attachable local
tool (`query_ledger_events`) wrapping the existing, unmodified
`src/managers/ledger_event_manager.py` (REQ-063-03). Capturing ledger events
is not a capability: it is `denidin.py`'s shared post-turn recognition.
"""
import json
import logging
from typing import Any, Dict

from src.constants.error_messages import BACKBONE_CAPABILITY_NOT_CONFIGURED

logger = logging.getLogger(__name__)


def dispatch_direct_tool_call(backbone, tool_name: str, args: Dict[str, Any],
                               turn_context: Dict[str, Any]) -> str:
    """Executes one `query_ledger_events` call directly on the ongoing chain
    - deterministic, no separate AI call, the same `query_events(**arguments)`
    call the legacy handler makes. Returns the raw matching events as
    JSON for the model to reason over (arithmetic/aggregation is the model's
    job, per cap_ledger_query.md)."""
    del turn_context
    if tool_name != "query_ledger_events":
        return f"error: unknown ledger tool {tool_name!r}"
    if backbone.ledger_event_manager is None:
        return BACKBONE_CAPABILITY_NOT_CONFIGURED
    result = backbone.ledger_event_manager.query_events(**args)
    return json.dumps(result, ensure_ascii=False)
