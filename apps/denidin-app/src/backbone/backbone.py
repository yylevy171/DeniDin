"""
Backbone (Feature 063) — the new, standalone module implementing the
Backbone-as-tool-backbone-kernel architecture, and the one AI implementation: built at
startup by `denidin.py::initialize_app` (Feature 067 removed the legacy AIHandler and the flag).

See contracts/capability-resolution-loop.md (the loop) and contracts/prompt-assembly.md
(the prompt-loading/caching + per-call instructions assembly this module implements).
"""
import contextlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union


from src.backbone.backbone_tools import (
    BACKBONE_TOOLS,
    extract_backbone_tool_calls,
)
from src.backbone.capability_tags import ALWAYS_PRESENT_CAPABILITIES, CapabilityTag, capability_catalog_text
from src.backbone.flow_tags import FlowTag, flow_catalog_text
from src.backbone.loading import apply_loading, describe_loading, parse_requested
from src.backbone.pending_messages import format_pending_items
from src.backbone.prompt_cache import MtimePromptCache
from src.backbone.resolution_tools import RESOLUTION_TOOLS, extract_resolution_tool_calls
from src.capabilities.toolsets import (
    build_capability_tools,
    dispatch_local_tool,
    extract_local_calls,
    local_tool_owners,
)
from openai import APIError, APITimeoutError, BadRequestError, RateLimitError

from src.constants.error_messages import (
    BACKBONE_AI_API_ERROR, BACKBONE_AI_RATE_LIMITED, BACKBONE_AI_TIMEOUT, BACKBONE_UNEXPECTED_ERROR,
)
from src.models.message import AIRequest, AIResponse, WhatsAppMessage
from src.models.user import Role
from src.utils.capability_audit_log import log_capability_action, log_loading_action
from src.utils.logger import read_version, DEFAULT_VERSION_FILE
from src.tool_actions.messaging_actions import build_react_to_message_payload
from src.core.ai_manager import AIManager
from src.utils.wire_log import audit_wire, debug_wire
from src.utils.time_utils import now_local, local_from_timestamp
from src.utils.allocation_threshold import fill_allocation_threshold

logger = logging.getLogger(__name__)


# A generous bound, never expected to bind in practice, existing purely so a
# pathological back-and-forth can't loop forever. Raised 10 -> 100 (2026-09-28)
# after the mandatory-every-interaction send_progress_update wording pushed
# ordinary multi-step turns (e.g. a ledger query needing two searches) past
# the old cap of 10, which silently dropped a genuinely-produced final
# send_to_user answer - see the loop-cap fallback's own known bug noted below.
MAX_BACKBONE_TOOL_LOOP_ITERATIONS = 100

# The backbone flows: the flows shown in the backbone's own "## Flows" catalog.
# Every other flow is reached only through a flow that offers it (the Morning
# document flows through flow_morning_document_write). Flows themselves don't
# know who loads them, and load_flows still accepts any flow.
BACKBONE_FLOWS: Tuple[FlowTag, ...] = (
    FlowTag.ADD_CLIENT,
    FlowTag.MODIFY_CLIENT,
    FlowTag.MORNING_DOCUMENT_WRITE,
    FlowTag.FEE_AGREEMENT_PROVIDED_BY_USER,
    FlowTag.DEPOSIT_PROVIDED_BY_USER,
    FlowTag.USER_QUESTION,
    FlowTag.INVOICING_QUERY,
    FlowTag.GENERATE_FEE_AGREEMENT_DOCX,
    FlowTag.CREATE_REMINDER,
    FlowTag.MODIFY_REMINDER,
    FlowTag.AGREEMENT_MANAGEMENT,
)

# Information reaches the user ONLY through tools (send_to_user, approval_with_yes_no_buttons,
# ...). Output text is ignored - logged, never sent. A response that is plain text with no tool
# call gets this one note and another call; if the model does it again, the app pauses.
PLAIN_TEXT_IGNORED_NOTE = (
    "Your last output text was IGNORED: output text is never shown to the user and never acted on. "
    "Information reaches the user ONLY through tools - call send_to_user to say something (or "
    "approval_with_yes_no_buttons for a yes/no question). If you have nothing to do right now, "
    "respond with nothing at all."
)

# The Morning tools that create a document - each success is recorded in the ledger by the
# app (DeniDin.record_created_document), never by the model.
DOCUMENT_CREATING_TOOLS = frozenset({
    "create_invoice", "create_transaction_account", "create_combo_document", "create_credit_note",
    "create_receipt", "create_combo_document_as_reference",
})

# OpenAI's error code for a previous_response_id it no longer knows (Gate Zero C4).
CHAIN_NOT_FOUND_CODE = "previous_response_not_found"

# English label per MediaFileManager.validate_format result, used in the
# first-round "[ATTACHED MEDIA: ...]" marker of a media turn.
MEDIA_TYPE_LABELS = {"image": "image", "pdf": "PDF", "docx": "Word document"}

_DEFAULT_BACKBONE_CONFIG = {
    "file": "backbone.md",
    "base_dir": "config",
    "prompts_dir": "prompts",
    "capabilities_dir": "capabilities",
}


