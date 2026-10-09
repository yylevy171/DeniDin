"""
Backbone (Feature 063) — the new, standalone module implementing the
Backbone-as-tool-backbone-kernel architecture. Selected once at startup by
`denidin.py::initialize_app` only when `config.feature_flags['enable_capability_backbone']`
is true; `src/handlers/ai_handler.py` is never imported by, and never imports, this
module (REQ-063-07).

See contracts/capability-resolution-loop.md (the loop) and contracts/prompt-assembly.md
(the prompt-loading/caching + per-call instructions assembly this module implements).
"""
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
from src.backbone.prompt_cache import MtimePromptCache
from src.backbone.resolution_tools import RESOLUTION_TOOLS, extract_resolution_tool_calls
from src.capabilities.toolsets import (
    WRITE_TOOL_NAMES,
    build_capability_tools,
    dispatch_local_tool,
    extract_local_calls,
    local_tool_owners,
)
from openai import APIError, APITimeoutError, RateLimitError

from src.constants.error_messages import (
    APPROVED_WRITE_NOT_PERFORMED_NOTE, APPROVED_WRITE_POSSIBLY_DUPLICATED_NOTE, BACKBONE_AI_API_ERROR,
    BACKBONE_AI_RATE_LIMITED, BACKBONE_AI_TIMEOUT, BACKBONE_UNEXPECTED_ERROR,
    LEDGER_FOLLOWUP_FAILED_TRY_AGAIN,
)
from src.models.message import AIRequest, AIResponse, WhatsAppMessage, should_reply_for
from src.models.user import Role
from src.utils.capability_audit_log import log_capability_action, log_loading_action
from src.utils.logger import read_version, DEFAULT_VERSION_FILE
from src.tool_actions.messaging_actions import (
    build_react_to_message_payload, send_progress_update_message,
)
from src.core.ai_manager import AIManager
from src.utils.wire_log import audit_wire, debug_wire
from src.utils.time_utils import now_local, local_from_timestamp

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

# A reply reaches the user ONLY through send_to_user / approval_with_yes_no_buttons
# (2026-09-30). A round that ends in plain text (no tool call) is never sent: the model
# gets this one reminder and another round; if it answers in plain text again, the user
# gets BACKBONE_UNEXPECTED_ERROR instead.
PLAIN_TEXT_REPLY_REMINDER = (
    "Your last response was plain text, which is never shown to the user. "
    "To reply, call send_to_user (or approval_with_yes_no_buttons for a yes/no approval)."
)

# Hebrew label per MediaFileManager.validate_format result, used in the
# first-round "[מדיה מצורפת: ...]" marker of a media turn.
MEDIA_TYPE_LABELS = {"image": "תמונה", "pdf": "PDF", "docx": "מסמך Word"}

_DEFAULT_BACKBONE_CONFIG = {
    "file": "backbone.md",
    "base_dir": "config",
    "prompts_dir": "prompts",
    "capabilities_dir": "capabilities",
}


