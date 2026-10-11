"""
Reading local function-tool calls off a Responses API response - shared by every caller
that attaches a local function tool (the legacy AIHandler, the ledger-event recognizer,
the accounting reconciler, the image extractor). Moved out of handlers/ai_handler.py
(REQ-063-08) with behavior unchanged.
"""
import json
from typing import Dict, List, Optional, cast

from src.utils.logger import get_logger

logger = get_logger(__name__)


def extract_function_call(response, tool_name: str) -> Optional[Dict]:
    """Find a `function_call` item named `tool_name` in a Responses API `response.output`
    and return its parsed arguments, or None if absent.

    Never raises - malformed `arguments` JSON is logged and treated as "not called",
    the same as if the model hadn't called the tool at all. Shared by the text path
    (AIHandler._finalize_response) and the image path (ImageExtractor._vision_extract) -
    the extraction logic itself doesn't care which one is calling it.
    """
    for item in (getattr(response, "output", None) or []):
        if getattr(item, "type", None) != "function_call" or getattr(item, "name", None) != tool_name:
            continue
        try:
            return cast(Dict, json.loads(item.arguments))
        except json.JSONDecodeError as e:
            logger.warning(f"Malformed {tool_name!r} function_call arguments discarded: {e}")
            return None
    return None


def extract_function_call_id(response, tool_name: str) -> Optional[str]:
    """Find a `function_call` item named `tool_name` in a Responses API `response.output`
    and return its `call_id`, or None if absent.

    Companion to `extract_function_call` - needed only when a real second round-trip
    must report a result back for this specific call (see AIHandler._finalize_response's
    ledger-event follow-up: reasoning models emit a `function_call` OR a final `message`
    in one turn, never both, so `output_text` is empty until the call's result is
    reported back via `previous_response_id` + `function_call_output`).
    """
    for item in (getattr(response, "output", None) or []):
        if getattr(item, "type", None) != "function_call" or getattr(item, "name", None) != tool_name:
            continue
        return getattr(item, "call_id", None)
    return None


def extract_all_function_calls(response, tool_name: str) -> List[Dict]:
    """Find EVERY `function_call` item named `tool_name` in a Responses API
    `response.output`, returning each as {"arguments": dict, "call_id": str}.

    A single turn can legitimately contain more than one call to the same tool -
    e.g. runtime_constitution.md's Ledger Event Recognition explicitly wants one
    capture per hourly work-log entry, never aggregated, so a message describing
    several entries produces several `capture_ledger_event` calls in one turn.
    OpenAI requires a `function_call_output` for EVERY pending function call
    before it will continue a conversation (confirmed empirically, 2026-07-28: a
    follow-up round-trip that only resolved the first of two calls was rejected
    with "No tool output found for function call ..."), so any follow-up must
    account for all of them, not just the first (unlike `extract_function_call`/
    `extract_function_call_id`, which only ever return the first match).

    Never raises - malformed `arguments` JSON on any individual item (most often a
    truncated response - see `arguments=None` below) is logged and kept in the
    results with `arguments=None`, NOT dropped: OpenAI still considers that
    call_id pending regardless of whether we could parse it, so any follow-up
    must still resolve it (bugfix-018 - a dropped call_id here left OpenAI
    rejecting the whole follow-up with "No tool output found for function call
    ...", which in turn left the user with a silently empty reply).
    """
    results = []
    for item in (getattr(response, "output", None) or []):
        if getattr(item, "type", None) != "function_call" or getattr(item, "name", None) != tool_name:
            continue
        call_id = getattr(item, "call_id", None)
        try:
            arguments = json.loads(item.arguments)
        except json.JSONDecodeError as e:
            logger.warning(f"Malformed {tool_name!r} function_call arguments discarded: {e}")
            results.append({"arguments": None, "call_id": call_id})
            continue
        results.append({"arguments": arguments, "call_id": call_id})
    return results
