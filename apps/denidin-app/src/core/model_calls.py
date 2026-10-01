"""
OpenAI-call/error-handling/persistence primitives shared by the legacy AIHandler
and the Feature 063 backbone (2026-09-30 consolidation request):
ONE place that calls OpenAI with an explicit retry for the SDK's own retry gap,
ONE fallback-response shape, and ONE "record what the user sent/was told" write
for a turn that never reached a normal reply - moved out of handlers/ai_handler.py
with behavior unchanged, one implementation, used by both paths.
"""
import contextlib
import logging
import time
from typing import Any, Callable, Dict, List, Optional

from openai import APIStatusError

from src.models.message import AIResponse
from src.utils.time_utils import now_local

logger = logging.getLogger(__name__)

# HTTP status codes the OpenAI SDK's own retry logic does NOT cover
# (openai._base_client.BaseClient._should_retry only retries 408/409/429/>=500,
# or an explicit `x-should-retry: true` response header - confirmed from the
# installed SDK's own source, not assumed) but that are worth one explicit
# retry here anyway. Currently just 424 (Failed Dependency) - seen live when
# OpenAI's own connector-proxy fails to fetch an attached MCP server's tool
# list before the model ever sees the conversation (real production/test
# investigation, 2026-09-30).
EXPLICIT_RETRY_STATUS_CODES = frozenset({424})

# 2020-01-01 00:00:00 UTC (Feature 069). Anything below this - 0, a negative
# value, a malformed webhook timestamp, a test sentinel - is treated as "no
# usable source time", so the persisted Message.timestamp falls back to
# processing time instead of landing the message decades in the past.
_MIN_PLAUSIBLE_SOURCE_EPOCH = 1_577_836_800


def call_model_with_retry(call_fn: Callable[[], Any], *, context: str,
                           max_retries: int = 1, backoff_seconds: float = 2.0) -> Any:
    """Calls call_fn() (a responses.create(**kwargs) invocation), retrying once
    (by default) on an APIStatusError whose status_code is in
    EXPLICIT_RETRY_STATUS_CODES - a gap the OpenAI SDK's own max_retries never
    covers. Any other exception, or a retryable one that still fails after
    max_retries, propagates unchanged - callers keep their own existing
    except/fallback handling untouched."""
    attempt = 0
    while True:
        try:
            return call_fn()
        except APIStatusError as exc:
            status_code = getattr(exc, "status_code", None)
            if status_code not in EXPLICIT_RETRY_STATUS_CODES or attempt >= max_retries:
                raise
            attempt += 1
            logger.warning(
                "%s: got HTTP %s (not covered by the OpenAI SDK's own retry "
                "logic) - retrying explicitly (%d/%d) after %.1fs",
                context, status_code, attempt, max_retries, backoff_seconds,
            )
            time.sleep(backoff_seconds)


def build_fallback_response(request_id: str, message: str) -> AIResponse:
    """The one AIResponse shape both the legacy AIHandler and the backbone
    backbone return when their own top-level try/except catches something
    unexpected - identical in both before this consolidation, so there is now
    exactly one implementation."""
    return AIResponse(
        request_id=request_id,
        response_text=message,
        tokens_used=0,
        prompt_tokens=0,
        completion_tokens=0,
        model="error-fallback",
        finish_reason="error",
        timestamp=int(time.time()),
    )


def sane_source_epoch(epoch: Optional[int]) -> Optional[int]:
    """Return `epoch` when it's a plausible real send-time, else None."""
    if epoch is None or epoch < _MIN_PLAUSIBLE_SOURCE_EPOCH:
        return None
    return epoch


