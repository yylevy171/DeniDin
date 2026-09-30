"""
Backbone-level cross-cutting local tools (Feature 063 remaining Deferred item) -
`send_progress_update` (Feature 080) and `react_to_message` (Feature 084).
Unlike every domain capability's own tools, these apply uniformly regardless of
which capabilities are loaded (backbone.md's own "Proactive Progress Updates"/
"Reaction Management" sections), so BackboneOrchestrator._run_orchestration_loop
attaches them to every Responses API call it makes.

The schemas live in `src/tool_actions/tool_schemas.py` - one definition shared with
the legacy AIHandler, never a second copy.

Every backbone-tool call in a round's response is dispatched, and ALL their
outputs are submitted together in the loop's next round - closing bugfix-042's
exact failure mode (every function_call gets its output submitted, never left
dangling).
"""
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from src.tool_actions.tool_schemas import REACT_TO_MESSAGE_TOOL, SEND_PROGRESS_UPDATE_TOOL

logger = logging.getLogger(__name__)

BACKBONE_TOOLS: List[Dict[str, Any]] = [SEND_PROGRESS_UPDATE_TOOL, REACT_TO_MESSAGE_TOOL]
_BACKBONE_TOOL_NAMES = {tool["name"] for tool in BACKBONE_TOOLS}


def extract_backbone_tool_calls(response) -> List[Tuple[str, str, Dict[str, Any]]]:
    """Every (call_id, tool_name, parsed_args) for a send_progress_update/
    react_to_message function_call item in `response.output`, in order. Never
    raises - a malformed call's arguments are skipped (logged) rather than
    crashing the turn."""
    calls: List[Tuple[str, str, Dict[str, Any]]] = []
    for item in (getattr(response, "output", None) or []):
        if getattr(item, "type", None) != "function_call":
            continue
        name = getattr(item, "name", None)
        if name not in _BACKBONE_TOOL_NAMES:
            continue
        call_id = getattr(item, "call_id", None)
        if not call_id:
            continue
        try:
            args = json.loads(item.arguments)
        except (json.JSONDecodeError, TypeError) as exc:
            logger.warning("Malformed %r arguments discarded: %s", name, exc)
            continue
        calls.append((str(call_id), str(name), args))
    return calls
