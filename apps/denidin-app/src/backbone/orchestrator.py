"""
BackboneOrchestrator (Feature 063) — the new, standalone module implementing the
Backbone-as-tool-orchestrator-kernel architecture. Selected once at startup by
`denidin.py::initialize_app` only when `config.feature_flags['enable_capability_backbone']`
is true; `src/handlers/ai_handler.py` is never imported by, and never imports, this
module (REQ-063-07).

See contracts/capability-resolution-loop.md (the loop) and contracts/prompt-assembly.md
(the prompt-loading/caching + per-call instructions assembly this module implements).
"""
import json
from dataclasses import dataclass
import logging
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from src.backbone.backbone_tools import (
    BACKBONE_TOOLS,
    extract_backbone_tool_calls,
)
from src.backbone.capability_tags import ALWAYS_PRESENT_CAPABILITIES, CapabilityTag, capability_catalog_text
from src.backbone.flow_tags import FlowTag, flow_catalog_text
from src.backbone.loading import apply_loading, describe_loading, parse_requested
from src.backbone.prompt_cache import MtimePromptCache
from src.backbone.orchestration_tools import ORCHESTRATION_TOOLS, extract_orchestration_tool_calls
from src.capabilities.toolsets import (
    build_capability_tools,
    dispatch_local_tool,
    extract_local_calls,
    local_tool_owners,
)
from src.constants.error_messages import BACKBONE_UNEXPECTED_ERROR
from src.models.config import AppConfiguration
from src.models.message import AIRequest, AIResponse, NO_REPLY_SENTINEL
from src.models.user import Role
from src.utils.capability_audit_log import log_capability_action, log_loading_action
from src.utils.logger import read_version, DEFAULT_VERSION_FILE
from src.tool_actions.messaging_actions import (
    build_react_to_message_payload, send_progress_update_message,
)
from src.tool_actions.model_call_actions import (
    build_fallback_response, call_model_with_retry, record_exchange as shared_record_exchange,
)
from src.utils.wire_log import audit_wire, debug_wire
from src.utils.time_utils import now_local, local_from_timestamp

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _TurnParties:
    """Who/where one turn is with - the values _finalize_response/_persist_turn
    need to store the turn on the right session (bundled to keep signatures small)."""
    chat_id: str
    role: Role
    sender: Optional[str]
    user_phone: Optional[str]
    sender_phone: Optional[str]
    is_group: bool
    chat_name: Optional[str]

# A generous bound, never expected to bind in practice, existing purely so a
# pathological back-and-forth can't loop forever. Raised 10 -> 100 (2026-09-28)
# after the mandatory-every-interaction send_progress_update wording pushed
# ordinary multi-step turns (e.g. a ledger query needing two searches) past
# the old cap of 10, which silently dropped a genuinely-produced final
# send_to_user answer - see the loop-cap fallback's own known bug noted below.
MAX_BACKBONE_TOOL_LOOP_ITERATIONS = 100

# 2026-09-15: standalone equivalent of ai_handler.py's _MIN_PLAUSIBLE_SOURCE_EPOCH
# (REQ-063-07 - never imported from there). A plausible real WhatsApp send epoch
# floor (2020-01-01 UTC) - a malformed webhook/test sentinel timestamp below this
# falls back to None (processing time) rather than landing a persisted message in
# 1970, same reasoning as the legacy constant.
_MIN_PLAUSIBLE_SOURCE_EPOCH = 1_577_836_800

_DEFAULT_BACKBONE_CONFIG = {
    "file": "backbone.md",
    "base_dir": "config",
    "prompts_dir": "prompts",
    "capabilities_dir": "capabilities",
}


