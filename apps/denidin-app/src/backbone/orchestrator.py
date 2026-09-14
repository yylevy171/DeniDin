"""
BackboneOrchestrator (Feature 063) — the new, standalone module implementing the
Backbone-as-tool-orchestrator-kernel architecture. Selected once at startup by
`denidin.py::initialize_app` only when `config.feature_flags['enable_capability_backbone']`
is true; `src/handlers/ai_handler.py` is never imported by, and never imports, this
module (REQ-063-07).

See contracts/orchestration-loop.md (the loop) and contracts/prompt-assembly.md
(the prompt-loading/caching + per-call instructions assembly this module implements).
"""
import logging
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from src.backbone.capability_tags import CapabilityTag, DOMAIN_CAPABILITY_TAGS, capability_catalog_text
from src.backbone.intent_identification import identify_intent
from src.backbone.planning import Plan, build_plan, role_allowed_capabilities
from src.models.config import AppConfiguration
from src.models.message import AIRequest, AIResponse, NO_REPLY_SENTINEL
from src.models.user import Role
from src.utils.time_utils import now_local, local_from_timestamp

logger = logging.getLogger(__name__)

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

    def __init__(self, ai_client: Any, config: AppConfiguration,  # pylint: disable=too-many-positional-arguments
                 reminder_manager: Optional[Any] = None,
                 ledger_event_manager: Optional[Any] = None,
                 pending_local_tool_approval_manager: Optional[Any] = None,
                 morning_mcp_locator: Optional[Any] = None,
                 session_manager: Optional[Any] = None,
                 pending_approval_manager: Optional[Any] = None):
        self.client = ai_client
        self.config = config
        self.reminder_manager = reminder_manager
        self.ledger_event_manager = ledger_event_manager
        self.pending_local_tool_approval_manager = pending_local_tool_approval_manager
        self.morning_mcp_locator = morning_mcp_locator
        # pending_approval_manager (2026-09-14): the SAME PendingApprovalManager
        # instance AIHandler already uses for MCP document-creation approvals
        # (Feature 022) - shared, unmodified (REQ-063-03), now also populated by
        # this orchestrator's own invoicing_write step.
        self.pending_approval_manager = pending_approval_manager
        # session_manager: the SAME SessionManager instance AIHandler already uses
        # (REQ-063-03) - gives every step this turn real conversation history via
        # get_rolling_window, same shape/source the legacy path has always used.
        # None is tolerated (unit tests, or a misconfigured process) - a turn just
        # runs with no history rather than crashing.
        self.session_manager = session_manager

        backbone_config = dict(_DEFAULT_BACKBONE_CONFIG)
        backbone_config.update(config.backbone_config or {})
        self._backbone_config = backbone_config

        self._backbone_content: str = ""
        self._backbone_mtime: Optional[float] = None
        self._capability_content: Dict[str, str] = {}
        self._capability_mtimes: Dict[str, float] = {}
        self._user_memory_content: str = ""
        self._user_memory_mtime: Optional[float] = None

        # Set once per get_response() call, read by call_capability_step() for
        # every step within that SAME turn (2026-09-14). Deliberately a plain
        # instance attribute, not threaded as an explicit parameter through
        # every one of the ~6 call sites across src/capabilities/* + planning.py
        # - this process handles one webhook turn at a time (same assumption
        # AIHandler.own_whatsapp_number already makes), so there is no real
        # concurrent-turn clobbering risk in practice.
        self._turn_conversation_history: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Prompt loading/caching (contracts/prompt-assembly.md)
    # ------------------------------------------------------------------

    def _base_dir(self) -> Path:
        return Path(self._backbone_config.get("base_dir", "config"))

    def _prompts_dir(self) -> Path:
        return self._base_dir() / self._backbone_config.get("prompts_dir", "prompts")

    def _capabilities_dir(self) -> Path:
        return self._prompts_dir() / self._backbone_config.get("capabilities_dir", "capabilities")

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
        """Independent mtime cache per capability tag. Missing file: log WARNING,
        return "" — that capability silently contributes nothing rather than
        crashing the turn (mirrors _load_constitution's fallback pattern)."""
        prompt_path = self._capabilities_dir() / f"{tag.value}.md"
        cache_key = tag.value
        try:
            mtime = prompt_path.stat().st_mtime
        except FileNotFoundError:
            logger.warning("Capability prompt file not found for %s at %s", tag.value, prompt_path)
            return self._capability_content.get(cache_key, "")

        if cache_key not in self._capability_mtimes or mtime != self._capability_mtimes[cache_key]:
            self._capability_content[cache_key] = prompt_path.read_text(encoding="utf-8")
            self._capability_mtimes[cache_key] = mtime
        return self._capability_content[cache_key]

    def build_instructions(self, active_tag: CapabilityTag, accumulated_context: str = "",
                            today_timestamp: Optional[int] = None) -> str:
        """contracts/prompt-assembly.md's fixed assembly order:
        backbone + exactly ONE capability's prompt + accumulated_context + '---' + today.

        Date AND time (not date alone) - mirrors AIHandler._load_constitution's own
        current-date-and-time injection: without a current TIME, the model cannot
        resolve a relative clock offset ("תזכיר לי בעוד שעה") and asks the user what
        time it is instead of just computing it - a real gap the legacy code already
        fixed once for Feature 054 (reminders), confirmed via a real billed-test
        failure (2026-09-14, this orchestrator regressed on it by injecting only the
        date - same billed test caught it here too).
        """
        now = local_from_timestamp(today_timestamp) if today_timestamp else now_local()
        # Capability catalog (2026-09-14): every domain capability's name +
        # one-line description, authored once in capability_tags.py, rendered
        # here so it's part of the same stable instructions prefix every call
        # already shares - not injected per-call by Intent Identification/
        # Planning individually. Godfather/Admin-only scope for now (client role
        # RBAC narrowing is deferred - see role_allowed_capabilities), so the
        # full catalog is always shown unconditionally; parse_plan still drops
        # any step naming a capability this role isn't allowed, unchanged.
        catalog = capability_catalog_text(list(DOMAIN_CAPABILITY_TAGS))
        parts = [
            self.load_backbone(),
            f"## Capabilities\n\n{catalog}" if catalog else "",
            self.load_capability_prompt(active_tag),
            self.load_user_memory(),
        ]
        if accumulated_context:
            parts.append(accumulated_context)
        parts.append("---")
        parts.append(
            f"THE CURRENT DATE AND TIME IS {now.strftime('%Y-%m-%d')} {now.strftime('%H:%M')} "
            f"(Asia/Jerusalem, Israel local time). Treat this as the authoritative \"now\" when "
            f"resolving any relative or partial date/time the user gives (a day/month with no "
            f"year, \"היום\", \"אתמול\", \"בעוד שעה\", \"בעוד חצי שעה\", etc.) — never fall back "
            f"on a year from your training data, and never ask the user what time it is now."
        )
        return "\n\n".join(part for part in parts if part)

    # ------------------------------------------------------------------
    # The single-step OpenAI call primitive every capability step uses
    # ------------------------------------------------------------------

    def call_capability_step(self, tag: CapabilityTag, request: AIRequest,
                              accumulated_context: str = "",
                              tools: Optional[List[Dict]] = None) -> str:
        """Issues one Responses API call with Backbone + exactly one active
        capability's prompt+tools + accumulated context (R3's single-active-capability
        property). Returns the response's plain text output."""
        instructions = self.build_instructions(tag, accumulated_context, request.timestamp)
        # self._turn_conversation_history (2026-09-14): the rolling window computed
        # ONCE in get_response() for this turn, prepended before the current
        # message - same shape/order AIHandler._call_openai_api already uses
        # (oldest-first history, then the current turn), given to every step this
        # turn makes, not just the first.
        input_items = list(self._turn_conversation_history)
        input_items.append({"role": "user", "content": request.user_prompt})
        kwargs: Dict[str, Any] = {
            "model": request.model,
            "instructions": instructions,
            "input": input_items,
            "max_output_tokens": request.max_tokens,
        }
        if tools:
            kwargs["tools"] = tools

        start = time.monotonic()
        response = self.client.responses.create(**kwargs)
        duration_ms = (time.monotonic() - start) * 1000
        usage = getattr(response, "usage", None)
        cached_tokens = getattr(getattr(usage, "input_tokens_details", None), "cached_tokens", None)
        logger.info(
            "Backbone step=%s instructions_bytes=%d duration_ms=%.0f cached_tokens=%s",
            tag.value, len(instructions.encode("utf-8")), duration_ms, cached_tokens,
        )
        return getattr(response, "output_text", "") or ""

    # ------------------------------------------------------------------
    # The orchestration loop (contracts/orchestration-loop.md)
    # ------------------------------------------------------------------

    def get_response(  # pylint: disable=too-many-positional-arguments,too-many-locals
            self, request: AIRequest, chat_id: Optional[str] = None,
            user_role: str = "client", sender: Optional[str] = None,
            recipient: Optional[str] = None, user_phone: Optional[str] = None,
            is_group: bool = False, chat_name: Optional[str] = None,
            sender_phone: Optional[str] = None,
            progress_callback: Optional[Callable[[str], None]] = None,
            is_media: bool = False,
            media_extraction: Optional[Dict[str, Any]] = None) -> AIResponse:
        """The orchestrator's entry point — same shape `AIHandler.get_response` already
        exposes, so denidin.py's calling code is unaffected by which implementation
        produced the returned AIResponse (REQ-063-07).

        media_extraction (2026-09-14): the ALREADY-computed extraction result
        (extracted_text/document_analysis/media_type) for a media turn - denidin.py
        runs the real, unmodified MediaHandler pipeline (download/extract/save/
        session-persist/ledger-stash-detect, REQ-063-03) before this call, not
        inside the plan, so this is real content, not a stub. None for a text turn.
        """
        del sender, recipient, is_group, chat_name, progress_callback

        role = self._resolve_role(user_role)
        effective_chat_id = chat_id or request.chat_id
        turn_context = {
            "role": role,
            "user_phone": user_phone or sender_phone,
            "chat_id": effective_chat_id,
            "sender_phone": sender_phone,
            "media_extraction": media_extraction,
        }

        # Conversation history (2026-09-14): the SAME rolling-window shape/source
        # AIHandler._call_openai_api already uses (SessionManager.get_rolling_window,
        # oldest-first, role-token-capped) - godfather/admin-only scope for now
        # (explicit decision - client role isn't exercised through this orchestrator
        # yet), so the token cap always uses the godfather/admin limit. Set once here,
        # read by call_capability_step for every step this turn makes (see that
        # method's own docstring for why this is a plain instance attribute rather
        # than threaded through every call site).
        self._turn_conversation_history = self._load_conversation_history(effective_chat_id)

        # Feature 063: a typed "כן"/"לא" reply resolves a pending reminders_write
        # local-tool approval BEFORE Intent Identification/Planning run at all -
        # the same gate contracts/local-tool-approval-gate.md and AIHandler's own
        # get_response/_resolve_pending_local_tool_approval already implement,
        # reimplemented here as new code (REQ-063-07). A decline/unrecognized
        # reply returns None and falls through to a normal turn below, same
        # contract as the legacy resolver.
        pending_resolved = self._resolve_pending_local_tool_approval(request, effective_chat_id, turn_context)
        if pending_resolved is not None:
            return pending_resolved

        # Same gate for a pending invoicing_write MCP approval (Feature 022's
        # PendingApprovalManager, shared with ai_handler.py) - checked in the
        # same "before Intent Identification/Planning run at all" position, same
        # decline-returns-None-and-falls-through contract.
        pending_mcp_resolved = self._resolve_pending_mcp_approval(request, effective_chat_id)
        if pending_mcp_resolved is not None:
            return pending_mcp_resolved

        # Step 1: Intent Identification. allowed_tags is computed here, BEFORE Intent
        # Identification runs (not just before Planning, as originally written) -
        # Intent Identification needs to know what domains of capability this role
        # even HAS this turn to correctly recognize which domain a request touches
        # (e.g. "how much was agreed with X" -> Ledger Query's domain), without that
        # requiring per-capability hardcoded phrasing examples in its own prompt file
        # (a real bug found via a billed test, 2026-09-14: with no visibility into the
        # capability catalog at all, Intent Identification didn't just fail to route -
        # it answered the user's question itself, incorrectly, having no way to know a
        # ledger lookup tool existed to route to instead).
        allowed_tags = role_allowed_capabilities(role)
        intent_text = identify_intent(
            self, request, allowed_tags, is_media=is_media, media_extraction=media_extraction,
        )

        # Step 2: Planning
        plan = build_plan(self, request, intent_text, allowed_tags)

        # Step 3: Execution loop (empty plan => step 4 uses Intent Identification's
        # output alone, per contracts/orchestration-loop.md)
        if plan.is_empty:
            final_text = intent_text
        else:
            final_text = self._execute_plan(plan, request, intent_text, turn_context)

        return self._finalize_response(request, final_text, effective_chat_id)

    def _resolve_pending_local_tool_approval(self, request: AIRequest, effective_chat_id: str,
                                              turn_context: Dict[str, Any]) -> Optional[AIResponse]:
        """Only reminders_write populates pending_local_tool_approval_manager today
        (REQ-063-03: shared with ai_handler.py, so a legacy-created pending approval
        is resolvable here too, and vice versa). Lazily imported, same reasoning as
        _resolve_capability_handler above."""
        if self.pending_local_tool_approval_manager is None:
            return None
        # pylint: disable=import-outside-toplevel
        from src.capabilities.reminders.handler import resolve_typed_reply
        literal_sender_phone = (
            request.original_message.sender_id if request.original_message
            else (turn_context.get("user_phone") or effective_chat_id)
        )
        literal_sender_role = str(turn_context.get("role", Role.CLIENT))
        return resolve_typed_reply(
            self, request, effective_chat_id, literal_sender_phone, literal_sender_role,
        )

    def _resolve_pending_mcp_approval(self, request: AIRequest,
                                       effective_chat_id: str) -> Optional[AIResponse]:
        """invoicing_write populates pending_approval_manager - lazily imported,
        same reasoning as _resolve_pending_local_tool_approval above."""
        if self.pending_approval_manager is None:
            return None
        # pylint: disable=import-outside-toplevel
        from src.capabilities.invoicing.handler import resolve_typed_reply as invoicing_resolve_typed_reply
        return invoicing_resolve_typed_reply(self, request, effective_chat_id)

    def _execute_plan(self, plan: Plan, request: AIRequest, intent_text: str,
                       turn_context: Dict[str, Any]) -> str:
        """Executes each step in order, threading prior steps' results into the next
        step's accumulated context (contracts/orchestration-loop.md step 3). A step's
        own failure does not abort the whole plan (logged, continues with an error
        note in the accumulated context)."""
        accumulated_context = f"Intent Identification determined: {intent_text}"
        last_output = intent_text

        for step in plan.steps:
            try:
                handler = self._resolve_capability_handler(step.capability)
                step_output = handler(self, request, accumulated_context, step.note, turn_context)
                accumulated_context += f"\n\n[{step.capability.value}] {step_output}"
                last_output = step_output
            except Exception as exc:  # pylint: disable=broad-except
                logger.error("Plan step %s failed (non-fatal, continuing): %s", step.capability.value, exc)
                accumulated_context += f"\n\n[{step.capability.value}] step failed: {exc}"

        return last_output

    @staticmethod
    def _resolve_capability_handler(tag: CapabilityTag) -> Callable[..., str]:  # pylint: disable=too-many-return-statements
        """Maps a domain CapabilityTag to its capability handler's step entry
        point. Imported lazily to avoid a hard import-time dependency from
        src/backbone on every src/capabilities subpackage."""
        # pylint: disable=import-outside-toplevel
        if tag == CapabilityTag.REMINDERS_READ:
            from src.capabilities.reminders.handler import read as reminders_read
            return reminders_read
        if tag == CapabilityTag.REMINDERS_WRITE:
            from src.capabilities.reminders.handler import propose_write as reminders_write
            return reminders_write
        if tag == CapabilityTag.LEDGER_QUERY:
            from src.capabilities.ledger_events.handler import query as ledger_query
            return ledger_query
        if tag == CapabilityTag.LEDGER_CAPTURE:
            from src.capabilities.ledger_events.handler import capture as ledger_capture
            return ledger_capture
        if tag == CapabilityTag.INVOICING_READ:
            from src.capabilities.invoicing.handler import read_step as invoicing_read
            return invoicing_read
        if tag == CapabilityTag.INVOICING_WRITE:
            from src.capabilities.invoicing.handler import propose_write as invoicing_write
            return invoicing_write
        if tag == CapabilityTag.MEDIA_ANALYSIS:
            from src.capabilities.media_analysis.handler import extract as media_extract
            return media_extract
        raise NotImplementedError(
            f"No capability handler wired yet for {tag.value} "
            "(see tasks.md's 'Deferred' section — write-approval-flow parity is scoped follow-up work)"
        )

    def _finalize_response(self, request: AIRequest, final_text: str,
                            effective_chat_id: Optional[str] = None) -> AIResponse:
        """Same [[NO_REPLY]] sentinel handling as AIHandler._finalize_response
        (contracts/orchestration-loop.md step 4) — reimplemented here, not shared
        code, per REQ-063-07.

        offer_approval_buttons (Feature 047 parity, added 2026-09-14 after a real
        billed-test failure): True iff a reminders_write step just created a NEW
        pending local-tool approval THIS turn. Any approval that existed BEFORE
        this turn was already resolved-or-cleared by
        _resolve_pending_local_tool_approval at the top of get_response (its
        typed-reply resolver clears the manager on every path — approve, decline,
        AND unrecognized — before this turn ever reaches Planning/execution), so a
        pending approval found here can only be one this turn's own
        propose_write just set — same "computed once, lockstep with the actual
        state" property AIHandler's own new_pending_approval_created has, just
        checked by re-reading the shared manager instead of a locally threaded
        bool (mirrors _resolve_pending_local_tool_approval's own reasoning for
        reusing the same shared instance)."""
        should_reply = final_text.strip() != NO_REPLY_SENTINEL
        offer_approval_buttons = bool(effective_chat_id and (
            (self.pending_local_tool_approval_manager is not None
             and self.pending_local_tool_approval_manager.get(effective_chat_id) is not None)
            or (self.pending_approval_manager is not None
                and self.pending_approval_manager.get(effective_chat_id) is not None)
        ))
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
        )

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
        if self.session_manager is None or not chat_id:
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

    # ------------------------------------------------------------------
    # Pending-approval / button-tap resolution (contracts/orchestration-loop.md
    # Non-goals: skips Intent Identification/Planning, resumes the specific
    # pending step directly)
    # ------------------------------------------------------------------

    def resolve_button_tap(self, chat_id: str, selected_id: str, stanza_id: str,
                            request: Optional[AIRequest] = None) -> Optional[AIResponse]:
        """Resolves a WhatsApp interactive-button tap against whichever pending
        approval this chat actually has - at most one populated per chat in
        practice (mirrors denidin.py's own "checks the MCP-pending manager
        first, then the local-tool one" ordering for AIHandler). Returns None
        for a stale tap (no pending approval anywhere, or stanza_id mismatch on
        whichever one exists) — silently ignored, exactly as
        AIHandler.resolve_button_tap's own staleness guard does."""
        # pylint: disable=import-outside-toplevel
        if self.pending_approval_manager is not None:
            from src.capabilities.invoicing.handler import resolve_button_tap as invoicing_resolve_tap
            resolved = invoicing_resolve_tap(self, chat_id, selected_id, stanza_id, request)
            if resolved is not None:
                return resolved

        if self.pending_local_tool_approval_manager is not None:
            from src.capabilities.reminders.handler import resolve_button_tap as reminders_resolve_tap
            return reminders_resolve_tap(self, chat_id, selected_id, stanza_id, request)

        return None