class Backbone(AIManager):  # pylint: disable=too-many-instance-attributes
    """The backbone kernel - the AI implementation (REQ-063-08). DeniDin's Shared
    Managers are handed in (AIManager's keyword arguments), never built here."""

    def __init__(self, denidin: Any):
        super().__init__(denidin)
        config = self.config
        # The telemetry builder of the turn in progress (set in handle_message).
        self._turn_telemetry_builder: Optional[Any] = None
        # _app_version (2026-09-17, closing a real gap found by direct user
        # review: build_instructions never told the model its own version at
        # all, unlike AIHandler._load_constitution's "YOUR CURRENT VERSION
        # IS..." line - under the backbone, "what version are you running?"
        # had no way to be answered. Same source (read_version against
        # DEFAULT_VERSION_FILE), read once at construction, mirroring
        # AIHandler's own self._app_version.
        self._app_version = read_version(DEFAULT_VERSION_FILE)

        backbone_config = dict(_DEFAULT_BACKBONE_CONFIG)
        backbone_config.update(config.backbone_config or {})
        self._backbone_config = backbone_config

        # This turn's own record_planning_status output (2026-09-16) - the ONLY
        # new persisted cross-turn state the resolution redesign adds: a plain
        # internal-note history entry, threaded back into the next turn purely
        # via the existing rolling-window conversation history (no new store, no
        # schema). Reset every turn in handle_message.
        self._turn_planning_status: Optional[str] = None

        self._backbone_content: str = ""
        self._backbone_mtime: Optional[float] = None
        self._capability_prompts = MtimePromptCache("capability", self._capabilities_dir)
        self._flow_prompts = MtimePromptCache("flow", self._flows_dir)
        # Context sections code adds by turn type (Item14, 2026-10-01): today only
        # group_etiquette.md, for a group chat.
        self._context_prompts = MtimePromptCache("context", self._prompts_dir)
        self._user_memory_content: str = ""
        self._user_memory_mtime: Optional[float] = None

        # Set once per handle_message() call, read by the resolution loop for
        # every round within that SAME turn (2026-09-14). Deliberately a plain
        # instance attribute, not threaded as an explicit parameter through
        # every one of the ~6 call sites across src/capabilities/* + planning.py
        # - this process handles one webhook turn at a time, so there is no real
        # concurrent-turn clobbering risk in practice.

        # Set once per handle_message() call, same lifecycle/reasoning as
        # _turn_conversation_history above - read by the loop's
        # backbone-tool resolution (send_progress_update/react_to_message) for
        # every round this turn makes.
        self._turn_chat_id: Optional[str] = None
        self._turn_message_id: Optional[str] = None
        self._turn_request_id: str = ""

        # What this handle_message() call did, for observability (denidin_app.last_response):
        # the texts it sent, and whether any went out as approval buttons. Nothing waits on
        # these and nothing is delivered from them - every send happens the moment the model
        # calls the tool.
        self._turn_sent_texts: List[str] = []
        self._turn_offered_approval: bool = False

        # Set once per handle_message() call (2026-09-15) - the ChromaDB
        # daily_summary semantic recall for this turn's own query, appended into
        # every round's instructions the same way AIHandler appends it to
        # `constitution` (see _recall_memory's own docstring for the exact
        # parity call this mirrors). "" when memory_manager is None/recall fails/
        # nothing relevant found - never blocks the turn.
        self._turn_memory_context: str = ""

        # Accumulates every real Morning MCP tool call made by any round this
        # turn (2026-09-15) - same {"name","error","arguments","output"} shape
        # AIHandler._finalize_response already extracts (REQ-SEC-002 audit
        # logging parity) - threaded into the returned AIResponse.mcp_calls so
        # the post-turn ledger-recognition hook (denidin.py's shared
        # _run_post_turn_ledger_recognition) sees this turn's real Morning
        # activity under the flag-on path too, not an empty list.
        self._turn_mcp_calls: List[Dict[str, Any]] = []

        # This turn's token usage summed over every model call, and the last call's
        # response (its model/finish reason are the turn's) - reported on the returned
        # AIResponse exactly as AIHandler reports them (2026-10-01).
        self._turn_tokens = [0, 0, 0]  # total, input (prompt), output (completion)
        self._turn_last_response: Optional[Any] = None

        # True when this message answers an approval-buttons prompt with a yes. An approval
        # asks about WHATEVER the model asked (a write, an offer, any question) - the app never
        # assumes it was a write. The model calls are run with the SDK's own retries off (as
        # legacy's approval call) and nothing is attached to the model's input while it handles
        # the approved action (REQ-RMH-014).
        self._turn_answers_approval: bool = False

        # The inbound WhatsAppMessage this turn answers (request.original_message) -
        # the addressing for internal notes stored mid-turn (see record_planning_status).
        self._turn_original_message: Optional[Any] = None

        # Which capabilities are loaded is NOT per-turn instance state - it lives
        # in Session.active_capabilities (persisted with the session on every
        # change; see _get_active_tags/_set_active_tags).

    # ------------------------------------------------------------------
    # Prompt loading/caching (contracts/prompt-assembly.md)
    # ------------------------------------------------------------------

    def _base_dir(self) -> Path:
        return Path(self._backbone_config.get("base_dir", "config"))

    def _prompts_dir(self) -> Path:
        return self._base_dir() / self._backbone_config.get("prompts_dir", "prompts")

    def _capabilities_dir(self) -> Path:
        return self._prompts_dir() / self._backbone_config.get("capabilities_dir", "capabilities")

    def _flows_dir(self) -> Path:
        return self._prompts_dir() / self._backbone_config.get("flows_dir", "flows")

    def load_backbone(self) -> str:
        """Loads config/prompts/backbone.md via an mtime cache (mirrors
        AIHandler._load_constitution's existing pattern, reimplemented here)."""
        backbone_path = self._prompts_dir() / self._backbone_config.get("file", "backbone.md")
        try:
            mtime = backbone_path.stat().st_mtime
        except FileNotFoundError:
            logger.warning("Backbone file not found at %s", backbone_path)
            return self._backbone_content or ""

        if self._backbone_mtime is None or mtime != self._backbone_mtime:
            self._backbone_content = backbone_path.read_text(encoding="utf-8")
            self._backbone_mtime = mtime
        return self._backbone_content

    def load_user_memory(self) -> str:
        """Loads config/prompts/user_memory.md (2026-09-14, forward-looking
        placeholder - empty content today, no user-defined-memory feature exists
        yet). Same mtime-cache pattern as load_backbone; a missing file is
        tolerated the same way (empty string, WARNING logged) rather than
        treated as an error - this section is optional by design."""
        memory_path = self._prompts_dir() / "user_memory.md"
        try:
            mtime = memory_path.stat().st_mtime
        except FileNotFoundError:
            return self._user_memory_content or ""

        if self._user_memory_mtime is None or mtime != self._user_memory_mtime:
            self._user_memory_content = memory_path.read_text(encoding="utf-8")
            self._user_memory_mtime = mtime
        return self._user_memory_content

    def load_capability_prompt(self, tag: CapabilityTag) -> str:
        """Independent mtime cache per capability tag (see MtimePromptCache)."""
        return self._capability_prompts.get(tag.value)

    def load_flow_prompt(self, tag: FlowTag) -> str:
        """Independent mtime cache per flow tag, same contract as
        load_capability_prompt."""
        return self._flow_prompts.get(tag.value)

    def build_instructions(self, active_tags: Union[None, CapabilityTag, List[CapabilityTag]],
                            accumulated_context: str = "",
                            today_timestamp: Optional[int] = None,
                            *, active_flows: Optional[List[FlowTag]] = None,
                            is_group: bool = False) -> str:
        """contracts/prompt-assembly.md's fixed assembly order:
        backbone + the always-present capabilities' prompts (fixed order) + flow
        catalog + capability catalog + EVERY loaded flow's blueprint + EVERY loaded
        capability's prompt (a growing set each) +
        "Loaded flows"/"Loaded capabilities" lines +
        accumulated_context + recalled memory + '---' + today (memory
        deliberately last among the dynamic parts - see the inline comment
        above its append call for why). `active_tags` may be None (plain
        backbone), one tag, or a list.

        Date AND time (not date alone) - mirrors AIHandler._load_constitution's own
        current-date-and-time injection: without a current TIME, the model cannot
        resolve a relative clock offset ("תזכיר לי בעוד שעה") and asks the user what
        time it is instead of just computing it - a real gap the legacy code already
        fixed once for Feature 054 (reminders), confirmed via a real billed-test
        failure (2026-09-14, this backbone regressed on it by injecting only the
        date - same billed test caught it here too).
        """
        now = local_from_timestamp(today_timestamp) if today_timestamp else now_local()
        # Capability catalog: every capability's name + one-line description,
        # authored once in capability_tags.py, rendered here as part of the same
        # stable instructions prefix every call shares. Godfather/Admin-only
        # scope for now (client role is out of scope), so the full catalog is
        # always shown unconditionally.
        catalog = capability_catalog_text(list(CapabilityTag))
        if active_tags is None:
            tags: List[CapabilityTag] = []
        elif isinstance(active_tags, CapabilityTag):
            tags = [active_tags]
        else:
            tags = list(active_tags)
        # Loaded flows/capabilities render in CANONICAL order (enum order), never
        # load order, so the same set always yields the same bytes (cache hits).
        flows = sorted(set(active_flows or []), key=list(FlowTag).index)
        tags = sorted(set(tags), key=list(CapabilityTag).index)
        flow_catalog = flow_catalog_text(list(BACKBONE_FLOWS))
        loaded_line = (
            "## Loaded flows\n\n" + (", ".join(f.value for f in flows) if flows else "(none)")
            + "\n\n## Loaded capabilities\n\n"
            + (", ".join(t.value for t in tags) if tags else "(none - plain backbone)")
        )
        parts = [
            self.load_backbone(),
            *[self._capability_prompts.get(name) for name in ALWAYS_PRESENT_CAPABILITIES],
            # Group chats only (Item14): the code knows whether this is a group; the
            # section is never shown in a 1:1 chat.
            self._context_prompts.get("group_etiquette") if is_group else "",
            f"## Flows\n\n{flow_catalog}" if flow_catalog else "",
            f"## Capabilities\n\n{catalog}" if catalog else "",
            *[self.load_flow_prompt(f) for f in flows],
            *[self.load_capability_prompt(t) for t in tags],
            loaded_line,
            self.load_user_memory(),
        ]
        if accumulated_context:
            parts.append(accumulated_context)
        # Memory recall varies per query/chat, so it goes AFTER all capability
        # content, next to the other turn-varying part (accumulated_context), right
        # before the date suffix - REQ-063-06: the stable backbone + always-present
        # + capability prefix must stay byte-identical across turns to hit the cache.
        if self._turn_memory_context:
            parts.append(self._turn_memory_context)
        parts.append("---")
        parts.append(
            f"THE CURRENT DATE AND TIME IS {now.strftime('%Y-%m-%d')} {now.strftime('%H:%M')} "
            f"(Asia/Jerusalem, Israel local time). Treat this as the authoritative \"now\" when "
            f"resolving any relative or partial date/time the user gives (a day/month with no "
            f"year, \"היום\", \"אתמול\", \"בעוד שעה\", \"בעוד חצי שעה\", etc.) — never fall back "
            f"on a year from your training data, and never ask the user what time it is now.\n"
            f"YOUR CURRENT VERSION IS {self._app_version}. If asked what version you are "
            f"running (in any language), state this exact value."
        )
        # Feature 098: {{ALLOCATION_THRESHOLD_NIS}} may appear in any capability or
        # flow prompt, so it is filled once here, on the assembled text.
        return fill_allocation_threshold(
            "\n\n".join(part for part in parts if part), self.config.allocation_threshold_nis
        )

    # ------------------------------------------------------------------
    # MCP call extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_mcp_call_items(response) -> List[Dict[str, Any]]:
        """Pulls every `mcp_call`-type item off one API response's `.output` - same
        shape/reasoning as AIHandler._extract_mcp_call_items (this session's earlier
        fix for the identical bug class in the legacy dispatch loop), reimplemented
        here as new code (REQ-063-07). 2026-10-01: the shared
        AIManager.extract_mcp_call_items (also AIHandler's) - it normalizes
        `error` to a string, which this copy did not (a raw HTTPError crashed message
        storage on the legacy path once, 2026-09-15)."""
        return AIManager.extract_mcp_call_items(response)

    # ------------------------------------------------------------------
    # The resolution loop (contracts/capability-resolution-loop.md)
    # ------------------------------------------------------------------

    def handle_message(  # pylint: disable=too-many-locals
            self, request: AIRequest, chat_id: Optional[str] = None, *,
            user_role: Optional[str] = None, sender: Optional[str] = None,
            recipient: Optional[str] = None, user_phone: Optional[str] = None,
            is_group: bool = False, chat_name: Optional[str] = None,
            sender_phone: Optional[str] = None) -> AIResponse:
        """The backbone's AIManager.handle_message (REQ-063-08): resolves one WhatsApp turn
        (one incoming message → one final reply) via one or more OpenAI call "rounds" -
        see `_call_model`'s "first round"/"follow-up round" context labels: a turn is
        NOT guaranteed to be a single OpenAI call, since the model may spend a round
        loading a flow/capability before it can actually answer.

        user_role: None (denidin.py's call) resolves it from user_phone (else
        sender_phone) off DeniDin's UserManager - 'godfather' when unknown.

        A media turn (REQ-063-04a) carries its file on `request.media` - the RAW, not-yet-
        extracted bytes: denidin.py's flag-on media dispatch downloads and validates the
        file and hands it here WITHOUT running any extraction call first. The model is told
        only "media attached, type X, caption Y" - no content - and itself loads
        `cap_media_analysis` and calls its `analyze_media` tool; only then does
        `src/capabilities/media_analysis/handler.py` run the real vision/PDF/DOCX
        extraction on `turn_context["media"]`.
        """
        # The ENTIRE turn below is wrapped in one top-level try/except, mirroring
        # AIHandler._get_response_impl's own APITimeoutError/RateLimitError/
        # APIError/Exception -> friendly fallback safety net: anything that raises
        # (memory recall, session persistence, finalize, a model call) replies
        # with a friendly fallback instead of crashing the turn.
        # Feature 080 telemetry (2026-09-15, closing a real gap - see __init__'s
        # telemetry_manager docstring), 2026-09-30 consolidation: the telemetry
        # lifecycle itself (one TelemetryBuilder per turn, recorded on the way out -
        # success OR exception alike, complete no-op when self.telemetry_manager is
        # None) is now the ONE shared AIManager.telemetry_span
        # implementation, also used by AIHandler.handle_message - the two were
        # byte-for-byte identical in shape before this change, just stored the
        # active builder differently (this class's own instance attribute vs.
        # AIHandler's module-level contextvar), which telemetry_span is agnostic to.
        if user_role is None:
            # REQ-063-08: the role RBAC gates on is resolved here, off DeniDin's own
            # UserManager (user_phone is the RBAC phone - the group's most-permissive
            # member for a group turn), never by the caller.
            user_role = self._role_for_phone(user_phone or sender_phone)
        effective_chat_id_for_telemetry = chat_id or request.chat_id
        with self.telemetry_span(request.request_id, effective_chat_id_for_telemetry) as builder:
            self._turn_telemetry_builder = builder
            return self._handle_message_body(
                request, chat_id=chat_id, user_role=user_role, sender=sender, recipient=recipient,
                user_phone=user_phone, is_group=is_group, chat_name=chat_name, sender_phone=sender_phone,
            )

    def _role_for_phone(self, phone: Optional[str]) -> str:
        """The phone's role, or 'godfather' (the default role) when it can't be resolved."""
        if self.user_manager is None or not phone:
            return "godfather"
        user = self.user_manager.get_user(phone)
        return user.role if user else "godfather"

    def _handle_message_body(  # pylint: disable=too-many-locals,too-many-arguments
            self, request: AIRequest, *, chat_id: Optional[str], user_role: str,
            sender: Optional[str], recipient: Optional[str], user_phone: Optional[str],
            is_group: bool, chat_name: Optional[str], sender_phone: Optional[str]) -> AIResponse:
        """The actual per-turn logic, split out of handle_message so the telemetry_span
        context manager above wraps it cleanly (a context manager's body can't easily
        `return` from inside a try/except/finally spanning the whole call otherwise)."""
        # Message addressing (sender/recipient/group) is no longer needed here - every
        # message is stored at the WhatsApp boundary by DeniDin (2026-09-30).
        del sender, recipient, chat_name
        try:
            role = self._resolve_role(user_role)
            effective_chat_id = chat_id or request.chat_id
            # Backbone-tool dispatch context (2026-09-14, same per-turn-instance-attribute
            # lifecycle/reasoning as _turn_conversation_history) - chat_id/message_id are
            # send_progress_update's and react_to_message's real dispatch target/default.
            self._turn_chat_id = effective_chat_id
            self._turn_message_id = request.message_id
            self._turn_request_id = request.request_id
            self._turn_sent_texts = []
            # Reset per-turn MCP-call accumulator (2026-09-15) - see __init__'s
            # _turn_mcp_calls docstring.
            self._turn_mcp_calls = []
            self._turn_tokens = [0, 0, 0]
            self._turn_last_response = None
            self._turn_original_message = request.original_message
            self._turn_offered_approval = False
            # Long-term memory recall (2026-09-15, closing a real gap - see
            # _recall_memory's own docstring): computed once here, read by
            # build_instructions for every round this turn makes, same
            # once-per-turn/read-by-every-round lifecycle as _turn_conversation_history.
            self._turn_memory_context = self._recall_memory(
                request.user_prompt, effective_chat_id, user_phone, sender_phone,
            )
            turn_context = {
                "role": role,
                "request_id": request.request_id,
                "user_phone": user_phone or sender_phone,
                "chat_id": effective_chat_id,
                "sender_phone": sender_phone,
                # The turn's attached file (None for a text turn) - analyze_media reads it.
                "media": request.media,
                "timestamp": request.timestamp,
                # The stored inbound message this turn answers - analyze_media fills
                # its extracted text into it (2026-09-30).
                "message_id": request.message_id,
                # The inbound message itself - analyze_media stores the read document's
                # stash in the conversation addressed like it (M1/M2, 2026-10-04).
                "original_message": request.original_message,
                "caption": request.user_prompt if request.media is not None else "",
                # Group chats get the group etiquette section (Item14).
                "is_group": is_group,
            }

            # The tool-driven resolution loop (see
            # contracts/capability-resolution-loop.md): one continuous conversation
            # driven by load_capabilities/unload_capabilities/load_flows/unload_flows/reset_to_backbone/
            # record_planning_status/approval_with_yes_no_buttons/send_to_user.
            self._turn_planning_status = None
            # A yes to outstanding approval buttons makes this the message that answers an
            # approval (Item4). Any new message supersedes whatever approval buttons were
            # outstanding.
            self._turn_answers_approval = False
            if effective_chat_id:
                approval_was_pending = bool(
                    self.session_manager.get_session(effective_chat_id).approval_message_id)
                self._turn_answers_approval = (
                    approval_was_pending and self.is_affirmative_reply(request.user_prompt))
                # Feature 067 (REQ-RMH-017): the stale-tap guard is cleared only when the
                # approval itself is answered here (a typed or tapped yes/no); unrelated
                # messages leave it alone, and a newer approval overwrites it when sent.
                if approval_was_pending and (
                        self._turn_answers_approval or self.is_negative_reply(request.user_prompt)):
                    self.session_manager.set_approval_message_id(effective_chat_id, None)
            self._run_conversation(request, turn_context)
            return self._activity_record(request)
        # Legacy's per-error replies (AIHandler._get_response_impl), checked in its order:
        # APITimeoutError and RateLimitError are both APIErrors (C8, 2026-10-04).
        except APITimeoutError as exc:
            logger.error("OpenAI API timeout for request %s after retries: %s",
                         request.request_id, exc, exc_info=True)
            return self._report_failure(request, BACKBONE_AI_TIMEOUT)
        except RateLimitError as exc:
            logger.error("OpenAI rate limit exceeded for request %s after retries: %s",
                         request.request_id, exc, exc_info=True)
            return self._report_failure(request, BACKBONE_AI_RATE_LIMITED)
        except APIError as exc:
            logger.error("OpenAI API error for request %s after retries: %s",
                         request.request_id, exc, exc_info=True)
            return self._report_failure(request, BACKBONE_AI_API_ERROR)
        except Exception as exc:  # pylint: disable=broad-except
            logger.error(
                "Unexpected error in Backbone.handle_message for request %s: %s",
                request.request_id, exc, exc_info=True,
            )
            return self._report_failure(request, BACKBONE_UNEXPECTED_ERROR)

    def _report_failure(self, request: AIRequest, message: str) -> AIResponse:
        """A model call failed after its retries (or something unexpected broke): the friendly
        error text goes to the user at once and the app pauses. The chain is dropped - it may
        end at a response whose tool calls were never answered - so the next message starts a
        new one from the rolling window."""
        chat_id = self._turn_chat_id
        if chat_id:
            try:
                self.session_manager.set_ai_chain_id(chat_id, None)
            except Exception as exc:  # pylint: disable=broad-except
                logger.error("Could not drop the model chain of %s after a failure: %s", chat_id, exc)
        self._send_to_user(message)
        return self._activity_record(request)

    # ------------------------------------------------------------------
    # Loaded-capability state (persisted on Session.active_capabilities)
    # ------------------------------------------------------------------

    def _get_active_tags(self, chat_id: str) -> List[CapabilityTag]:
        """This chat's currently-loaded capabilities, oldest-loaded first -
        read from the persisted Session (the sole source of truth). Unknown/
        retired tag values are dropped."""
        tags: List[CapabilityTag] = []
        for name in self.session_manager.get_session(chat_id).active_capabilities:
            try:
                tag = CapabilityTag(name)
            except ValueError:
                continue
            if tag not in tags:
                tags.append(tag)
        return tags

    def _set_active_tags(self, chat_id: str, tags: List[CapabilityTag]) -> None:
        """Persists the loaded set (Session.active_capabilities) - the one
        write path every load/unload/reset dispatch goes through."""
        self.session_manager.set_active_capabilities(chat_id, [t.value for t in tags])

    def _get_active_flows(self, chat_id: str) -> List[FlowTag]:
        """This chat's currently-loaded flows, oldest-loaded first, read from
        the persisted Session. Unknown/retired values are dropped."""
        flows: List[FlowTag] = []
        for name in self.session_manager.get_session(chat_id).active_flows:
            try:
                flow = FlowTag(name)
            except ValueError:
                continue
            if flow not in flows:
                flows.append(flow)
        return flows

    def _set_active_flows(self, chat_id: str, flows: List[FlowTag]) -> None:
        """Persists the loaded flow set (Session.active_flows)."""
        self.session_manager.set_active_flows(chat_id, [f.value for f in flows])

    def _build_round_inputs(self, request: AIRequest, chat_id: str,
                             turn_context: Dict[str, Any]):
        """Everything one API call needs, recomputed from the persisted
        loaded flow/capability sets EVERY round (initial AND follow-up):
        `instructions` (backbone + catalogs + each loaded flow's and capability's prompt)
        AND `tools` (resolution + backbone + each loaded capability's real
        tools) - both from the SAME set, so a prompt is never attached
        without its tools (the root cause of the original bug), and
        previous_response_id chaining - which retains neither - never loses
        either. Returns (tags, instructions, tools)."""
        tags = self._get_active_tags(chat_id)
        tools = list(RESOLUTION_TOOLS) + list(BACKBONE_TOOLS) + build_capability_tools(self, tags, turn_context)
        instructions = self.build_instructions(
            tags, "", request.timestamp, active_flows=self._get_active_flows(chat_id),
            is_group=bool(turn_context.get("is_group")))
        return tags, instructions, tools

    # ------------------------------------------------------------------
    # The resolution loop (contracts/capability-resolution-loop.md)
    # ------------------------------------------------------------------

    @staticmethod
    def _timestamp_label(request: AIRequest) -> str:
        """`[HH:MM:SS dd/mm] ` - the message's send time, Israel local (REQ-RMH-007); "" when
        the request carries no timestamp."""
        epoch = request.timestamp
        return f"[{local_from_timestamp(epoch).strftime('%H:%M:%S %d/%m')}] " if epoch else ""

    @staticmethod
    def _first_round_user_content(request: AIRequest) -> str:
        """The user message the first round sends. For a media turn (2026-09-30) the
        model gets NO media bytes here - only a marker saying a file is attached (type +
        filename), followed by the caption if any; backbone.md tells it to load
        cap_media_analysis and call analyze_media, which does the real extraction."""
        if request.media is None:
            return request.user_prompt
        type_label = MEDIA_TYPE_LABELS.get(request.media.media_type or "", "file")
        filename = request.media.filename or ""
        marker = f"[ATTACHED MEDIA: {type_label}, file: {filename}]"
        return f"{marker}\n{request.user_prompt}" if request.user_prompt else marker

    def _first_input(self, request: AIRequest, chat_id: str) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """The first model call's input and the chain it continues. With a live chain the input
        is just this message (the chain holds everything before it); without one it is the
        rolling window followed by the message, and the call starts a new chain."""
        user_item = {
            "role": "user",
            # A media request's first-round text is pinned by an approved test (no
            # timestamp) - a human decision is pending on stamping it (Feature 067 open point).
            "content": ("" if request.media is not None else self._timestamp_label(request))
            + self._first_round_user_content(request)}
        chain_id = self.session_manager.get_session(chat_id).ai_chain_id
        if chain_id:
            return [user_item], chain_id
        return self._window_input(request, chat_id) + [user_item], None

    def _window_input(self, request: AIRequest, chat_id: str) -> List[Dict[str, Any]]:
        """The rolling window (last 14 days, everything stored before this message) a new
        chain starts from; long-term summaries ride along in the instructions."""
        return self._load_conversation_history(chat_id, exclude_message_id=request.message_id)

    def _run_conversation(self, request: AIRequest, turn_context: Dict[str, Any]) -> None:
        """The model works whenever it has something to do and pauses when it has nothing.
        There is no end: every model response is acted on - each tool call is executed at
        once (a send is sent, buttons are sent) and its result handed back in the next call,
        together with any user messages that arrived meanwhile - and the app pauses only
        when a response carries no tool call. Output text is ignored (logged); a response
        with text and no tool call gets ONE more call telling the model so; an empty response
        pauses at once. Instructions AND tools are rebuilt from the persisted loaded
        flow/capability sets for every call (a chain retains neither)."""
        chat_id: str = turn_context["chat_id"]  # every message has a chat
        input_items, previous_id = self._first_input(request, chat_id)
        told_text_ignored = False
        for _round in range(MAX_BACKBONE_TOOL_LOOP_ITERATIONS):
            tags, instructions, tools = self._build_round_inputs(request, chat_id, turn_context)
            response = self._call_chained(request, chat_id, input_items, previous_id, instructions, tools)
            previous_id = getattr(response, "id", None)
            last_output_at = now_local()  # when the model's most recent output came back
            has_calls = any(getattr(item, "type", None) == "function_call"
                            for item in (getattr(response, "output", None) or []))
            with (self.tool_call_span(self._turn_telemetry_builder, "local_tools") if has_calls
                  else contextlib.nullcontext()):
                outputs = self._execute_round_calls(request, turn_context, chat_id=chat_id, tags=tags,
                                                    response=response)
            if outputs is None:
                plain_text = (getattr(response, "output_text", "") or "").strip()
                if not plain_text:
                    return  # nothing to do: the app pauses
                logger.warning("Model answered in plain text without a tool call (request %s) - text ignored: %r",
                               request.request_id, plain_text)
                if told_text_ignored:
                    return
                told_text_ignored = True
                input_items = [{"role": "developer", "content": PLAIN_TEXT_IGNORED_NOTE}]
                continue
            told_text_ignored = False
            input_items = self._compose_follow_up_input(chat_id, outputs, last_output_at)
        logger.warning(
            "Conversation hit MAX_BACKBONE_TOOL_LOOP_ITERATIONS=%d for request %s - pausing.",
            MAX_BACKBONE_TOOL_LOOP_ITERATIONS, request.request_id,
        )

    def _call_chained(self, request: AIRequest, chat_id: str, input_items: List[Dict[str, Any]],
                      previous_id: Optional[str], instructions: str, tools: List[Dict[str, Any]]) -> Any:
        """One model call continuing the chat's chain (`previous_id`), or starting a new one when
        there is none. The new response id is stored on the session as the chain's head. When
        OpenAI no longer knows the chain (previous_response_not_found) it is dropped and the
        call is made again as the start of a new chain, from the rolling window."""
        kwargs: Dict[str, Any] = {
            "model": request.model,
            "instructions": instructions,
            "input": input_items,
            "max_output_tokens": request.max_tokens,
            "tools": tools,
            "truncation": "auto",  # a long chain drops its oldest items instead of failing (no hard cap)
        }
        if previous_id:
            kwargs["previous_response_id"] = previous_id
        try:
            response = self._call_model("conversation (chained)" if previous_id else "conversation (new chain)",
                                        chat_id, kwargs)
        except BadRequestError as exc:
            if not previous_id or getattr(exc, "code", None) != CHAIN_NOT_FOUND_CODE:
                raise
            logger.warning("[067] OpenAI no longer knows the chain of %s (%s) - starting a new one from the "
                           "rolling window", chat_id, previous_id)
            kwargs.pop("previous_response_id")
            kwargs["input"] = self._window_input(request, chat_id) + [
                item for item in input_items if item.get("role") == "user"]
            response = self._call_model("conversation (new chain after expiry)", chat_id, kwargs)
        self.session_manager.set_ai_chain_id(chat_id, getattr(response, "id", None))
        return response

    def _compose_follow_up_input(self, chat_id: str, outputs: List[Dict[str, Any]],
                                 last_output_at: Any) -> List[Dict[str, Any]]:
        """The model's next input at a hand-back (Feature 067, REQ-RMH-001): (A) what the
        app did for the model - its tool results - and (B) the user messages that arrived
        since, each with its send time and whether it came before or after the model's last
        output. The model's own work is never aborted; it just sees the new messages next.
        Nothing is attached while an approved action is being handled (REQ-RMH-014) - those
        messages are handled afterwards."""
        if self._turn_answers_approval:
            return outputs
        drained = self.denidin.receive_pending(chat_id)
        if drained is None or not drained.ordered:
            return outputs
        logger.info("[067] %d message(s) arrived while working in %s - handed to the model with its tool results",
                    len(drained.ordered), chat_id)
        return outputs + format_pending_items(drained, last_output_at)

    def _execute_round_calls(self, request: AIRequest, turn_context: Dict[str, Any], *, chat_id: str,
                              tags: List[CapabilityTag], response: Any
                              ) -> Optional[List[Dict[str, Any]]]:
        """Executes every tool call in one response, at once - each function_call gets an
        output, an error one when it could not run. None when the response carries no tool
        call at all."""
        resolution_calls = extract_resolution_tool_calls(response)
        backbone_calls = extract_backbone_tool_calls(response)
        domain_calls = extract_local_calls(response, local_tool_owners(self, tags, turn_context))
        outputs = self._run_resolution_calls(resolution_calls, chat_id)
        outputs += self._run_domain_calls(domain_calls, turn_context)
        outputs += self._run_backbone_calls(backbone_calls, request)
        outputs += self._unanswered_call_outputs(response, {o["call_id"] for o in outputs})
        return outputs or None

    @staticmethod
    def _unanswered_call_outputs(response: Any, answered_call_ids: set) -> List[Dict[str, Any]]:
        """An error output for every function_call in `response` that got none - its
        arguments didn't parse (e.g. cut off at the output limit) or it names no attached
        tool. Legacy answered each such call with its own isolated error
        (ai_handler.py's _compute_query_ledger_events_outputs/_compute_react_to_message_outputs);
        left unanswered, OpenAI rejects the next round ("No tool output found") and the
        turn ends in an error (M3, 2026-10-04)."""
        outputs: List[Dict[str, Any]] = []
        for item in (getattr(response, "output", None) or []):
            if getattr(item, "type", None) != "function_call":
                continue
            call_id = getattr(item, "call_id", None)
            if not call_id or call_id in answered_call_ids:
                continue
            name = getattr(item, "name", None)
            try:
                json.loads(getattr(item, "arguments", None) or "")
                reason = f"Tool {name!r} is not available right now - this call was not executed."
            except (json.JSONDecodeError, TypeError):
                reason = ("Arguments could not be parsed (likely truncated) - this call was not "
                          "executed. Do not resubmit this exact call.")
            logger.warning("Unanswered %r function_call %r answered with an error: %s", name, call_id, reason)
            outputs.append({"type": "function_call_output", "call_id": call_id,
                            "output": json.dumps({"status": "error", "reason": reason}, ensure_ascii=False)})
        return outputs

    def _run_resolution_calls(self, calls: List[Tuple[str, str, Dict[str, Any]]], chat_id: str
                                  ) -> List[Dict[str, Any]]:
        outputs: List[Dict[str, Any]] = []
        for call_id, tool_name, args in calls:
            if tool_name == "send_to_user":
                result_text = ("ok" if self._send_to_user(str(args.get("text", "")))
                               else "error: the message was not sent.")
            elif tool_name == "approval_with_yes_no_buttons":
                result_text = ("ok" if self._send_approval_buttons(str(args.get("text", "")))
                               else "error: the approval buttons were not sent.")
            else:
                result_text = self._dispatch_resolution_tool(tool_name, args, chat_id)
            outputs.append({"type": "function_call_output", "call_id": call_id, "output": result_text})
        return outputs

    def _send_to_user(self, text: Optional[str]) -> bool:
        """Sends `text` to the user now (DeniDin.send_to_user - cut to length, wire-logged,
        stored). False when nothing was sent. Best-effort - never raises."""
        text = (text or "").strip()
        if not text:
            logger.warning("send_to_user called with no text - nothing sent")
            return False
        try:
            sent = self.denidin.send_to_user(self._turn_chat_id, text, mcp_calls=list(self._turn_mcp_calls) or None)
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("send_to_user: failed to send: %s", exc)
            return False
        if sent:
            self._after_sent(text)
        return bool(sent)

    def _send_approval_buttons(self, text: Optional[str]) -> bool:
        """Sends `text` to the user now as the yes/no approval buttons (DeniDin.send_approval_buttons
        stores the sent message id on the chat). False when nothing was sent."""
        text = (text or "").strip()
        if not text:
            logger.warning("approval_with_yes_no_buttons called with no text - nothing sent")
            return False
        try:
            sent = self.denidin.send_approval_buttons(
                self._turn_chat_id, text, mcp_calls=list(self._turn_mcp_calls) or None)
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("approval_with_yes_no_buttons: failed to send: %s", exc)
            return False
        if sent:
            self._turn_offered_approval = True
            self._after_sent(text)
        return bool(sent)

    def _after_sent(self, text: str) -> None:
        """Per sent message: remember it for the activity record, and run the log-only
        possible-fabricated-confirmation check against the Morning calls made so far."""
        self._turn_sent_texts.append(text)
        self.log_possible_hallucinated_confirmation(
            self._turn_request_id, text, True, self._turn_mcp_calls)
        if self._turn_telemetry_builder is not None:
            self._turn_telemetry_builder.mark_progress_update_sent()

    def _run_domain_calls(self, calls: List[Tuple[str, str, Dict[str, Any], CapabilityTag]],
                           turn_context: Dict[str, Any]) -> List[Dict[str, Any]]:
        outputs: List[Dict[str, Any]] = []
        for call_id, tool_name, args, owner_tag in calls:
            try:
                result_text = dispatch_local_tool(self, owner_tag, tool_name, args, turn_context)
                outcome = "failure" if result_text.startswith(("⚠️", "error:")) else "success"
            except Exception as exc:  # pylint: disable=broad-except
                logger.error("%s(%s) failed (non-fatal): %s", tool_name, owner_tag.value, exc, exc_info=True)
                result_text, outcome = f"error: {tool_name} failed: {exc}", "exception"
            log_capability_action(owner_tag.value, f"{tool_name}({args})", outcome, result_text)
            outputs.append({"type": "function_call_output", "call_id": call_id, "output": result_text})
        return outputs

    def _run_backbone_calls(self, calls: List[Tuple[str, str, Dict[str, Any]]], request: AIRequest
                             ) -> List[Dict[str, Any]]:
        outputs: List[Dict[str, Any]] = []
        for call_id, tool_name, args in calls:
            if tool_name == "send_progress_update":
                # The same send as send_to_user (stored by the send itself, like every message).
                payload = {"sent": self._send_to_user(args.get("text"))}
            else:
                payload = build_react_to_message_payload(
                    self.denidin, request, self._turn_chat_id, args, call_id,
                )
            outputs.append({"type": "function_call_output", "call_id": call_id,
                            "output": json.dumps(payload, ensure_ascii=False)})
        return outputs

    def _call_model(self, context: str, chat_id: str, kwargs: Dict[str, Any]) -> Any:
        """One Responses API call, wire-logged both directions, its mcp_call items accumulated,
        telemetry recorded. WhatsApp's typing indicator is on exactly while the call is in
        flight. Retries explicitly once on an HTTP 424 (a gap the OpenAI SDK's own max_retries
        never covers - see AIManager.call_model_with_retry's docstring)."""
        audit_wire("openai", "out", context, kwargs)
        debug_wire("openai", "out", context, kwargs)
        typing_job = self.denidin.start_typing(chat_id)
        try:
            # Retry + Feature 080 timing via the shared AIManager.timed_model_call: a failed
            # call is timed and counted too.
            if self._turn_answers_approval:
                # Same as legacy _call_openai_approval_api (Item4): the OpenAI SDK's own
                # retries are off (max_retries=0) while the approved action runs; the shared
                # explicit 424 retry still applies.
                response = self.timed_model_call(
                    self._turn_telemetry_builder,
                    lambda: self.client.with_options(max_retries=0).responses.create(**kwargs),
                    context=context,
                )
            else:
                response = self.timed_model_call(
                    self._turn_telemetry_builder, lambda: self.client.responses.create(**kwargs),
                    context=context,
                )
        finally:
            self.denidin.stop_typing(typing_job)
        audit_wire("openai", "in", context, response)
        debug_wire("openai", "in", context, response)
        new_mcp_calls = self._extract_mcp_call_items(response)
        self._turn_mcp_calls.extend(new_mcp_calls)
        self.record_mcp_tool_calls(self._turn_telemetry_builder, new_mcp_calls)  # telemetry, as they happen
        # A Morning document created now is recorded in the ledger by the app itself.
        if any(call["name"] in DOCUMENT_CREATING_TOOLS and not call["error"] for call in new_mcp_calls):
            self.denidin.record_created_document()
        usage = getattr(response, "usage", None)
        if usage is not None:
            self._turn_tokens[0] += int(getattr(usage, "total_tokens", 0) or 0)
            self._turn_tokens[1] += int(getattr(usage, "input_tokens", 0) or 0)
            self._turn_tokens[2] += int(getattr(usage, "output_tokens", 0) or 0)
        self._turn_last_response = response
        return response

    def _dispatch_resolution_tool(self, tool_name: str, args: Dict[str, Any], chat_id: str) -> str:
        """Dispatches one load_flows/unload_flows/load_capabilities/
        unload_capabilities/reset_to_backbone/record_planning_status call,
        returning the plain-text string fed back as its function_call_output.

        Loading a capability attaches BOTH its prompt text AND its real tools
        to every following round (see _build_round_inputs); loading a flow
        attaches its blueprint text only - the flow itself tells the model
        which capabilities to load. Loading an already-loaded item / unloading
        one that isn't loaded is a harmless no-op. Every load/unload/reset is
        audit-logged with the model's own latest planning status (its stated
        reasoning) - see log_loading_action."""
        if tool_name == "record_planning_status":
            self._turn_planning_status = (
                f"WHERE I WAS: {args.get('where_i_was', '')}\n"
                f"THIS TURN'S PURPOSE: {args.get('this_turns_purpose', '')}\n"
                f"EXPECTATION: {args.get('expectation', '')}"
            )
            # Stored the moment it's recorded, as a clearly-tagged internal note (never
            # sent to the user) - flows into later turns via the rolling window.
            if self._turn_original_message is not None:
                self.denidin.store_outbound(
                    self._turn_original_message,
                    f"[[INTERNAL_PLANNING_NOTE]]\n{self._turn_planning_status}",
                )
            return "recorded"
        if tool_name == "reset_to_backbone":
            flows = [f.value for f in self._get_active_flows(chat_id)]
            capabilities = [t.value for t in self._get_active_tags(chat_id)]
            self._set_active_flows(chat_id, [])
            self._set_active_tags(chat_id, [])
            log_loading_action("reset", "all", flows + capabilities, now_loaded_flows=[],
                               now_loaded_capabilities=[], planning_status=self._turn_planning_status)
            return "reset - every flow and capability unloaded; you are back to the plain backbone."
        handlers = {
            "load_flows": ("flow", True),
            "unload_flows": ("flow", False),
            "load_capabilities": ("capability", True),
            "unload_capabilities": ("capability", False),
        }
        if tool_name not in handlers:
            return f"error: unknown resolution tool {tool_name!r}"
        kind, loading = handlers[tool_name]
        return self._apply_loading(kind, loading, args, chat_id)

    def _apply_loading(self, kind: str, loading: bool, args: Dict[str, Any], chat_id: str) -> str:
        """Shared body of the four load/unload tools: parse the requested names
        against the closed enum (unknown ones are reported back), update the
        persisted set, audit-log, and describe the resulting sets to the model."""
        is_flow = kind == "flow"
        requested = list(args.get("flows" if is_flow else "capabilities") or [])
        valid, unknown = parse_requested(FlowTag if is_flow else CapabilityTag, requested)
        current = self._get_active_flows(chat_id) if is_flow else self._get_active_tags(chat_id)
        updated = apply_loading(current, valid, loading=loading)
        if updated != current:
            if is_flow:
                self._set_active_flows(chat_id, updated)
            else:
                self._set_active_tags(chat_id, updated)
        flows_now = [f.value for f in self._get_active_flows(chat_id)]
        capabilities_now = [t.value for t in self._get_active_tags(chat_id)]
        log_loading_action("load" if loading else "unload", kind, requested, now_loaded_flows=flows_now,
                           now_loaded_capabilities=capabilities_now, planning_status=self._turn_planning_status)
        return describe_loading(kind, loading=loading, valid=valid, unknown=unknown,
                                flows_now=flows_now, capabilities_now=capabilities_now)

    def _activity_record(self, request: AIRequest) -> AIResponse:
        """A record of what this call to handle_message did - the texts it sent, the Morning
        calls it made, its token usage - for observability (denidin_app.last_response, the
        E2E harness). Nothing is delivered from it: every send already happened."""
        last = self._turn_last_response
        model = getattr(last, "model", None)
        finish_reason = self.finish_reason_of(last) if last is not None else "stop"
        total_tokens, prompt_tokens, completion_tokens = self._turn_tokens
        sent_text = self._turn_sent_texts[-1] if self._turn_sent_texts else ""
        return AIResponse(
            request_id=request.request_id,
            response_text=sent_text,
            tokens_used=total_tokens,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            model=model if isinstance(model, str) and model else request.model,
            finish_reason=finish_reason if isinstance(finish_reason, str) else "stop",
            timestamp=request.timestamp or int(now_local().timestamp()),
            should_reply=bool(sent_text),
            offer_approval_buttons=bool(self._turn_offered_approval),
            mcp_calls=list(self._turn_mcp_calls),
        )

    @staticmethod
    def _resolve_role(user_role: str) -> Role:
        """Clients are out of scope for the backbone for now (2026-10-01, explicit
        decision): an unknown/missing role is treated as godfather."""
        try:
            return Role(user_role.upper())
        except ValueError:
            return Role.GODFATHER

    def _load_conversation_history(self, chat_id: Optional[str],
                                   exclude_message_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Feature 070 rolling window via the AIManager.load_rolling_window.
        Godfather/Admin-only scope for now (explicit decision, 2026-09-14): always the
        godfather/admin token limit from config.memory['session']['max_tokens_by_role']."""
        session_config = (self.config.memory or {}).get('session', {})
        return self.load_rolling_window(
            chat_id,
            window_days=session_config.get('window_days', 14),
            max_tokens=session_config.get('max_tokens_by_role', {}).get('godfather', 100000),
            before_message_id=exclude_message_id,  # Feature 067: only what came before this message
            with_timestamps=True,  # Feature 067 (REQ-RMH-007): the model reads the timeline
        )

    def _recall_memory(self, user_prompt: str, chat_id: Optional[str],
                        user_phone: Optional[str], sender_phone: Optional[str]) -> str:
        """Long-term daily_summary recall via the AIManager.recall_memory_context
        (the same call AIHandler.create_request makes): RBAC-filtered when user_manager is
        available, plain recall otherwise. "" (never raises) when nothing is found."""
        longterm_config = (self.config.memory or {}).get('longterm', {})
        return self.recall_memory_context(
            query=user_prompt, chat_id=chat_id,
            top_k=longterm_config.get('daily_summary_top_k', 10),
            min_similarity=longterm_config.get('min_similarity', 0.7),
            user_phone=user_phone or sender_phone,
        )

    # ------------------------------------------------------------------
    # Button-tap resolution (a tap is just an ordinary "כן"/"לא" turn)
    # ------------------------------------------------------------------

    def resolve_button_tap(self, message: WhatsAppMessage, selected_id: str, stanza_id: str, *,
                           user_role: Optional[str] = None) -> Optional[AIResponse]:
        """Feature 047's stale-tap guard: a tap is live only if its `stanza_id`
        exactly equals the idMessage of the approval-buttons message this chat
        is currently offering (Session.approval_message_id). A stale/superseded/
        already-used tap returns None - the caller sends nothing at all. A live
        tap is consumed and resolved like a typed "כן"/"לא": a synthetic AIRequest
        carrying that answer runs through the ordinary handle_message() loop, where the
        model reads its own history and acts on it - with the same progress updates and
        sender/chat details a typed reply gets (2026-09-30)."""
        chat_id = message.chat_id
        if self.session_manager.get_session(chat_id).approval_message_id != stanza_id:
            logger.info("[047] Stale button tap ignored: chat=%r stanza_id=%r", chat_id, stanza_id)
            return None
        if user_role is None:
            user_role = self._role_for_phone(message.sender_id)
        # 2026-09-15 (T7/T10): the tap needs a real AIRequest (model, max_tokens) for
        # its approval-resolution call - mirrors the legacy tap's synthetic request.
        request = AIRequest(
            user_prompt="כן" if selected_id == "denidin_approve" else "לא",
            constitution="",
            max_tokens=self.config.ai_reply_max_tokens,
            model=self.config.ai_model,
            chat_id=chat_id,
            message_id=message.message_id,
            original_message=message,
        )
        return self.handle_message(
            request, chat_id=chat_id, user_role=user_role,
            sender=message.sender_display_name, user_phone=message.sender_id,
            sender_phone=message.sender_id, is_group=message.is_group,
            chat_name=message.chat_name,
        )

    def extraction_prompt_prefix(self) -> str:
        """Nothing - the extractors prepend this to their own extraction prompt, and
        the vision model is not the conversational model: it gets the extraction
        prompt alone (2026-10-01). Prepending the backbone + a capability's prompt
        told a tool-less vision model to load capabilities, call analyze_media and
        answer the user, so it wrote fake tool calls before its JSON and the JSON
        no longer parsed (T1, 2026-10-01)."""
        return ""

    def capture_ledger_events_from_text(self, text: str, today_timestamp: Optional[int] = None
                                        ) -> List[Dict]:
        """No inline capture here: extracted text goes back through the model, and
        capture happens through DeniDin's shared post-turn recognition once the turn is
        persisted - running it inline too would risk capturing the same event twice."""
        del text, today_timestamp
        logger.info(
            "cap_media_analysis capability: inline ledger capture skipped here - "
            "capture happens automatically via the shared post-turn recognition "
            "mechanism once this turn is persisted (see ledger_events/handler.py)."
        )
        return []
