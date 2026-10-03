"""
Wire Log (2026-09-24, debug_exact_calls skill investigation).

The ONLY two logging functions for anything crossing a wire boundary this
app has (OpenAI, WhatsApp inbound, WhatsApp outbound - text/buttons/
reaction/progress-update/proactive/file/etc). Every call site imports and
calls `audit_wire`/`debug_wire` directly - there is no third function, no
per-module alias, no per-boundary wrapper, no thin/thick delegator anywhere
else in this codebase. (Before this, the count had crept to five real
functions across two modules - `rawlog.py`'s `log_outgoing_request`/
`log_raw_response`, `whatsapp_audit_log.py`'s `log_inbound`/`log_outbound` -
PLUS a THIRD layer: `ai_handler.py` re-exported its own
`_log_outgoing_request`/`_log_raw_response` aliases, which
`accounting_reconciliation_service.py` and `image_extractor.py` then
imported cross-module instead of importing the real thing. All of that is
now deleted - `rawlog.py`/`whatsapp_audit_log.py` no longer exist.)

- `audit_wire(boundary, direction, context, payload)` - INFO-level, concise,
  prod-safe. Derives its own short summary from `payload` based on
  `boundary`/`direction` - callers never pre-format a summary string
  themselves, they just pass the same raw payload `debug_wire` gets.
- `debug_wire(boundary, direction, context, payload)` - DEBUG-level, full
  byte/JSON-verbatim. Logs `payload` in full: an OpenAI SDK response
  object's real `model_dump_json()` text as-is (never re-wrapped in an
  extra repr() layer - a real bug this consolidation also fixed, see git
  history), a WhatsApp webhook/send payload with binary fields redacted,
  anything else via `repr()`.

`boundary` is `'openai'`, `'vision'` or `'whatsapp'`. `'vision'` is the media
extractors' vision-model call (config.ai_vision_model, possibly a different model
from the conversational one) - same OpenAI API and payload shapes as `'openai'`,
named apart so a trace never confuses the two; its inline image data URL is
redacted before logging. `direction` is `'out'` (app -> the
other side) or `'in'` (the other side -> app). `context` is a short label
for the specific call site (e.g. `'_run_resolution_loop (first round)'`,
`'text'`, `'reaction'`, `'webhook'`) - free text, not an enum.

`payload` shape by boundary:
- `openai`/`out`: the exact `kwargs` dict passed to `responses.create(**kwargs)`.
- `openai`/`in`: the response object itself (or any object exposing
  `model_dump_json`/`id`/`status`).
- `whatsapp`/`in`: the raw webhook event dict (`notification.event`).
- `whatsapp`/`out`: a small dict, at minimum `{"chat_id": ..., "message": ...}`
  - any extra keys (`reaction`, `idMessage`, etc.) are logged too, not
    filtered.

Never raises - logging must never be the reason a real call fails.
"""
import copy
from typing import Any, Dict

from src.utils.logger import get_logger

logger = get_logger(__name__)

# Fields anywhere in a WhatsApp payload that may carry inline base64 binary
# and must never be logged verbatim - confirmed against Green API's own
# documented webhook shape (src/models/green_api.py's FileMessageData:
# "jpegThumbnail: Image preview in base64"). downloadUrl (a plain URL, not
# binary) and everything else is safe and logged as-is.
_BINARY_FIELD_NAMES = {"jpegThumbnail"}


