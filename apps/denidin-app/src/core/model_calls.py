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
from typing import Any, Callable, Optional

from openai import APIStatusError

from src.models.message import AIResponse
from src.utils.time_utils import local_from_timestamp, now_local

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


def record_exchange(session_manager, *, memory_enabled: bool, rbac_enabled: bool,
                     user_manager, own_whatsapp_number: Optional[str],
                     chat_id: str, user_text: Optional[str],
                     assistant_text: Optional[str], sender_phone: Optional[str],
                     sender_display: Optional[str], is_group: bool = False,
                     chat_name: Optional[str] = None,
                     whatsapp_id_message: Optional[str] = None,
                     source_timestamp: Optional[int] = None) -> None:
    """bugfix-058: records an exchange that never reached a normal reply - e.g.
    an unsupported-type auto-reply, a failed media turn, the catch-all error
    reply, or (2026-09-30) an OpenAI-call exception in either the legacy or
    backbone path - so what the user sent and what they were told is still in
    the session. `user_text=None` records only the assistant text (a notice
    with no new user message). The user message is skipped when the chat
    already holds one with the same `whatsapp_id_message` (the turn persisted
    it before failing). Never raises."""
    if not (memory_enabled and session_manager and chat_id):
        return
    try:
        if rbac_enabled and user_manager and sender_phone:
            role = user_manager.get_user(sender_phone).role
        else:
            role = "client"
        own_number_jid = f"{own_whatsapp_number}@c.us" if own_whatsapp_number else None
        epoch = sane_source_epoch(source_timestamp)
        user_ts = None if epoch is None else local_from_timestamp(epoch)
        already_stored = bool(
            whatsapp_id_message
            and session_manager.has_whatsapp_id_message(chat_id, whatsapp_id_message)
        )
        if user_text and not already_stored:
            session_manager.add_message(
                chat_id=chat_id, role="user", content=user_text, user_role=role,
                sender=sender_phone, sender_name=sender_display,
                recipient=chat_id if is_group else own_number_jid,
                recipient_name=(chat_name or chat_id) if is_group else "DeniDin",
                whatsapp_id_message=whatsapp_id_message, timestamp=user_ts,
            )
        if assistant_text:
            session_manager.add_message(
                chat_id=chat_id, role="assistant", content=assistant_text, user_role=role,
                sender=own_number_jid, sender_name="DeniDin",
                recipient=chat_id if is_group else sender_phone,
                recipient_name=(chat_name or chat_id) if is_group else sender_display,
            )
    except Exception as e:  # pylint: disable=broad-except
        logger.error(f"Failed to record exchange in session: {e}", exc_info=True)
