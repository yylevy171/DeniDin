"""
AIManager (Feature 063, REQ-063-08): the abstract base of DeniDin's AI implementation.

DeniDin owns its data (users, sessions, memory, ledger events, reminders, ...); the AI
implementation is one more object of the app, constructed with the DeniDin object and
reaching everything through it (its managers, and its WhatsApp sends). It has
exactly two implementations - `AIHandler` (legacy, flag off) and `Backbone` (flag on) -
and `initialize_app` builds exactly one of them.

Logic both implementations need lives here once, as methods of this class: building the
AIRequest for an inbound message, the Morning MCP connection, every model call (explicit
retry + telemetry timing), the per-turn context (rolling window, memory recall), the
turn-result helpers and the approved-write safeguards. Each implementation provides its
own turn (`single_turn`), button-tap resolution, sent-approval bookkeeping, and the two
hooks the media extractors call.
"""
import contextlib
import json
import logging
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Dict, Iterable, List, Optional, Tuple, cast

from openai import APIStatusError, OpenAI

from src.managers.memory_collections import collection_name_for_chat
from src.models.message import AIRequest, AIResponse, WhatsAppMessage
from src.utils.time_utils import now_local

if TYPE_CHECKING:  # annotations only - the managers never import this module back
    from src.handlers.fee_agreement_tools import FeeAgreementToolHandler
    from src.handlers.morning_mcp_locator import MorningMcpLocator
    from src.managers.doc_template_engine import DocTemplateEngine
    from src.managers.ledger_event_manager import LedgerEventManager
    from src.managers.memory_manager import MemoryManager
    from src.managers.reminder_manager import ReminderManager
    from src.managers.roll_marker_store import RollMarkerStore
    from src.managers.session_manager import SessionManager
    from src.managers.telemetry_manager import TelemetryManager
    from src.managers.user_manager import UserManager
    from src.models.config import AppConfiguration

logger = logging.getLogger(__name__)

# Maximum inbound message length to prevent excessive API costs.
MAX_MESSAGE_LENGTH = 10000

# HTTP status codes the OpenAI SDK's own retry logic does NOT cover
# (openai._base_client.BaseClient._should_retry only retries 408/409/429/>=500,
# or an explicit `x-should-retry: true` response header - confirmed from the
# installed SDK's own source, not assumed) but that are worth one explicit
# retry here anyway. Currently just 424 (Failed Dependency) - seen live when
# OpenAI's own connector-proxy fails to fetch an attached MCP server's tool
# list before the model ever sees the conversation (real production/test
# investigation, 2026-09-30).
EXPLICIT_RETRY_STATUS_CODES = frozenset({424})

# The Morning MCP tools by kind (Feature 022/026). Writes (documents created or
# cancelled, client records added or changed) require explicit human approval on the
# legacy path; reads never do. Both sides are listed explicitly - confirmed empirically
# (2026-07-23, real E2E run) that a `require_approval` filter with ONLY an "always" key
# does NOT leave unlisted tools defaulting to no-approval (`download_invoice_pdf` still
# came back as a pending mcp_approval_request).
MORNING_WRITE_MCP_TOOLS = (
    "create_invoice",
    "create_transaction_account",
    "create_combo_document",
    "create_credit_note",
    "create_receipt",
    "create_combo_document_as_reference",
    "cancel_transaction_account",
    "add_client",
    "update_client",
)
MORNING_READ_MCP_TOOLS = (
    "list_invoices", "get_invoice_details", "get_financial_summary",
    "download_invoice_pdf", "list_clients", "get_client_details",
    "resolve_client_name",
)

RECALLED_MEMORIES_HEADER = "RECALLED MEMORIES (from past conversations):\n"

# WhatsApp reply length limit the reply is cut to (AIResponse.truncate_for_whatsapp).
WHATSAPP_MAX_REPLY_CHARS = 4000

# Phrases of a state-changing Morning confirmation ("issued", "marked paid",
# "cancelled", "added" - all "successfully").
_CONFIRMATION_PHRASES = ("הוצאה בהצלחה", "סומנה כשולמה", "בוטלה בהצלחה", "נוסף בהצלחה")