def timed_model_call(builder: Optional[Any], call_fn: Callable[[], Any], *, context: str) -> Any:
    """2026-10-01 consolidation: the ONE timed responses.create() call (Feature 080,
    REQ-080-04) - moved out of AIHandler._timed_llm_call, also used by the backbone (which
    used to record only successful calls). call_fn runs through call_model_with_retry;
    the call is timed and recorded into `builder` on success AND failure alike (a
    timed-out/errored call still consumed wall-clock time), the call's own exception
    propagating unchanged. Recording is a no-op when `builder` is None; the retry always
    applies."""
    retrying_call_fn = lambda: call_model_with_retry(call_fn, context=context)  # noqa: E731
    if builder is None:
        return retrying_call_fn()
    from src.managers.telemetry_manager import monotonic_ms  # pylint: disable=import-outside-toplevel
    start_ms = monotonic_ms()
    response = None
    try:
        response = retrying_call_fn()
        return response
    finally:
        duration_ms = monotonic_ms() - start_ms
        usage = getattr(response, "usage", None)
        input_tokens = getattr(usage, "input_tokens", 0) or 0
        output_tokens = getattr(usage, "output_tokens", 0) or 0
        try:
            builder.record_llm_call(duration_ms, input_tokens, output_tokens)
        except Exception as telemetry_error:  # pylint: disable=broad-except
            # Telemetry accounting must never break the real call it's timing.
            logger.warning(f"Feature 080 telemetry record_llm_call failed: {telemetry_error}")


@contextlib.contextmanager
def tool_call_span(builder: Optional[Any], tool_name: str, *, is_morning_tool: bool = False):
    """2026-10-01 consolidation: the ONE tool-call timing (Feature 080, REQ-080-04,
    contracts/telemetry-recorder.md's record_tool_call()) - moved out of
    AIHandler._timed_tool_call so the backbone records tool calls exactly the way the
    legacy path does. Times the wrapped block, success or exception alike, and records it
    into `builder`; a complete no-op when `builder` is None. A telemetry failure is
    logged, never raised - it must never break the real call it's timing."""
    if builder is None:
        yield
        return
    from src.managers.telemetry_manager import monotonic_ms  # pylint: disable=import-outside-toplevel
    start_ms = monotonic_ms()
    try:
        yield
    finally:
        duration_ms = monotonic_ms() - start_ms
        try:
            builder.record_tool_call(tool_name, duration_ms, is_morning_tool=is_morning_tool)
        except Exception as telemetry_error:  # pylint: disable=broad-except
            logger.warning(f"Feature 080 telemetry record_tool_call failed: {telemetry_error}")


def timed_tool_call(builder: Optional[Any], tool_name: str, call_fn: Callable[[], Any], *,
                    is_morning_tool: bool = False) -> Any:
    """call_fn() inside tool_call_span - the function form of the same timing."""
    with tool_call_span(builder, tool_name, is_morning_tool=is_morning_tool):
        return call_fn()


def record_mcp_tool_calls(builder: Optional[Any], mcp_calls: List[Dict[str, Any]]) -> None:
    """Records each of a turn's Morning MCP calls (Feature 080, REQ-080-04) for the
    tool_calls_count/morning_api_request_times_ms breakdown - moved out of
    AIHandler._finalize_response, one implementation for both paths. Duration is
    deliberately ~0: OpenAI's Responses API runs a remote MCP call server-side, INSIDE
    responses.create() (already timed as an LLM call), so there is no separate per-tool
    duration observable from this side. A no-op when `builder` is None."""
    if builder is None:
        return
    for call in mcp_calls:
        timed_tool_call(builder, call["name"], lambda: None, is_morning_tool=True)


@contextlib.contextmanager
def telemetry_span(telemetry_manager: Optional[Any], request_id: str, effective_chat_id: Optional[str]):
    """2026-09-30 consolidation: the ONE turn-level telemetry lifecycle (Feature 080,
    REQ-080-04) - previously copy-pasted, byte-for-byte identically in shape, into both
    AIHandler.get_response (a module-level contextvar) and
    Backbone.turn_with_rounds (an instance attribute). Yields the constructed
    TelemetryBuilder for the caller to install into whichever turn-scoped mechanism it
    uses (this function is agnostic to that), and records the finished RequestTelemetry
    row on the way out - success OR exception alike. Yields None and is a complete no-op
    when telemetry_manager is None (the flag is off, or was never configured) -
    preserving byte-identical behavior to before Feature 080 existed."""
    if telemetry_manager is None:
        yield None
        return
    from src.managers.telemetry_manager import TelemetryBuilder  # pylint: disable=import-outside-toplevel
    builder = TelemetryBuilder(request_id, effective_chat_id, now_local().isoformat())
    try:
        yield builder
    finally:
        try:
            record = builder.finalize(now_local().isoformat())
            telemetry_manager.record(record)
        except Exception as telemetry_error:  # pylint: disable=broad-except
            logger.warning("Feature 080 telemetry finalize/record failed: %s", telemetry_error)