def _redact_data_urls(value: Any) -> Any:
    """Deep-copy `value`, replacing any inline `data:` URL string (the image a
    vision request carries, base64, often megabytes) with a short placeholder.
    Applied to every `vision` payload before logging."""
    if isinstance(value, dict):
        return {key: _redact_data_urls(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_redact_data_urls(item) for item in value]
    if isinstance(value, str) and value.startswith("data:"):
        return f"<redacted data URL, {len(value)} chars>"
    return value


def _redact_binary_fields(value: Any) -> Any:
    """Deep-copy `value`, replacing any dict value whose key is a known
    binary-carrying field with a short placeholder instead of the real
    (potentially large) base64 content. Recurses through nested
    dicts/lists so this is safe regardless of exactly where Green API
    nests the field for a given message type. Internal to this module -
    both `audit_wire` and `debug_wire` apply it to any `whatsapp` payload
    before logging, so no call site ever has to remember to redact
    anything itself."""
    if isinstance(value, dict):
        result: Dict[str, Any] = {}
        for key, val in value.items():
            if key in _BINARY_FIELD_NAMES and isinstance(val, str) and val:
                result[key] = f"<redacted base64, {len(val)} chars>"
            else:
                result[key] = _redact_binary_fields(val)
        return result
    if isinstance(value, list):
        return [_redact_binary_fields(item) for item in value]
    return value


def _loaded_capabilities(instructions: Any) -> Any:
    """The comma-separated capability list out of a backbone `instructions`
    body's "## Loaded capabilities" section, or None if it has none (a
    non-backbone call). Replaces printing the whole instructions text."""
    import re  # pylint: disable=import-outside-toplevel
    if not isinstance(instructions, str):
        return None
    match = re.search(r"## Loaded capabilities\n\n([^\n]+)", instructions)
    return match.group(1).strip() if match else None


def _loaded_flows(instructions: Any) -> Any:
    """The comma-separated flow list out of a backbone `instructions` body's
    "## Loaded flows" section, or None if it has none."""
    import re  # pylint: disable=import-outside-toplevel
    if not isinstance(instructions, str):
        return None
    match = re.search(r"## Loaded flows\n\n([^\n]+)", instructions)
    return match.group(1).strip() if match else None


def _name_instructions(instructions: Any) -> str:
    """Names the `instructions` bundle instead of printing its (potentially
    huge, cache-defeating-to-log) full text - the one deliberate exception
    to "audit carries everything debug does": everything else in a
    `responses.create()` call is short enough to log in full at INFO, this
    one field alone is not. A backbone call names its loaded flows/
    capabilities (already extracted for exactly this purpose); anything
    else just gets a short, fixed label so it's still identifiable which
    prompt bundle was in play."""
    flows = _loaded_flows(instructions)
    capabilities = _loaded_capabilities(instructions)
    if flows is not None or capabilities is not None:
        return f"backbone (flows={flows}, capabilities={capabilities})"
    if isinstance(instructions, str) and "Ledger Event Recognition" in instructions:
        return "ledger recognition prompt"
    if isinstance(instructions, str) and instructions:
        return "runtime constitution (legacy ai_handler)"
    return "none"


def _summarize(boundary: str, direction: str, payload: Any) -> str:
    """Derives `audit_wire`'s payload - the SAME structured content
    `debug_wire` logs, JSON-serialized, with exactly one difference: an
    `openai`/`out` call's `instructions` field is replaced with a short name
    (see `_name_instructions`) instead of its full text. Nothing else is
    shortened, summarized, or reshaped - `parse_trace.py` runs this through
    the IDENTICAL per-item renderer it uses for debug (that renderer already
    treats a short `instructions` value as a plain line instead of nesting
    it), which is what makes an audit section actually look like a debug
    section rather than a hand-rolled one-line summary that could never
    structurally match it no matter how much detail got stuffed in."""
    import json  # pylint: disable=import-outside-toplevel
    if boundary == "vision" and direction == "out" and isinstance(payload, dict):
        return json.dumps(_redact_data_urls(payload), ensure_ascii=False, default=str)
    if boundary in ("openai", "vision"):
        if direction == "out" and isinstance(payload, dict):
            named = dict(payload)
            named["instructions"] = _name_instructions(payload.get("instructions"))
            return json.dumps(named, ensure_ascii=False, default=str)
        if direction == "in":
            dump_fn = getattr(payload, "model_dump", None)
            data = dump_fn() if callable(dump_fn) else payload
            return json.dumps(data, ensure_ascii=False, default=str)
    if boundary == "whatsapp" and isinstance(payload, dict):
        redacted = _redact_binary_fields(payload)
        return json.dumps(redacted, ensure_ascii=False, default=str)
    return repr(payload)


def audit_wire(boundary: str, direction: str, context: str, payload: Any) -> None:
    """INFO-level, concise, prod-safe record of one message crossing ANY
    wire boundary this app has. See module docstring for `payload` shape
    per boundary/direction."""
    try:
        summary = _summarize(boundary, direction, payload)
        logger.info(f"[WIRE-AUDIT] boundary={boundary!r} direction={direction!r} context={context!r} {summary}")
    except Exception as e:  # pylint: disable=broad-except
        logger.error(f"[WIRE-AUDIT] {context} {direction}: failed to log: {e}", exc_info=True)


def debug_wire(boundary: str, direction: str, context: str, payload: Any) -> None:
    """DEBUG-level, full byte/JSON-verbatim record of the exact content that
    crossed a wire. See module docstring for `payload` shape per
    boundary/direction and exactly how each is rendered."""
    try:
        if boundary == "whatsapp" and isinstance(payload, (dict, list)):
            payload = _redact_binary_fields(copy.deepcopy(payload))
        if boundary == "vision" and isinstance(payload, (dict, list)):
            payload = _redact_data_urls(payload)
        dump_fn = getattr(payload, "model_dump_json", None)
        content = dump_fn() if callable(dump_fn) else repr(payload)
        logger.debug(f"[WIRE-DEBUG] boundary={boundary!r} direction={direction!r} "
                     f"context={context!r} payload={content}")
    except Exception as e:  # pylint: disable=broad-except
        logger.error(f"[WIRE-DEBUG] {context} {direction}: failed to log: {e}", exc_info=True)