# Free-form affirmative replies recognized as approval of a pending write (Feature
# 022) - matched against the trimmed, casefolded message (or its leading token), not
# as a substring-anywhere check, to avoid false positives on unrelated longer sentences.
AFFIRMATIVE_REPLIES = {
    "yes", "yep", "yeah", "sure", "ok", "okay", "go ahead",
    "כן", "אישור", "בסדר", "אוקיי", "אוקי",
    # Feature 046: additional common Hebrew affirmatives - "מאשר"/"מאשרת" ("I
    # confirm", masc./fem.) plus "בטח"/"סבבה", not previously recognized.
    "מאשר", "מאשרת", "בטח", "סבבה",
    # bugfix-028 B1: the prompt itself ended "— לאשר?" while this set had only
    # "אישור", so the prompt invited a word the parser rejected. Live: the user
    # answered "לאשר" twice, got the identical prompt back twice, and gave up.
    # The prompt is now a closed question, but the word it used to invite must
    # still be understood.
    "לאשר",
}

# What was NOT done, by what the approved write was about (2026-10-01): a reminder
# write that never ran must not be reported as "no document was created".
_NOTHING_DONE = {
    "document": "לא נוצר שום מסמך",
    "client": "לא נוסף ולא עודכן שום לקוח",
    "reminder": "לא נוצרה, לא שונתה ולא נמחקה שום תזכורת",
}
_NOTHING_DONE_GENERIC = "לא בוצע שום שינוי"

_INVOICE_WRITE_TOOLS = frozenset((
    "create_invoice", "create_transaction_account", "create_combo_document",
    "create_credit_note", "create_receipt", "create_combo_document_as_reference",
    "cancel_transaction_account",
))
_CLIENT_WRITE_TOOLS = frozenset(("add_client", "update_client"))
_REMINDER_WRITE_TOOLS = frozenset(("create_reminder", "modify_reminder", "delete_reminder"))

_HEBREW_LETTER = re.compile(r"[א-ת]")


def _field(item: Any, name: str) -> Any:
    """`name` off a raw Responses API item (object) or an already-extracted dict."""
    return item.get(name) if isinstance(item, dict) else getattr(item, name, None)


def _arguments_signature(call: Any) -> str:
    """A call's arguments as one comparable string: a JSON string or dict both become
    sorted-key JSON, so the same arguments compare equal however they were carried."""
    raw = _field(call, "arguments")
    arguments = raw
    if isinstance(raw, str):
        try:
            arguments = json.loads(raw)
        except ValueError:
            return raw
    try:
        return json.dumps(arguments, sort_keys=True, ensure_ascii=False)
    except TypeError:
        return repr(arguments)


def _call_succeeded(call: Any) -> bool:
    """A call carrying an error, or a local tool whose output starts with "⚠️"/"error:",
    failed - it is an attempt, never an execution."""
    if _field(call, "error"):
        return False
    output = _field(call, "output")
    return not (isinstance(output, str) and output.startswith(("⚠️", "error:")))


@dataclass
class WriteExecutions:
    """What an approved turn executed: how many times each write tool was called
    (attempts, failed ones included), the arguments of each SUCCESSFUL call, and the
    first failure text any call carried (for telling the user why nothing ran)."""
    counts: Dict[str, int] = field(default_factory=dict)
    failure_detail: str = ""
    successful_arguments: Dict[str, List[str]] = field(default_factory=dict)

    @property
    def duplicated(self) -> List[str]:
        """Write tools that SUCCEEDED more than once with identical arguments - the
        signature of the same approved call being run twice (2026-10-04). Failed
        attempts, and deliberate writes with different arguments, never count."""
        return [name for name, signatures in self.successful_arguments.items()
                if len(signatures) != len(set(signatures))]

    @property
    def ran_any(self) -> bool:
        return bool(self.counts)