class BackboneOrchestrator:  # pylint: disable=too-many-instance-attributes
    """The new orchestrator kernel. Exposes the same interface
    `denidin.py`'s routing layer already calls against `AIHandler`
    (`get_response`, `resolve_button_tap`), so the rest of the app is unaware
    which implementation it is talking to (REQ-063-07)."""

    def __init__(self, ai_client: Any, config: AppConfiguration, *,
                 session_manager: Any,
                 reminder_manager: Optional[Any] = None,
                 ledger_event_manager: Optional[Any] = None,
                 morning_mcp_locator: Optional[Any] = None,
                 green_api_bot: Optional[Any] = None,
                 memory_manager: Optional[Any] = None,
                 user_manager: Optional[Any] = None,
                 own_whatsapp_number: str = "",
                 telemetry_manager: Optional[Any] = None,
                 fee_agreement_tools: Optional[Any] = None,
                 whatsapp_handler: Optional[Any] = None):
        self.client = ai_client
        self.config = config
        self.reminder_manager = reminder_manager
        self.ledger_event_manager = ledger_event_manager
        self.morning_mcp_locator = morning_mcp_locator
        # green_api_bot (2026-09-14): the SAME live bot instance AIHandler already
        # uses for react_to_message's real send_reaction side effect (Feature 084)
        # - shared, unmodified (REQ-063-03). None is tolerated (unit tests, or a
        # misconfigured process) - a reaction call is then a logged no-op, never
        # a crash (mirrors send_reaction's own "never raises" contract).
        self.green_api_bot = green_api_bot
        # session_manager: the SAME SessionManager instance AIHandler already uses
        # (REQ-063-03) - gives every round this turn real conversation history via
        # get_rolling_window, same shape/source the legacy path has always used,
        # and is the sole home of the loaded-capability set. Required: the app
        # cannot run without it.
        self.session_manager = session_manager
        # memory_manager/user_manager/own_whatsapp_number (2026-09-15, closing a
        # real gap found by full re-audit against spec.md/plan.md: session
        # persistence AND long-term memory recall were never wired into this
        # orchestrator at all - every flag-on turn's rolling window and recalled
        # memories were silently empty, forever, regardless of prior turns. All
        # three are the SAME shared instances AIHandler already owns (REQ-063-03) -
        # memory_manager for ChromaDB daily_summary recall, user_manager only for
        # RBAC-scoped recall (allowed_memory_scopes/can_see_all_memories), and
        # own_whatsapp_number for the assistant message's own persisted sender JID
        # (mirrors AIHandler.own_whatsapp_number, resolved once at startup).
        self.memory_manager = memory_manager
        self.user_manager = user_manager
        self.own_whatsapp_number = own_whatsapp_number
        # telemetry_manager (2026-09-15, closing a real gap: Feature 080's
        # per-request latency/token telemetry was never wired into this
        # orchestrator at all - every flag-on turn wrote zero RequestTelemetry
        # rows, silently, forever). The SAME shared TelemetryManager instance
        # AIHandler already owns (REQ-063-03) - None whenever the flag is off or
        # telemetry was never configured, same "complete no-op" contract
        # AIHandler.get_response's own docstring describes. Unlike the legacy
        # path's contextvar-based threading (needed because AIHandler's OpenAI
        # call sites are spread across many separate methods), this orchestrator
        # already threads all per-turn state as plain instance attributes (see
        # _turn_mcp_calls etc. above), so a TelemetryBuilder is simply one more
        # such attribute (_turn_telemetry_builder, set in get_response) -
        # simpler, same end result.
        self.telemetry_manager = telemetry_manager
        self._turn_telemetry_builder: Optional[Any] = None
        # fee_agreement_tools/whatsapp_handler (2026-09-16, cap_docx_write capability,
        # resolution redesign): the SAME FeeAgreementToolHandler/
        # WhatsAppHandler instances ai_handler.py already owns (REQ-063-03) - None
        # tolerated (unit tests, or a misconfigured process), in which case
        # cap_docx_write returns a friendly "not configured" text rather than crashing.
        self.fee_agreement_tools = fee_agreement_tools
        self.whatsapp_handler = whatsapp_handler
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
        # schema). Reset every turn in get_response.
        self._turn_planning_status: Optional[str] = None

        self._backbone_content: str = ""
        self._backbone_mtime: Optional[float] = None
        self._capability_prompts = MtimePromptCache("capability", self._capabilities_dir)
        self._flow_prompts = MtimePromptCache("flow", self._flows_dir)
        self._user_memory_content: str = ""
        self._user_memory_mtime: Optional[float] = None

        # Set once per get_response() call, read by the orchestration loop for
        # every round within that SAME turn (2026-09-14). Deliberately a plain
        # instance attribute, not threaded as an explicit parameter through
        # every one of the ~6 call sites across src/capabilities/* + planning.py
        # - this process handles one webhook turn at a time (same assumption
        # AIHandler.own_whatsapp_number already makes), so there is no real
        # concurrent-turn clobbering risk in practice.
        self._turn_conversation_history: List[Dict[str, Any]] = []

        # Set once per get_response() call, same lifecycle/reasoning as
        # _turn_conversation_history above - read by the loop's
        # backbone-tool resolution (send_progress_update/react_to_message) for
        # every round this turn makes.
        self._turn_progress_callback: Optional[Callable[[str], None]] = None
        self._turn_chat_id: Optional[str] = None
        self._turn_message_id: Optional[str] = None

        # Set False at the top of every get_response() call; flipped True by
        # ApprovalCapability.handle() iff the approval capability was used
        # THIS turn (2026-09-16) - _finalize_response reads this instead of
        # checking pending-approval managers to decide whether to offer
        # WhatsApp interactive buttons, now that cap_reminders_write creates no
        # pending-approval record of its own.
        self._turn_offered_approval: bool = False

        # Set once per get_response() call (2026-09-15) - the ChromaDB
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
                            *, active_flows: Optional[List[FlowTag]] = None) -> str:
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
        failure (2026-09-14, this orchestrator regressed on it by injecting only the
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
        flow_catalog = flow_catalog_text(list(FlowTag))
        loaded_line = (
            "## Loaded flows\n\n" + (", ".join(f.value for f in flows) if flows else "(none)")
            + "\n\n## Loaded capabilities\n\n"
            + (", ".join(t.value for t in tags) if tags else "(none - plain backbone)")
        )
        parts = [
            self.load_backbone(),
            *[self._capability_prompts.get(name) for name in ALWAYS_PRESENT_CAPABILITIES],
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
        here as new code (REQ-063-07)."""
        return [
            {
                "name": item.name,
                "error": item.error,
                "arguments": item.arguments,
                "output": item.output,
            }
            for item in (response.output or [])
            if getattr(item, "type", None) == "mcp_call"
        ]

    # ------------------------------------------------------------------
    # The orchestration loop (contracts/capability-resolution-loop.md)
    # ------------------------------------------------------------------

    def get_response(  # pylint: disable=too-many-locals
            self, request: AIRequest, chat_id: Optional[str] = None, *,
            user_role: str = "client", sender: Optional[str] = None,
            recipient: Optional[str] = None, user_phone: Optional[str] = None,
            is_group: bool = False, chat_name: Optional[str] = None,
            sender_phone: Optional[str] = None,
            progress_callback: Optional[Callable[[str], None]] = None,
            is_media: bool = False,
            media_extraction: Optional[Dict[str, Any]] = None,
            media: Optional[Any] = None,
            media_type: Optional[str] = None) -> AIResponse:
        """The orchestrator's entry point — same shape `AIHandler.get_response` already
        exposes, so denidin.py's calling code is unaffected by which implementation
        produced the returned AIResponse (REQ-063-07).

        media_extraction: an ALREADY-computed extraction result
        (extracted_text/document_analysis/media_type), when a caller has one to hand
        (e.g. a test fixture, or a future caller of this method directly). None for
        a text turn.

        media/media_type (2026-09-15, REQ-063-04a real design): the RAW, not-yet-
        extracted media for a media turn — denidin.py's flag-on media dispatch
        downloads and validates the file (reusing the unmodified low-level
        `MediaFileManager.download_file`/`validate_file_size`/`validate_format`,
        REQ-063-03), builds a `Media` object, and hands it here as-is, WITHOUT
        running any extraction call first. This is the real design per
        contracts/capability-resolution-loop.md: the model is told only "media
        attached, type X, caption Y" — no content — and itself CHOOSES whether
        to `load_capabilities(["cap_media_analysis"])` and call its `analyze_media` tool;
        only then does `src/capabilities/media_analysis/handler.py` make the
        real vision/PDF/DOCX extraction call, via `turn_context["media"]`/
        `["media_type"]` below. media_extraction (above) and media/media_type are
        mutually exclusive in practice — a caller passes at most one.
        """
        # The ENTIRE turn below is wrapped in one top-level try/except, mirroring
        # AIHandler._get_response_impl's own APITimeoutError/RateLimitError/
        # APIError/Exception -> friendly fallback safety net: anything that raises
        # (memory recall, session persistence, finalize, a model call) replies
        # with a friendly fallback instead of crashing the turn.
        # Feature 080 telemetry (2026-09-15, closing a real gap - see __init__'s
        # telemetry_manager docstring): one TelemetryBuilder per turn, recorded in
        # the `finally` below regardless of how the turn ends (success or the
        # except above) - mirrors AIHandler.get_response's own
        # "success OR exception" recording contract exactly. Complete no-op
        # whenever self.telemetry_manager is None.
        effective_chat_id_for_telemetry = chat_id or request.chat_id
        if self.telemetry_manager is not None:
            from src.managers.telemetry_manager import TelemetryBuilder  # pylint: disable=import-outside-toplevel
            self._turn_telemetry_builder = TelemetryBuilder(
                request.request_id, effective_chat_id_for_telemetry, now_local().isoformat(),
            )
        else:
            self._turn_telemetry_builder = None
        try:
            role = self._resolve_role(user_role)
            effective_chat_id = chat_id or request.chat_id
            # Backbone-tool dispatch context (2026-09-14, same per-turn-instance-attribute
            # lifecycle/reasoning as _turn_conversation_history) - progress_callback is
            # the caller's real "send this text to the user right now" hook
            # (denidin.py's notification.answer wrapper in production), chat_id/
            # message_id are react_to_message's real dispatch target/default.
            self._turn_progress_callback = progress_callback
            self._turn_chat_id = effective_chat_id
            self._turn_message_id = request.message_id
            # Reset per-turn MCP-call accumulator (2026-09-15) - see __init__'s
            # _turn_mcp_calls docstring.
            self._turn_mcp_calls = []
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
                "media_extraction": media_extraction,
                "media": media,
                "media_type": media_type,
                "timestamp": request.timestamp,
            }

            # Conversation history (2026-09-14): the SAME rolling-window shape/source
            # AIHandler._call_openai_api already uses (SessionManager.get_rolling_window,
            # oldest-first, role-token-capped) - godfather/admin-only scope for now
            # (explicit decision - client role isn't exercised through this orchestrator
            # yet), so the token cap always uses the godfather/admin limit. Set once here,
            # read by the loop for every round this turn makes (see that
            # method's own docstring for why this is a plain instance attribute rather
            # than threaded through every call site).
            self._turn_conversation_history = self._load_conversation_history(effective_chat_id)

            # The tool-driven orchestration loop (see
            # contracts/capability-resolution-loop.md): one continuous conversation
            # driven by load_capabilities/unload_capabilities/load_flows/unload_flows/reset_to_backbone/
            # record_planning_status/approval_with_yes_no_buttons/send_to_user.
            self._turn_planning_status = None
            # Any new turn supersedes whatever approval buttons were outstanding.
            if effective_chat_id:
                self.session_manager.set_approval_message_id(effective_chat_id, None)
            final_text = self._run_orchestration_loop(request, turn_context, is_media=is_media)

            parties = _TurnParties(
                effective_chat_id, role, sender, user_phone, sender_phone, is_group, chat_name,
            )
            return self._finalize_response(request, final_text, parties)
        except Exception as exc:  # pylint: disable=broad-except
            logger.error(
                "Unexpected error in BackboneOrchestrator.get_response for request %s: %s",
                request.request_id, exc, exc_info=True,
            )
            # 2026-09-30 (closing a real gap): persist what the user sent and the
            # fallback text they're about to be told, the same as AIHandler's own
            # _fallback_and_persist - previously an exception here (e.g. an OpenAI
            # 424 on an image turn) left the user's message, and any image, with
            # no record in the session at all. effective_chat_id may not exist yet
            # if the exception happened before it was computed above, so it's
            # re-derived here rather than assumed.
            shared_record_exchange(
                self.session_manager, memory_enabled=True,
                rbac_enabled=bool(self.user_manager), user_manager=self.user_manager,
                own_whatsapp_number=self.own_whatsapp_number,
                chat_id=chat_id or request.chat_id, user_text=request.user_prompt,
                assistant_text=BACKBONE_UNEXPECTED_ERROR, sender_phone=sender_phone or user_phone,
                sender_display=sender, is_group=is_group, chat_name=chat_name,
                whatsapp_id_message=getattr(request.original_message, "whatsapp_id_message", None),
                source_timestamp=request.timestamp,
            )
            return self._create_fallback_response(request.request_id, BACKBONE_UNEXPECTED_ERROR)
        finally:
            if self._turn_telemetry_builder is not None and self.telemetry_manager is not None:
                try:
                    record = self._turn_telemetry_builder.finalize(now_local().isoformat())
                    self.telemetry_manager.record(record)
                except Exception as telemetry_error:  # pylint: disable=broad-except
                    logger.warning("Feature 080 telemetry finalize/record failed: %s", telemetry_error)

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
        AND `tools` (orchestration + backbone + each loaded capability's real
        tools) - both from the SAME set, so a prompt is never attached
        without its tools (the root cause of the original bug), and
        previous_response_id chaining - which retains neither - never loses
        either. Returns (tags, instructions, tools)."""
        tags = self._get_active_tags(chat_id)
        tools = list(ORCHESTRATION_TOOLS) + list(BACKBONE_TOOLS) + build_capability_tools(self, tags, turn_context)
        instructions = self.build_instructions(
            tags, "", request.timestamp, active_flows=self._get_active_flows(chat_id))
        return tags, instructions, tools

    # ------------------------------------------------------------------
    # The orchestration loop (contracts/capability-resolution-loop.md)
    # ------------------------------------------------------------------

    def _run_orchestration_loop(self, request: AIRequest, turn_context: Dict[str, Any],
                                 *, is_media: bool = False) -> str:
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
        del is_media  # the model itself judges media-attached state from turn_context/backbone.md
        chat_id = turn_context.get("chat_id")
        tags, instructions, tools = self._build_round_inputs(request, chat_id, turn_context)
        input_items = list(self._turn_conversation_history)
        input_items.append({"role": "user", "content": request.user_prompt})

        response = self._call_model("_run_orchestration_loop (first round)", {
            "model": request.model,
            "instructions": instructions,
            "input": input_items,
            "max_output_tokens": request.max_tokens,
            "tools": tools,
        })

        for _loop_round in range(MAX_BACKBONE_TOOL_LOOP_ITERATIONS):
            round_result = self._execute_round_calls(
                request, turn_context, chat_id=chat_id, tags=tags, response=response)
            if round_result is None:
                return (getattr(response, "output_text", "") or "").strip() or NO_REPLY_SENTINEL
            outputs, final_text = round_result
            if final_text is not None:
                return final_text or NO_REPLY_SENTINEL

            try:
                # Recompute BOTH instructions and tools from the (possibly
                # just-mutated) persisted set - previous_response_id retains
                # neither.
                tags, instructions, tools = self._build_round_inputs(request, chat_id, turn_context)
                response = self._call_model("_run_orchestration_loop (follow-up)", {
                    "model": request.model,
                    "instructions": instructions,
                    "input": outputs,
                    "previous_response_id": getattr(response, "id", None),
                    "max_output_tokens": request.max_tokens,
                    "tools": tools,
                })
            except Exception as exc:  # pylint: disable=broad-except
                logger.error("Orchestration-loop follow-up call failed (non-fatal): %s", exc)
                return (getattr(response, "output_text", "") or "").strip() or NO_REPLY_SENTINEL

        logger.warning(
            "Orchestration loop hit MAX_BACKBONE_TOOL_LOOP_ITERATIONS=%d for request %s "
            "without a send_to_user call - returning whatever text the last round carries.",
            MAX_BACKBONE_TOOL_LOOP_ITERATIONS, request.request_id,
        )
        return (getattr(response, "output_text", "") or "").strip() or NO_REPLY_SENTINEL

    def _execute_round_calls(self, request: AIRequest, turn_context: Dict[str, Any], *, chat_id: str,
                              tags: List[CapabilityTag], response: Any
                              ) -> Optional[Tuple[List[Dict[str, Any]], Optional[str]]]:
        """Executes every tool call in one round's `response`: returns None when
        it carries no calls at all (plain text - the loop ends), else
        (function_call_output items for the next round, the reply text if the
        model called send_to_user/approval_with_yes_no_buttons this round)."""
        orchestration_calls = extract_orchestration_tool_calls(response)
        backbone_calls = extract_backbone_tool_calls(response)
        domain_calls = extract_local_calls(response, local_tool_owners(self, tags, turn_context))
        if not orchestration_calls and not backbone_calls and not domain_calls:
            return None
        outputs, final_text = self._run_orchestration_calls(orchestration_calls, chat_id)
        outputs += self._run_domain_calls(domain_calls, turn_context)
        outputs += self._run_backbone_calls(backbone_calls, request)
        return outputs, final_text

    def _run_orchestration_calls(self, calls: List[Tuple[str, str, Dict[str, Any]]], chat_id: str
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
                result_text = self._dispatch_orchestration_tool(tool_name, args, chat_id)
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
            outputs.append({"type": "function_call_output", "call_id": call_id, "output": result_text})
        return outputs

    def _run_backbone_calls(self, calls: List[Tuple[str, str, Dict[str, Any]]], request: AIRequest
                             ) -> List[Dict[str, Any]]:
        outputs: List[Dict[str, Any]] = []
        for call_id, tool_name, args in calls:
            if tool_name == "send_progress_update":
                payload = {"sent": send_progress_update_message(
                    self._turn_progress_callback, self._turn_telemetry_builder,
                    self._turn_chat_id, args.get("text"),
                )}
            else:
                payload = build_react_to_message_payload(
                    self.green_api_bot, self.session_manager, request, self._turn_chat_id, args, call_id,
                )
            outputs.append({"type": "function_call_output", "call_id": call_id,
                            "output": json.dumps(payload, ensure_ascii=False)})
        return outputs

    def _call_model(self, context: str, kwargs: Dict[str, Any]) -> Any:
        """One Responses API call, wire-logged both directions, its mcp_call
        items accumulated for this turn, telemetry recorded. 2026-09-30: retries
        explicitly once on an HTTP 424 (a gap the OpenAI SDK's own max_retries
        never covers - see model_call_actions.call_model_with_retry's docstring),
        the same shared retry AIHandler._timed_llm_call also uses."""
        audit_wire("openai", "out", context, kwargs)
        debug_wire("openai", "out", context, kwargs)
        start = time.monotonic()
        response = call_model_with_retry(
            lambda: self.client.responses.create(**kwargs), context=context,
        )
        duration_ms = (time.monotonic() - start) * 1000
        audit_wire("openai", "in", context, response)
        debug_wire("openai", "in", context, response)
        self._turn_mcp_calls.extend(self._extract_mcp_call_items(response))
        if self._turn_telemetry_builder is not None:
            usage = getattr(response, "usage", None)
            self._turn_telemetry_builder.record_llm_call(
                int(duration_ms),
                int(getattr(usage, "input_tokens", 0) or 0),
                int(getattr(usage, "output_tokens", 0) or 0),
            )
        return response

    def _dispatch_orchestration_tool(self, tool_name: str, args: Dict[str, Any], chat_id: str) -> str:
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
            return f"error: unknown orchestration tool {tool_name!r}"
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

    def _finalize_response(self, request: AIRequest, final_text: str, parties: _TurnParties) -> AIResponse:
        """Same [[NO_REPLY]] sentinel handling as AIHandler._finalize_response
        (contracts/capability-resolution-loop.md) — reimplemented here, not shared
        code, per REQ-063-07.

        offer_approval_buttons (Feature 047 parity): True iff the model called
        `approval_with_yes_no_buttons` THIS turn (self._turn_offered_approval),
        which asks WhatsAppHandler to render the reply as tappable buttons."""
        should_reply = final_text.strip() != NO_REPLY_SENTINEL
        offer_approval_buttons = bool(self._turn_offered_approval)
        self._persist_turn(request, final_text, should_reply, parties)
        return AIResponse(
            request_id=request.request_id,
            response_text=final_text,
            tokens_used=0,
            prompt_tokens=0,
            completion_tokens=0,
            model=request.model,
            finish_reason="stop",
            timestamp=request.timestamp or int(now_local().timestamp()),
            should_reply=should_reply,
            offer_approval_buttons=offer_approval_buttons,
            mcp_calls=list(self._turn_mcp_calls),
        )

    @staticmethod
    def _create_fallback_response(request_id: str, message: str) -> AIResponse:
        """2026-09-30 consolidation: delegates to model_call_actions.build_fallback_response,
        the one shared implementation also used by AIHandler._create_fallback_response - the
        two were byte-identical AIResponse shapes before this change. Unlike the legacy
        fallback strings (English, predating this session's Hebrew-only audit), `message`
        here is always one of the Hebrew BACKBONE_* constants in error_messages.py."""
        return build_fallback_response(request_id, message)

    @staticmethod
    def _resolve_role(user_role: str) -> Role:
        try:
            return Role(user_role.upper())
        except ValueError:
            return Role.CLIENT

    def _load_conversation_history(self, chat_id: Optional[str]) -> List[Dict[str, Any]]:
        """Same source/shape as AIHandler._call_openai_api's own conversation_history
        (SessionManager.get_rolling_window - oldest-first {"role", "content"} dicts,
        role-token-capped). Godfather/Admin-only scope for now (explicit decision,
        2026-09-14) - always uses the godfather/admin token limit from
        config.memory['session']['max_tokens_by_role'], same default AIHandler falls
        back to. Returns [] (never raises) when session_manager isn't configured or
        the lookup fails - a turn with no history is a degraded turn, not a crashed
        one, matching AIHandler's own try/except around this same call."""
        if not chat_id:
            return []
        try:
            session_config = (self.config.memory or {}).get('session', {})
            window_days = session_config.get('window_days', 14)
            max_tokens = session_config.get('max_tokens_by_role', {}).get('godfather', 100000)
            history = self.session_manager.get_rolling_window(
                chat_id, window_days=window_days, max_tokens=max_tokens,
            )
            return list(history) if history else []
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Failed to load conversation history for %s: %s", chat_id, exc)
            return []

    def _recall_memory(self, user_prompt: str, chat_id: Optional[str],
                        user_phone: Optional[str], sender_phone: Optional[str]) -> str:
        """2026-09-15 (closing a real gap - long-term memory recall was never
        wired into this orchestrator at all). Mirrors
        AIHandler.create_request's own recall block (ai_handler.py ~2095-2131):
        a single ChromaDB `daily_summary` semantic-similarity query over this
        chat's own collection, RBAC-filtered by the resolving user's
        allowed_memory_scopes/can_see_all_memories when user_manager is
        available (same `recall_with_rbac_filter` call legacy makes), else a
        plain `recall` call. Returns a "" (never raises) on any failure or
        when nothing relevant is found - a turn with no recalled memory is a
        degraded turn, not a crashed one, matching AIHandler's own
        try/except around this same call."""
        if self.memory_manager is None or not chat_id:
            return ""
        try:
            # pylint: disable=import-outside-toplevel
            from src.managers.memory_collections import collection_name_for_chat
            collection_name = collection_name_for_chat(chat_id)
            longterm_config = (self.config.memory or {}).get('longterm', {})
            top_k = longterm_config.get('daily_summary_top_k', 10)
            min_similarity = longterm_config.get('min_similarity', 0.7)

            effective_user_phone = user_phone or sender_phone
            if self.user_manager is not None and effective_user_phone:
                user = self.user_manager.get_user(effective_user_phone)
                recalled = self.memory_manager.recall_with_rbac_filter(
                    query=user_prompt,
                    collection_names=[collection_name],
                    user_phone=effective_user_phone,
                    allowed_scopes=user.allowed_memory_scopes,
                    can_see_all_memories=user.can_see_all_memories,
                    top_k=top_k,
                    min_similarity=min_similarity,
                )
            else:
                recalled = self.memory_manager.recall(
                    query=user_prompt,
                    collection_names=[collection_name],
                    top_k=top_k,
                    min_similarity=min_similarity,
                )
            if not recalled:
                return ""
            lines = "\n".join(
                f"- {mem['content']} (relevance: {mem['similarity']:.2f})" for mem in recalled
            )
            return f"RECALLED MEMORIES (from past conversations):\n{lines}"
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Failed to recall memories for %s: %s", chat_id, exc)
            return ""

    def _persist_turn(self, request: AIRequest, final_text: str, should_reply: bool,
                       parties: _TurnParties) -> None:
        """2026-09-15 (closing a real gap - flag-on turns never persisted a
        single message to the session; every rolling-window read this
        orchestrator itself does was reading a session that this orchestrator
        never wrote to). New, standalone code mirroring
        AIHandler.get_response's own persistence block (ai_handler.py
        ~3746-3862) shape-for-shape (RBAC-token-limited storage,
        sender/recipient JID resolution, source timestamps) so the rolling
        window, post-turn ledger recognition, and the nightly daily-summary
        roll all see flag-on turns exactly as they'd see a flag-off turn —
        REQ-063-05. Best-effort: any failure is logged, never raised (a
        storage failure must not turn an already-composed, already-sendable
        reply into a hard error)."""
        try:
            own_number_jid = f"{self.own_whatsapp_number}@c.us" if self.own_whatsapp_number else None
            resolved_sender_phone = parties.sender_phone or parties.user_phone or (
                parties.chat_id if not parties.is_group else None
            )
            user_msg_recipient = parties.chat_id if parties.is_group else own_number_jid
            user_msg_recipient_name = (parties.chat_name or parties.chat_id) if parties.is_group else "DeniDin"
            assistant_msg_recipient = parties.chat_id if parties.is_group else resolved_sender_phone
            assistant_msg_recipient_name = (
                (parties.chat_name or parties.chat_id) if parties.is_group else parties.sender
            )

            source_epoch = request.timestamp if (
                request.timestamp is not None and request.timestamp >= _MIN_PLAUSIBLE_SOURCE_EPOCH
            ) else None
            source_ts = None if source_epoch is None else local_from_timestamp(source_epoch)

            self.session_manager.add_message_with_tokens(
                chat_id=parties.chat_id,
                role="user",
                content=request.user_prompt,
                user_role=parties.role,
                sender=resolved_sender_phone,
                sender_name=parties.sender,
                recipient=user_msg_recipient,
                recipient_name=user_msg_recipient_name,
                message_id=request.message_id,
                timestamp=source_ts,
            )
            if should_reply:
                self.session_manager.add_message_with_tokens(
                    chat_id=parties.chat_id,
                    role="assistant",
                    content=final_text,
                    user_role=parties.role,
                    sender=own_number_jid,
                    sender_name="DeniDin",
                    recipient=assistant_msg_recipient,
                    recipient_name=assistant_msg_recipient_name,
                    mcp_calls=list(self._turn_mcp_calls),
                    timestamp=source_ts,
                )
            # record_planning_status (2026-09-16): the ONLY new persisted
            # cross-turn state the resolution redesign adds - a plain,
            # clearly-tagged internal-note history entry, persisted via this
            # SAME add_message_with_tokens call (never merged into the real
            # send_to_user reply above). Flows back into the next turn purely
            # via the existing rolling-window conversation history - no new
            # store, no schema. Persisted regardless of should_reply (a
            # [[NO_REPLY]] turn can still usefully record status).
            if self._turn_planning_status:
                self.session_manager.add_message_with_tokens(
                    chat_id=parties.chat_id,
                    role="assistant",
                    content=f"[[INTERNAL_PLANNING_NOTE]]\n{self._turn_planning_status}",
                    user_role=parties.role,
                    sender=own_number_jid,
                    sender_name="DeniDin",
                    recipient=assistant_msg_recipient,
                    recipient_name=assistant_msg_recipient_name,
                    timestamp=source_ts,
                )
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Failed to persist turn to session %s: %s", parties.chat_id, exc)

    # ------------------------------------------------------------------
    # Button-tap resolution (a tap is just an ordinary "כן"/"לא" turn)
    # ------------------------------------------------------------------

    def record_approval_message_id(self, chat_id: str, message_id: str) -> None:
        """Called by denidin.py right after an approval-buttons message is
        actually sent: remembers its idMessage so a later tap can be matched
        against it (Feature 047's stale-tap guard)."""
        self.session_manager.set_approval_message_id(chat_id, message_id)

    def resolve_button_tap(self, chat_id: str, stanza_id: str, request: AIRequest, *,
                            user_role: str = "godfather") -> Optional[AIResponse]:
        """Feature 047's stale-tap guard: a tap is live only if its `stanza_id`
        exactly equals the idMessage of the approval-buttons message this chat
        is currently offering (Session.approval_message_id). A stale/superseded/
        already-used tap returns None - the caller sends nothing at all. A live
        tap is consumed (cleared, so a second tap on the same message is stale)
        and then resolved like a typed "כן"/"לא": `request` is the caller's
        synthetic "כן"/"לא" AIRequest, run through the ordinary get_response()
        loop, where the model reads its own history and acts on the answer."""
        if self.session_manager.get_session(chat_id).approval_message_id != stanza_id:
            logger.info("[047] Stale button tap ignored: chat=%r stanza_id=%r", chat_id, stanza_id)
            return None
        return self.get_response(request, chat_id=chat_id, user_role=user_role)