class Backbone(AIManager):  # pylint: disable=too-many-instance-attributes
    """The new backbone kernel - the AI implementation when the backbone flag is on
    (REQ-063-08). DeniDin's Shared Managers are handed in (AIManager's keyword arguments), never
    built here; the backbone never imports or calls the legacy AIHandler."""

    def __init__(self, denidin: Any):
        super().__init__(denidin)
        config = self.config
        # The telemetry builder of the turn in progress (set in single_turn).
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
        # schema). Reset every turn in single_turn.
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

        # Set once per single_turn() call, read by the resolution loop for
        # every round within that SAME turn (2026-09-14). Deliberately a plain
        # instance attribute, not threaded as an explicit parameter through
        # every one of the ~6 call sites across src/capabilities/* + planning.py
        # - this process handles one webhook turn at a time, so there is no real
        # concurrent-turn clobbering risk in practice.
        self._turn_conversation_history: List[Dict[str, Any]] = []

        # Set once per single_turn() call, same lifecycle/reasoning as
        # _turn_conversation_history above - read by the loop's
        # backbone-tool resolution (send_progress_update/react_to_message) for
        # every round this turn makes.
        self._turn_chat_id: Optional[str] = None
        self._turn_message_id: Optional[str] = None

        # Set False at the top of every single_turn() call; flipped True by
        # ApprovalCapability.handle() iff the approval capability was used
        # THIS turn (2026-09-16) - _finalize_response reads this instead of
        # checking pending-approval managers to decide whether to offer
        # WhatsApp interactive buttons, now that cap_reminders_write creates no
        # pending-approval record of its own.
        self._turn_offered_approval: bool = False

        # Set once per single_turn() call (2026-09-15) - the ChromaDB
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

        # Item4 (2026-10-01): True when this turn answers an approval-buttons prompt
        # with a yes - the turn that runs the approved write. Its model calls are
        # run with the SDK's own retries off (as legacy's approval call), and what it
        # executed is checked (_apply_write_guards).
        # _turn_write_calls collects what it executed: every raw Morning mcp_call item
        # (any tool - a read's output can be the failure detail, as in legacy) and each
        # local write ({name, output, error}); only writes are counted.
        self._turn_is_approved_write: bool = False
        self._turn_write_calls: List[Any] = []

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
        return "\n\n".join(part for part in parts if part)

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

    def single_turn(  # pylint: disable=too-many-locals
            self, request: AIRequest, chat_id: Optional[str] = None, *,
            user_role: Optional[str] = None, sender: Optional[str] = None,
            recipient: Optional[str] = None, user_phone: Optional[str] = None,
            is_group: bool = False, chat_name: Optional[str] = None,
            sender_phone: Optional[str] = None) -> AIResponse:
        """The backbone's AIManager.single_turn (REQ-063-08): resolves one WhatsApp turn
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
        # implementation, also used by AIHandler.single_turn - the two were
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
            return self._single_turn_body(
                request, chat_id=chat_id, user_role=user_role, sender=sender, recipient=recipient,
                user_phone=user_phone, is_group=is_group, chat_name=chat_name, sender_phone=sender_phone,
            )

    def _role_for_phone(self, phone: Optional[str]) -> str:
        """The phone's role, or 'godfather' (the default role) when it can't be resolved."""
        if self.user_manager is None or not phone:
            return "godfather"
        user = self.user_manager.get_user(phone)
        return user.role if user else "godfather"

    def _single_turn_body(  # pylint: disable=too-many-locals,too-many-arguments
            self, request: AIRequest, *, chat_id: Optional[str], user_role: str,
            sender: Optional[str], recipient: Optional[str], user_phone: Optional[str],
            is_group: bool, chat_name: Optional[str], sender_phone: Optional[str]) -> AIResponse:
        """The actual per-turn logic, split out of single_turn so the telemetry_span
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
            # Reset per-turn MCP-call accumulator (2026-09-15) - see __init__'s
            # _turn_mcp_calls docstring.
            self._turn_mcp_calls = []
            self._turn_tokens = [0, 0, 0]
            self._turn_last_response = None
            self._turn_original_message = request.original_message
            # Reset per-turn approval-buttons flag (2026-09-16) - see __init__'s
            # _turn_offered_approval docstring.
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

            # Conversation history (2026-09-14): the SAME rolling-window shape/source
            # AIHandler._call_openai_api already uses (SessionManager.get_rolling_window,
            # oldest-first, role-token-capped) - godfather/admin-only scope for now
            # (explicit decision - client role isn't exercised through this backbone
            # yet), so the token cap always uses the godfather/admin limit. Set once here,
            # read by the loop for every round this turn makes (see that
            # method's own docstring for why this is a plain instance attribute rather
            # than threaded through every call site).
            self._turn_conversation_history = self._load_conversation_history(
                effective_chat_id, exclude_message_id=request.message_id)

            # The tool-driven resolution loop (see
            # contracts/capability-resolution-loop.md): one continuous conversation
            # driven by load_capabilities/unload_capabilities/load_flows/unload_flows/reset_to_backbone/
            # record_planning_status/approval_with_yes_no_buttons/send_to_user.
            self._turn_planning_status = None
            # A yes to outstanding approval buttons makes this the approved-write
            # turn (Item4). Any new turn supersedes whatever approval buttons were
            # outstanding.
            self._turn_write_calls = []
            self._turn_is_approved_write = False
            if effective_chat_id:
                approval_was_pending = bool(
                    self.session_manager.get_session(effective_chat_id).approval_message_id)
                self._turn_is_approved_write = (
                    approval_was_pending and self.is_affirmative_reply(request.user_prompt))
                self.session_manager.set_approval_message_id(effective_chat_id, None)
            final_text = self._run_resolution_loop(request, turn_context)
            final_text = self._apply_write_guards(request, final_text)

            # Feature 080: the turn's Morning MCP calls, recorded the same way
            # AIHandler._finalize_response records them (shared helper).
            if self._turn_mcp_calls:
                logger.info("MCP calls for request %s: %s", request.request_id, self._turn_mcp_calls)
            self.record_mcp_tool_calls(self._turn_telemetry_builder, self._turn_mcp_calls)
            return self._finalize_response(request, final_text)
        # Legacy's per-error replies (AIHandler._get_response_impl), checked in its order:
        # APITimeoutError and RateLimitError are both APIErrors (C8, 2026-10-04).
        except APITimeoutError as exc:
            logger.error("OpenAI API timeout for request %s after retries: %s",
                         request.request_id, exc, exc_info=True)
            return self._create_fallback_response(request.request_id, BACKBONE_AI_TIMEOUT)
        except RateLimitError as exc:
            logger.error("OpenAI rate limit exceeded for request %s after retries: %s",
                         request.request_id, exc, exc_info=True)
            return self._create_fallback_response(request.request_id, BACKBONE_AI_RATE_LIMITED)
        except APIError as exc:
            logger.error("OpenAI API error for request %s after retries: %s",
                         request.request_id, exc, exc_info=True)
            return self._create_fallback_response(request.request_id, BACKBONE_AI_API_ERROR)
        except Exception as exc:  # pylint: disable=broad-except
            logger.error(
                "Unexpected error in Backbone.single_turn for request %s: %s",
                request.request_id, exc, exc_info=True,
            )
            # Nothing to store here: the user's message was stored on receipt, every
            # message sent so far was stored as it was sent, and this fallback text is
            # stored when it's sent.
            return self._create_fallback_response(request.request_id, BACKBONE_UNEXPECTED_ERROR)

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
    def _first_round_user_content(request: AIRequest) -> str:
        """The user message the first round sends. For a media turn (2026-09-30) the
        model gets NO media bytes here - only a marker saying a file is attached (type +
        filename), followed by the caption if any; backbone.md tells it to load
        cap_media_analysis and call analyze_media, which does the real extraction."""
        if request.media is None:
            return request.user_prompt
        type_label = MEDIA_TYPE_LABELS.get(request.media.media_type or "", "קובץ")
        filename = request.media.filename or ""
        marker = f"[מדיה מצורפת: {type_label}, קובץ: {filename}]"
        return f"{marker}\n{request.user_prompt}" if request.user_prompt else marker

    def _run_resolution_loop(self, request: AIRequest, turn_context: Dict[str, Any]) -> str:
        """The tool-driven "resolution" loop - one continuous conversation, no
        "initial call"/"turn" concept beyond the API's own call chaining.
        Every round (including the first) rebuilds instructions AND tools from
        the persisted loaded-capability set; `load_flows` / `load_capabilities` /
        their unload counterparts / `reset_to_backbone` mutate those sets, so the
        change takes effect starting the very next round - and persists into
        following messages. Loops (capped by MAX_BACKBONE_TOOL_LOOP_ITERATIONS)
        until send_to_user / approval_with_yes_no_buttons is called, or the
        cap is hit (falls back to the last round's plain text - "never leave
        a turn silent")."""
        chat_id: str = turn_context["chat_id"]  # every turn has a chat
        tags, instructions, tools = self._build_round_inputs(request, chat_id, turn_context)
        input_items = list(self._turn_conversation_history)
        input_items.append({"role": "user", "content": self._first_round_user_content(request)})

        response = self._call_model("_run_resolution_loop (first round)", {
            "model": request.model,
            "instructions": instructions,
            "input": input_items,
            "max_output_tokens": request.max_tokens,
            "tools": tools,
        })

        reminded_of_send_to_user = False
        for _loop_round in range(MAX_BACKBONE_TOOL_LOOP_ITERATIONS):
            # Feature 080 telemetry, matching AIHandler._run_local_tool_dispatch_loop: each
            # round's tool dispatch AND its follow-up model call are timed as one
            # "local_tools" tool call (the shared AIManager.tool_call_span).
            with self.tool_call_span(self._turn_telemetry_builder, "local_tools"):
                round_result = self._execute_round_calls(
                    request, turn_context, chat_id=chat_id, tags=tags, response=response)
                if round_result is None:
                    # Plain text, no tool call - never sent to the user (see
                    # PLAIN_TEXT_REPLY_REMINDER).
                    plain_text = (getattr(response, "output_text", "") or "").strip()
                    if reminded_of_send_to_user:
                        logger.error(
                            "Model answered in plain text again after being reminded to use "
                            "send_to_user (request %s) - not sent; replying with an error. Text: %r",
                            request.request_id, plain_text)
                        return BACKBONE_UNEXPECTED_ERROR
                    logger.warning(
                        "Model answered in plain text without send_to_user (request %s) - not sent; "
                        "reminding it once. Text: %r", request.request_id, plain_text)
                    reminded_of_send_to_user = True
                    outputs = [{"role": "developer", "content": PLAIN_TEXT_REPLY_REMINDER}]
                    final_text = None
                else:
                    outputs, final_text = round_result
                if final_text is not None:
                    # Empty send_to_user text: an error reply, never silence (Item7).
                    return self.reply_or_fallback(final_text, BACKBONE_UNEXPECTED_ERROR)

                try:
                    # Recompute BOTH instructions and tools from the (possibly
                    # just-mutated) persisted set - previous_response_id retains
                    # neither.
                    tags, instructions, tools = self._build_round_inputs(request, chat_id, turn_context)
                    response = self._call_model("_run_resolution_loop (follow-up)", {
                        "model": request.model,
                        "instructions": instructions,
                        "input": outputs,
                        "previous_response_id": getattr(response, "id", None),
                        "max_output_tokens": request.max_tokens,
                        "tools": tools,
                    })
                except Exception as exc:  # pylint: disable=broad-except
                    logger.error("Resolution-loop follow-up call failed (non-fatal): %s", exc)
                    return self.reply_or_fallback(getattr(response, "output_text", ""),
                                             LEDGER_FOLLOWUP_FAILED_TRY_AGAIN)

        logger.warning(
            "Resolution loop hit MAX_BACKBONE_TOOL_LOOP_ITERATIONS=%d for request %s "
            "without a send_to_user call - returning whatever text the last round carries.",
            MAX_BACKBONE_TOOL_LOOP_ITERATIONS, request.request_id,
        )
        return self.reply_or_fallback(getattr(response, "output_text", ""), BACKBONE_UNEXPECTED_ERROR)

    def _execute_round_calls(self, request: AIRequest, turn_context: Dict[str, Any], *, chat_id: str,
                              tags: List[CapabilityTag], response: Any
                              ) -> Optional[Tuple[List[Dict[str, Any]], Optional[str]]]:
        """Executes every tool call in one round's `response` - each function_call gets
        an output, an error one when it could not run: returns None when
        it carries no calls at all (plain text - the loop ends), else
        (function_call_output items for the next round, the reply text if the
        model called send_to_user/approval_with_yes_no_buttons this round)."""
        resolution_calls = extract_resolution_tool_calls(response)
        backbone_calls = extract_backbone_tool_calls(response)
        domain_calls = extract_local_calls(response, local_tool_owners(self, tags, turn_context))
        outputs, final_text = self._run_resolution_calls(resolution_calls, chat_id)
        outputs += self._run_domain_calls(domain_calls, turn_context)
        outputs += self._run_backbone_calls(backbone_calls, request)
        outputs += self._unanswered_call_outputs(response, {o["call_id"] for o in outputs})
        if not outputs:
            return None
        return outputs, final_text

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
                                  ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        outputs: List[Dict[str, Any]] = []
        final_text: Optional[str] = None
        for call_id, tool_name, args in calls:
            if tool_name in ("send_to_user", "approval_with_yes_no_buttons"):
                final_text = str(args.get("text", "")).strip()
                if tool_name == "approval_with_yes_no_buttons":
                    # Stateless, domain-agnostic: just asks WhatsAppHandler to
                    # render the reply as tappable buttons - _finalize_response
                    # reads this flag.
                    self._turn_offered_approval = True
                result_text = "ok"
            else:
                result_text = self._dispatch_resolution_tool(tool_name, args, chat_id)
            outputs.append({"type": "function_call_output", "call_id": call_id, "output": result_text})
        return outputs, final_text

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
            if tool_name in WRITE_TOOL_NAMES:
                self._turn_write_calls.append({"name": tool_name, "arguments": args,
                                               "output": result_text, "error": None})
            outputs.append({"type": "function_call_output", "call_id": call_id, "output": result_text})
        return outputs

    def _run_backbone_calls(self, calls: List[Tuple[str, str, Dict[str, Any]]], request: AIRequest
                             ) -> List[Dict[str, Any]]:
        outputs: List[Dict[str, Any]] = []
        for call_id, tool_name, args in calls:
            if tool_name == "send_progress_update":
                sent = send_progress_update_message(
                    self.denidin, self._turn_telemetry_builder, self._turn_chat_id, args.get("text"),
                )
                # Stored by the send itself (DeniDin.send_progress_update), like every message.
                payload = {"sent": sent}
            else:
                payload = build_react_to_message_payload(
                    self.denidin, request, self._turn_chat_id, args, call_id,
                )
            outputs.append({"type": "function_call_output", "call_id": call_id,
                            "output": json.dumps(payload, ensure_ascii=False)})
        return outputs

    def _call_model(self, context: str, kwargs: Dict[str, Any]) -> Any:
        """One Responses API call, wire-logged both directions, its mcp_call
        items accumulated for this turn, telemetry recorded. 2026-09-30: retries
        explicitly once on an HTTP 424 (a gap the OpenAI SDK's own max_retries
        never covers - see AIManager.call_model_with_retry's docstring),
        the same shared retry AIHandler._timed_llm_call also uses."""
        audit_wire("openai", "out", context, kwargs)
        debug_wire("openai", "out", context, kwargs)
        # Retry + Feature 080 timing via the shared AIManager.timed_model_call (also
        # AIHandler._timed_llm_call's): a failed call is timed and counted too.
        if self._turn_is_approved_write:
            # Same as legacy _call_openai_approval_api (Item4): the OpenAI SDK's own
            # retries are off (max_retries=0) for the turn that runs the approved write;
            # the shared explicit 424 retry still applies.
            response = self.timed_model_call(
                self._turn_telemetry_builder,
                lambda: self.client.with_options(max_retries=0).responses.create(**kwargs),
                context=context,
            )
        else:
            response = self.timed_model_call(
                self._turn_telemetry_builder, lambda: self.client.responses.create(**kwargs), context=context,
            )
        audit_wire("openai", "in", context, response)
        debug_wire("openai", "in", context, response)
        self._turn_mcp_calls.extend(self._extract_mcp_call_items(response))
        self._turn_write_calls.extend(
            item for item in (getattr(response, "output", None) or [])
            if getattr(item, "type", None) == "mcp_call")
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

    def _apply_write_guards(self, request: AIRequest, final_text: str) -> str:
        """Item4 (2026-10-01, revised 2026-10-04): the approved-write checks, on the turn
        that answers approval buttons with a yes (shared AIManager). The model's reply
        is ALWAYS sent as is - the app only ever appends a short factual note after it:
        - the same write succeeded twice with identical arguments (the approved call run
          twice): APPROVED_WRITE_POSSIBLY_DUPLICATED_NOTE;
        - no write was even attempted: APPROVED_WRITE_NOT_PERFORMED_NOTE.
        Failed attempts append nothing - the model saw each error and reports it itself
        (ST14, 2026-10-03: three failed creates were once replaced with a "may have run
        twice" message although nothing was created)."""
        if not self._turn_is_approved_write:
            return final_text
        executions = self.tally_write_executions(self._turn_write_calls, WRITE_TOOL_NAMES)
        if executions.duplicated:
            logger.error(
                "[022] DUPLICATE EXECUTION DETECTED: approved turn for chat=%r request=%s ran %s "
                "successfully more than once with identical arguments. All write calls: %r",
                self._turn_chat_id, request.request_id, executions.duplicated, self._turn_write_calls)
            self._turn_offered_approval = False
            return f"{final_text}\n\n{APPROVED_WRITE_POSSIBLY_DUPLICATED_NOTE}"
        if not executions.ran_any:
            logger.error(
                "[022] APPROVED TOOL NEVER RAN: approved turn for chat=%r request=%s attempted no write. "
                "Reply sent with a note appended: %r", self._turn_chat_id, request.request_id, final_text)
            self._turn_offered_approval = False
            return f"{final_text}\n\n{APPROVED_WRITE_NOT_PERFORMED_NOTE}"
        return final_text

    def _finalize_response(self, request: AIRequest, final_text: str) -> AIResponse:
        """[[NO_REPLY]] sentinel handling via the shared models.message.should_reply_for
        (the same check AIHandler._finalize_response uses).

        offer_approval_buttons (Feature 047 parity): True iff the model called
        `approval_with_yes_no_buttons` THIS turn (self._turn_offered_approval),
        which asks WhatsAppHandler to render the reply as tappable buttons."""
        should_reply = should_reply_for(final_text)
        offer_approval_buttons = bool(self._turn_offered_approval)
        # Same shared post-turn steps as AIHandler._finalize_response (2026-10-01):
        # the possible-fabricated-confirmation warning (tools are always offered on
        # this path), the turn's real token totals / model / finish reason, and the
        # WhatsApp length cut.
        self.log_possible_hallucinated_confirmation(request.request_id, final_text, True, self._turn_mcp_calls)
        last = self._turn_last_response
        model = getattr(last, "model", None)
        finish_reason = self.finish_reason_of(last) if last is not None else "stop"
        total_tokens, prompt_tokens, completion_tokens = self._turn_tokens
        return self.fit_for_whatsapp(AIResponse(
            request_id=request.request_id,
            response_text=final_text,
            tokens_used=total_tokens,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            model=model if isinstance(model, str) and model else request.model,
            finish_reason=finish_reason if isinstance(finish_reason, str) else "stop",
            timestamp=request.timestamp or int(now_local().timestamp()),
            should_reply=should_reply,
            offer_approval_buttons=offer_approval_buttons,
            mcp_calls=list(self._turn_mcp_calls),
        ))

    @staticmethod
    def _create_fallback_response(request_id: str, message: str) -> AIResponse:
        """2026-09-30 consolidation: delegates to AIManager.build_fallback_response,
        the one shared implementation also used by AIHandler._create_fallback_response - the
        two were byte-identical AIResponse shapes before this change. Unlike the legacy
        fallback strings (English, predating this session's Hebrew-only audit), `message`
        here is always one of the Hebrew BACKBONE_* constants in error_messages.py."""
        return AIManager.build_fallback_response(request_id, message)

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
            exclude_message_ids=[exclude_message_id] if exclude_message_id else None,
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

    def record_sent_message_id(self, chat_id: str, message_id: str) -> None:
        """Called by denidin.py right after a reply is actually sent: remembers its
        idMessage so a later tap on an approval-buttons message can be matched against
        it (Feature 047's stale-tap guard)."""
        self.session_manager.set_approval_message_id(chat_id, message_id)

    def resolve_button_tap(self, message: WhatsAppMessage, selected_id: str, stanza_id: str, *,
                           user_role: Optional[str] = None) -> Optional[AIResponse]:
        """Feature 047's stale-tap guard: a tap is live only if its `stanza_id`
        exactly equals the idMessage of the approval-buttons message this chat
        is currently offering (Session.approval_message_id). A stale/superseded/
        already-used tap returns None - the caller sends nothing at all. A live
        tap is consumed and resolved like a typed "כן"/"לא": a synthetic AIRequest
        carrying that answer runs through the ordinary single_turn() loop, where the
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
        return self.single_turn(
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