class AIManager(ABC):  # pylint: disable=too-many-instance-attributes,too-many-public-methods
    """The AI implementation DeniDin holds as `denidin.ai_manager`. See the module
    docstring. Every data object is owned by DeniDin and read through it; None is
    tolerated for each of them except `session_manager` (a DeniDin built with only
    what is exercised)."""

    # Memory system and RBAC are always on (2026-07-14 decision: both graduated
    # from feature flags to permanent behavior).
    memory_enabled = True
    rbac_enabled = True

    def __init__(self, denidin: Any):
        """`denidin`: the DeniDin object (REQ-063-08). Everything an implementation
        uses - config, the OpenAI client, the managers, the WhatsApp side - is read
        from it at use time, never copied. A manager DeniDin doesn't have (an external
        app's DeniDin) reads as None."""
        self.denidin = denidin

    # ------------------------------------------------------------------
    # DeniDin's objects, read through `denidin`
    # ------------------------------------------------------------------

    # Every object below is built by initialize_app; a DeniDin built without one (a
    # test, an external app) reads it as None - its first use then fails loudly, and the
    # turn's own error handling replies with the friendly fallback. memory_manager and
    # telemetry_manager are genuinely optional (None = feature off) and checked.

    @property
    def client(self) -> OpenAI:
        """DeniDin's OpenAI client."""
        return cast(OpenAI, self.denidin.ai_client)

    @property
    def config(self) -> "AppConfiguration":
        return cast("AppConfiguration", self.denidin.config)

    @property
    def session_manager(self) -> "SessionManager":
        return cast("SessionManager", getattr(self.denidin, "session_manager", None))

    @property
    def user_manager(self) -> Optional["UserManager"]:
        return cast(Optional["UserManager"], getattr(self.denidin, "user_manager", None))

    @property
    def memory_manager(self) -> Optional["MemoryManager"]:
        """None when long-term memory is disabled in config."""
        return cast(Optional["MemoryManager"], getattr(self.denidin, "memory_manager", None))

    @property
    def ledger_event_manager(self) -> "LedgerEventManager":
        return cast("LedgerEventManager", getattr(self.denidin, "ledger_event_manager", None))

    @property
    def reminder_manager(self) -> "ReminderManager":
        return cast("ReminderManager", getattr(self.denidin, "reminder_manager", None))

    @property
    def morning_mcp_locator(self) -> Optional["MorningMcpLocator"]:
        return cast(Optional["MorningMcpLocator"], getattr(self.denidin, "morning_mcp_locator", None))

    @property
    def roll_marker_store(self) -> Optional["RollMarkerStore"]:
        return cast(Optional["RollMarkerStore"], getattr(self.denidin, "roll_marker_store", None))

    @property
    def doc_template_engine(self) -> Optional["DocTemplateEngine"]:
        return cast(Optional["DocTemplateEngine"], getattr(self.denidin, "doc_template_engine", None))

    @property
    def fee_agreement_tools(self) -> "FeeAgreementToolHandler":
        return cast("FeeAgreementToolHandler", getattr(self.denidin, "fee_agreement_tools", None))

    @property
    def telemetry_manager(self) -> Optional["TelemetryManager"]:
        """None = telemetry off."""
        return cast(Optional["TelemetryManager"], getattr(self.denidin, "telemetry_manager", None))


    # ------------------------------------------------------------------
    # Per implementation
    # ------------------------------------------------------------------

    @abstractmethod
    def single_turn(self, request: AIRequest, chat_id: Optional[str] = None, *,
                    user_role: Optional[str] = None, sender: Optional[str] = None,
                    recipient: Optional[str] = None, user_phone: Optional[str] = None,
                    is_group: bool = False, chat_name: Optional[str] = None,
                    sender_phone: Optional[str] = None) -> AIResponse:
        """One inbound message -> one AIResponse (the reply, or a deliberate no-reply).
        user_phone is the RBAC phone; user_role is resolved from it when not given
        ('godfather' when it can't be). Every implementation takes exactly these
        parameters; a media turn's file travels on `request.media`."""

    @abstractmethod
    def resolve_button_tap(self, message: WhatsAppMessage, selected_id: str, stanza_id: str, *,
                           user_role: Optional[str] = None) -> Optional[AIResponse]:
        """A WhatsApp interactive-buttons tap (Feature 047). None for a stale tap -
        the caller then sends nothing at all."""

    @abstractmethod
    def record_sent_message_id(self, chat_id: str, message_id: str) -> None:
        """Called right after a reply is actually sent with its WhatsApp idMessage, so a
        later button tap on it can be matched (Feature 047's stale-tap guard)."""

    @abstractmethod
    def extraction_prompt_prefix(self) -> str:
        """Text the media extractors put in front of their own extraction prompt
        ("" for none)."""

    @abstractmethod
    def capture_ledger_events_from_text(self, text: str, today_timestamp: Optional[int] = None
                                        ) -> List[Dict]:
        """The media extractors' inline ledger capture over extracted text ([] for none)."""

    # ------------------------------------------------------------------
    # The request for an inbound message
    # ------------------------------------------------------------------

    def _request_constitution(self, user_prompt: str, chat_id: Optional[str],
                              user_phone: Optional[str]) -> str:
        """The AIRequest's `constitution` field. None by default - an implementation
        that carries its instructions on the request overrides this."""
        del user_prompt, chat_id, user_phone
        return ""

    def create_request(self, message: WhatsAppMessage, chat_id: Optional[str] = None,
                       user_role: str = 'client', user_phone: Optional[str] = None) -> AIRequest:
        """An AIRequest from a WhatsApp message: blocked-sender check (raises
        PermissionError), length cap. (Mentions of DeniDin's own number were already
        rewritten to "@DeniDin" when WhatsAppHandler parsed the message.)

        user_phone: the phone whose role governs the turn (a group's most-permissive
        member); message.sender_id when not given. user_role is unused (kept for the
        call-site shape; RBAC resolves the role from the phone)."""
        del user_role
        effective_chat_id = chat_id or message.chat_id
        effective_user_phone = user_phone or message.sender_id

        if self.rbac_enabled and self.user_manager:
            user = self.user_manager.get_user(effective_user_phone)
            if user.is_blocked:
                logger.warning(f"Blocked user attempted to create request: {effective_user_phone}")
                raise PermissionError(f"User is blocked: {effective_user_phone}")

        user_prompt = message.text_content
        if len(user_prompt) > MAX_MESSAGE_LENGTH:
            logger.warning(
                f"Message length {len(user_prompt)} exceeds maximum {MAX_MESSAGE_LENGTH} chars. "
                f"Truncating from sender {message.sender_name}"
            )
            user_prompt = user_prompt[:MAX_MESSAGE_LENGTH]

        request = AIRequest(
            user_prompt=user_prompt,
            constitution=self._request_constitution(user_prompt, effective_chat_id, effective_user_phone),
            max_tokens=self.config.ai_reply_max_tokens,
            model=self.config.ai_model,
            chat_id=message.chat_id,
            message_id=message.message_id,
            # Feature 024: the real Green API notification timestamp (a captured ledger
            # event's message_timestamp must be when the user sent it, not processing time).
            timestamp=message.timestamp,
            # 2026-08-19: the whole original message (see AIRequest.original_message).
            original_message=message,
        )
        logger.debug(f"Created AIRequest {request.request_id} for message {message.message_id}")
        return request

    # ------------------------------------------------------------------
    # Morning MCP
    # ------------------------------------------------------------------

    def morning_mcp_connection(self, correlation_id: Optional[str], role: Any
                               ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """(server_url, auth_token, mcp_config) for the Morning MCP server, or None
        (logged) when the server is unavailable or the auth token
        is not configured. Logs the REQ-SEC-002 audit line (role, URL host, masked
        token) on success."""
        locator = self.morning_mcp_locator
        server_url = locator.current_server_url() if locator is not None else None
        if not server_url:
            logger.warning("Morning MCP server unavailable - proceeding without invoicing tools")
            return None

        mcp_config = getattr(self.config, 'mcp', {}) or {}
        auth_token = mcp_config.get('morning_auth_token')
        if not auth_token:
            logger.warning("mcp.morning_auth_token not configured - proceeding without invoicing tools")
            return None

        masked_token = f"{auth_token[:4]}...{auth_token[-4:]}" if len(auth_token) > 8 else "***"
        logger.info(
            f"Attaching Morning MCP tools for request={correlation_id}, role={role}, "
            f"url_host={server_url.split('/')[2] if '//' in server_url else server_url}, "
            f"token={masked_token}"
        )
        return server_url, auth_token, mcp_config

    @staticmethod
    def morning_mcp_entry(connection: Tuple[str, str, Dict[str, Any]], *, server_label: str,
                          require_approval: Any, allowed_tools: Optional[List[str]] = None
                          ) -> Dict[str, Any]:
        """One Responses API `tools` entry registering the Morning MCP server as a
        remote tool, for a connection from morning_mcp_connection."""
        server_url, auth_token, _mcp_config = connection
        entry: Dict[str, Any] = {
            "type": "mcp",
            "server_label": server_label,
            "server_url": server_url,
        }
        if allowed_tools is not None:
            entry["allowed_tools"] = list(allowed_tools)
        entry["require_approval"] = require_approval
        entry["headers"] = {"Authorization": f"Bearer {auth_token}"}
        return entry

    # ------------------------------------------------------------------
    # Model calls (explicit retry + Feature 080 telemetry)
    # ------------------------------------------------------------------

    @staticmethod
    def call_model_with_retry(call_fn: Callable[[], Any], *, context: str,
                              max_retries: int = 1, backoff_seconds: float = 2.0) -> Any:
        """Calls call_fn() (a responses.create(**kwargs) invocation), retrying once
        (by default) on an APIStatusError whose status_code is in
        EXPLICIT_RETRY_STATUS_CODES - a gap the OpenAI SDK's own max_retries never
        covers. Any other exception, or a retryable one that still fails after
        max_retries, propagates unchanged."""
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

    @staticmethod
    def build_fallback_response(request_id: str, message: str) -> AIResponse:
        """The AIResponse both implementations return when their top-level try/except
        catches something unexpected."""
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

    @classmethod
    def timed_model_call(cls, builder: Optional[Any], call_fn: Callable[[], Any], *, context: str) -> Any:
        """The timed responses.create() call (Feature 080, REQ-080-04): call_fn runs
        through call_model_with_retry; the call is timed and recorded into `builder` on
        success AND failure alike (a timed-out/errored call still consumed wall-clock
        time), the call's own exception propagating unchanged. Recording is a no-op when
        `builder` is None; the retry always applies."""
        def retrying_call_fn():
            return cls.call_model_with_retry(call_fn, context=context)
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

    @staticmethod
    @contextlib.contextmanager
    def tool_call_span(builder: Optional[Any], tool_name: str, *, is_morning_tool: bool = False):
        """Tool-call timing (Feature 080, contracts/telemetry-recorder.md's
        record_tool_call()): times the wrapped block, success or exception alike, and
        records it into `builder`; a complete no-op when `builder` is None. A telemetry
        failure is logged, never raised."""
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

    @classmethod
    def timed_tool_call(cls, builder: Optional[Any], tool_name: str, call_fn: Callable[[], Any], *,
                        is_morning_tool: bool = False) -> Any:
        """call_fn() inside tool_call_span - the function form of the same timing."""
        with cls.tool_call_span(builder, tool_name, is_morning_tool=is_morning_tool):
            return call_fn()

    @classmethod
    def record_mcp_tool_calls(cls, builder: Optional[Any], mcp_calls: List[Dict[str, Any]]) -> None:
        """Records each of a turn's Morning MCP calls (Feature 080) for the
        tool_calls_count/morning_api_request_times_ms breakdown. Duration is
        deliberately ~0: OpenAI runs a remote MCP call server-side, INSIDE
        responses.create() (already timed as an LLM call). A no-op when `builder`
        is None."""
        if builder is None:
            return
        for call in mcp_calls:
            cls.timed_tool_call(builder, call["name"], lambda: None, is_morning_tool=True)

    @contextlib.contextmanager
    def telemetry_span(self, request_id: str, effective_chat_id: str):
        """The turn-level telemetry lifecycle (Feature 080, REQ-080-04): yields one
        TelemetryBuilder for the turn and records the finished RequestTelemetry row on
        the way out - success OR exception alike. Yields None and is a complete no-op
        when there is no telemetry_manager."""
        if self.telemetry_manager is None:
            yield None
            return
        from src.managers.telemetry_manager import TelemetryBuilder  # pylint: disable=import-outside-toplevel
        builder = TelemetryBuilder(request_id, effective_chat_id, now_local().isoformat())
        try:
            yield builder
        finally:
            try:
                record = builder.finalize(now_local().isoformat())
                self.telemetry_manager.record(record)
            except Exception as telemetry_error:  # pylint: disable=broad-except
                logger.warning("Feature 080 telemetry finalize/record failed: %s", telemetry_error)

    def single_prompt_text(self, *, model: str, prompt: str, max_output_tokens: int,
                           context: str) -> str:
        """One standalone, tool-less, session-less text call (Item17, 2026-10-01) - for
        a helper analysis that is not a conversational turn (the DOCX reader's document
        analysis). Wire-logged both directions, with the explicit retry. Returns the
        reply text ("" when there is none); exceptions propagate to the caller."""
        from src.utils.wire_log import audit_wire, debug_wire  # pylint: disable=import-outside-toplevel
        kwargs: Dict[str, Any] = {"model": model, "input": prompt, "max_output_tokens": max_output_tokens}
        audit_wire("openai", "out", context, kwargs)
        debug_wire("openai", "out", context, kwargs)
        response = self.call_model_with_retry(lambda: self.client.responses.create(**kwargs), context=context)
        audit_wire("openai", "in", context, response)
        debug_wire("openai", "in", context, response)
        return (getattr(response, "output_text", "") or "").strip()

    # ------------------------------------------------------------------
    # Per-turn context: the rolling window and long-term memory recall
    # ------------------------------------------------------------------

    def load_rolling_window(self, chat_id: Optional[str], *, window_days: int, max_tokens: int,
                            exclude_message_ids: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Feature 070: the chat's rolling verbatim window (oldest-first
        {"role", "content"} dicts, trimmed oldest-first to `max_tokens`, read-only).
        `exclude_message_ids`: the current turn's own inbound message (already stored on
        receipt) - the caller sends it to the model explicitly as the turn's input.
        Returns [] - never raises - when there's no session manager/chat or the read
        fails: a turn with no history is degraded, not crashed."""
        if not (self.session_manager and chat_id):
            return []
        try:
            history = self.session_manager.get_rolling_window(
                chat_id, window_days=window_days, max_tokens=max_tokens,
                exclude_message_ids=[m for m in (exclude_message_ids or []) if m],
            )
            if history:
                logger.info(f"Retrieved {len(history)} messages from session history")
            return list(history) if history else []
        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"Failed to retrieve conversation history: {e}", exc_info=True)
            return []

    def recall_memory_context(self, *, query: str, chat_id: Optional[str], top_k: int,
                              min_similarity: float, user_phone: Optional[str] = None) -> str:
        """One semantic-similarity recall over this chat's `daily_summary`
        collection, formatted as the RECALLED MEMORIES block (header + one
        "- <content> (relevance: 0.NN)" line per memory). RBAC-filtered by the
        user's allowed_memory_scopes/can_see_all_memories when there is a
        user_manager and a `user_phone`, else a plain recall. Returns "" - never
        raises - when there's no query (e.g. a media message without a caption),
        nothing relevant is found, or recall fails."""
        if self.memory_manager is None or not chat_id or not query:
            return ""
        try:
            collection_name = collection_name_for_chat(chat_id)
            if self.user_manager is not None and user_phone:
                user = self.user_manager.get_user(user_phone)
                recalled = self.memory_manager.recall_with_rbac_filter(
                    query=query,
                    collection_names=[collection_name],
                    user_phone=user_phone,
                    allowed_scopes=user.allowed_memory_scopes,
                    can_see_all_memories=user.can_see_all_memories,
                    top_k=top_k,
                    min_similarity=min_similarity,
                )
            else:
                recalled = self.memory_manager.recall(
                    query=query,
                    collection_names=[collection_name],
                    top_k=top_k,
                    min_similarity=min_similarity,
                )
            if not recalled:
                return ""
            logger.info(f"Recalled {len(recalled)} memories for {chat_id}")
            return RECALLED_MEMORIES_HEADER + "".join(
                f"- {mem['content']} (relevance: {mem['similarity']:.2f})\n" for mem in recalled
            )
        except Exception as e:  # pylint: disable=broad-except
            logger.error(f"Failed to recall memories: {e}", exc_info=True)
            return ""

    # ------------------------------------------------------------------
    # Turn results
    # ------------------------------------------------------------------

    @staticmethod
    def extract_mcp_call_items(response) -> List[Dict[str, Any]]:
        """Every `mcp_call` item on one API response's `.output`, as
        {name, error, arguments, output}.

        `error` is normalized to a plain string (2026-09-15, real billed failure): on a
        network-level failure (e.g. a 503 from the MCP tunnel) the SDK's `item.error` can
        be a raw exception object (`HTTPError(...)`), which later crashed message storage
        (`json.dump` -> `TypeError`). Normalized once, here, at the boundary."""
        return [
            {
                "name": item.name,
                "error": str(item.error) if item.error is not None else None,
                "arguments": item.arguments,
                "output": item.output,
            }
            for item in (getattr(response, "output", None) or [])
            if getattr(item, "type", None) == "mcp_call"
        ]

    @staticmethod
    def finish_reason_of(response) -> str:
        """The Responses API has no per-choice finish_reason: "stop", unless the
        response carries incomplete_details, then its reason (or "incomplete")."""
        incomplete = getattr(response, "incomplete_details", None)
        if incomplete is not None:
            return getattr(incomplete, "reason", None) or "incomplete"
        return "stop"

    @staticmethod
    def fit_for_whatsapp(ai_response: AIResponse) -> AIResponse:
        """The reply cut to WhatsApp's limit (AIResponse.truncate_for_whatsapp) when it
        is longer, logged; otherwise unchanged."""
        if len(ai_response.response_text) > WHATSAPP_MAX_REPLY_CHARS:
            logger.warning("Response truncated to %d chars for WhatsApp", WHATSAPP_MAX_REPLY_CHARS)
            return ai_response.truncate_for_whatsapp()
        return ai_response

    @staticmethod
    def reply_or_fallback(text: str, fallback: str) -> str:
        """The reply text, or `fallback` when there is none (Item7, 2026-10-01): a turn
        the user sent something to is never left silent by accident. A deliberate
        [[NO_REPLY]] is non-empty text, so it passes through unchanged."""
        return (text or "").strip() or fallback

    @staticmethod
    def log_possible_hallucinated_confirmation(request_id: str, response_text: str,
                                                tools_offered: bool,
                                                mcp_calls: List[Dict[str, Any]]) -> None:
        """Detection safety net, log only: tools were offered this turn and the reply
        reads like a state-changing Morning confirmation, but no MCP call was made - the
        model may have pattern-completed a fabricated success from earlier turns."""
        if mcp_calls or not tools_offered:
            return
        if any(phrase in (response_text or "") for phrase in _CONFIRMATION_PHRASES):
            logger.warning(
                f"Possible hallucinated invoicing confirmation for request "
                f"{request_id}: reply text suggests a state-changing "
                f"action succeeded, but no MCP tool was called. "
                f"Reply: {response_text!r}"
            )

    # ------------------------------------------------------------------
    # Approved-write safeguards (Item4, 2026-10-01): recognizing a yes to an approval
    # prompt, and checking what an approved turn actually executed - the approved write
    # ran more than once (every execution already happened server-side), or never ran
    # at all (bugfix-028 B4(b)).
    # ------------------------------------------------------------------

    @staticmethod
    def is_affirmative_reply(text: str) -> bool:
        """Whether `text` reads as a yes to a pending approval - matched as the whole
        trimmed message or its leading token, not a substring-anywhere check.

        bugfix-028 B2: the leading token is the first RUN OF WORD CHARACTERS, not the
        first whitespace-split token, because WhatsApp prefixes RTL text with Unicode
        bidi controls (U+200F and friends) that are not whitespace. Anchoring on the
        FIRST word still refuses "לא נכון, אל תפיק"."""
        normalized = (text or "").strip().casefold()
        if not normalized:
            return False
        if normalized in AFFIRMATIVE_REPLIES:
            return True
        leading_match = re.search(r"\w+", normalized, flags=re.UNICODE)
        if leading_match is None:
            return False
        return leading_match.group(0) in AFFIRMATIVE_REPLIES

    @staticmethod
    def mcp_error_text(call: Any) -> str:
        """Human-readable failure text off an `mcp_call` item's `.error` (2026-08-12):
        a failed Morning tool call has `output=None` and an error shaped
        `{"type": "mcp_tool_execution_error", "content": [{"type": "text", "text": ...}]}`.
        A plain-string error is returned as-is."""
        error = _field(call, "error")
        if not error:
            return ""
        if isinstance(error, str):
            return error
        content = error.get("content") if isinstance(error, dict) else getattr(error, "content", None)
        if not content:
            return ""
        for block in content:
            text = block.get("text") if isinstance(block, dict) else getattr(block, "text", None)
            if text:
                return str(text)
        return ""

    @classmethod
    def tally_write_executions(cls, calls: Iterable[Any], write_tool_names: Iterable[str]
                               ) -> WriteExecutions:
        """Counts executions of each tool in `write_tool_names` among `calls` (raw
        `mcp_call` items or {name, arguments, output, error} dicts), and records the
        arguments of each successful one (WriteExecutions.duplicated). The failure detail is taken
        from the first call of ANY name that carries output or error text, cut to 200
        characters."""
        names = set(write_tool_names)
        result = WriteExecutions()
        for call in calls:
            name = _field(call, "name")
            if name in names:
                result.counts[name] = result.counts.get(name, 0) + 1
                if _call_succeeded(call):
                    result.successful_arguments.setdefault(name, []).append(_arguments_signature(call))
            if not result.failure_detail:
                output = _field(call, "output")
                if output:
                    result.failure_detail = f" ({str(output)[:200]})"
                else:
                    error_text = cls.mcp_error_text(call)
                    if error_text:
                        result.failure_detail = f" ({error_text[:200]})"
        return result

    @staticmethod
    def write_subject(tool_names: Iterable[str]) -> str:
        """"document" / "client" / "reminder" when every one of `tool_names` (the writes
        the approval could have been about) is of that one kind; "" when mixed or none."""
        kinds = set()
        for name in tool_names:
            if name in _INVOICE_WRITE_TOOLS:
                kinds.add("document")
            elif name in _CLIENT_WRITE_TOOLS:
                kinds.add("client")
            elif name in _REMINDER_WRITE_TOOLS:
                kinds.add("reminder")
        return kinds.pop() if len(kinds) == 1 else ""

    @staticmethod
    def approved_write_not_run_message(failure_detail: str, subject: str = "") -> str:
        """The reply when the user approved a write and it never ran (bugfix-028 B4(b)).
        Hebrew only: the failure detail (a tool's own output/error text) is shown only
        when it is Hebrew text, never raw English/JSON. `subject` (write_subject) names
        what was not done."""
        detail = failure_detail if _HEBREW_LETTER.search(failure_detail or "") else ""
        nothing_done = _NOTHING_DONE.get(subject, _NOTHING_DONE_GENERIC)
        return (f"אישרת, אבל הפעולה לא בוצעה בפועל{detail}. "
                f"{nothing_done}. נסי שוב או ספרי לי איך להמשיך.")
