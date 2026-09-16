"""
BackboneOrchestrator (Feature 063) — the new, standalone module implementing the
Backbone-as-tool-orchestrator-kernel architecture. Selected once at startup by
`denidin.py::initialize_app` only when `config.feature_flags['enable_capability_backbone']`
is true; `src/handlers/ai_handler.py` is never imported by, and never imports, this
module (REQ-063-07).

See contracts/orchestration-loop.md (the loop) and contracts/prompt-assembly.md
(the prompt-loading/caching + per-call instructions assembly this module implements).
"""
import json
import logging
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from src.backbone.backbone_tools import (
    BACKBONE_TOOLS,
    dispatch_react_to_message,
    dispatch_send_progress_update,
    extract_backbone_tool_calls,
)
from src.backbone.capability_tags import CapabilityTag, DOMAIN_CAPABILITY_TAGS, capability_catalog_text
from src.backbone.intent_identification import identify_intent
from src.backbone.planning import Plan, build_plan, role_allowed_capabilities
from src.constants.error_messages import BACKBONE_UNEXPECTED_ERROR
from src.models.config import AppConfiguration
from src.models.message import AIRequest, AIResponse, NO_REPLY_SENTINEL
from src.models.user import Role
from src.utils.time_utils import now_local, local_from_timestamp

logger = logging.getLogger(__name__)

# 2026-09-15 (closing a real gap - see _resolve_backbone_tool_calls' own
# docstring): same value/reasoning as AIHandler's MAX_LOCAL_TOOL_LOOP_ITERATIONS -
# a generous bound, never expected to bind in practice, existing purely so a
# pathological back-and-forth can't loop forever.
MAX_BACKBONE_TOOL_LOOP_ITERATIONS = 10

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

    def __init__(self, ai_client: Any, config: AppConfiguration,  # pylint: disable=too-many-positional-arguments
                 reminder_manager: Optional[Any] = None,
                 ledger_event_manager: Optional[Any] = None,
                 pending_local_tool_approval_manager: Optional[Any] = None,
                 morning_mcp_locator: Optional[Any] = None,
                 session_manager: Optional[Any] = None,
                 pending_approval_manager: Optional[Any] = None,
                 green_api_bot: Optional[Any] = None,
                 memory_manager: Optional[Any] = None,
                 user_manager: Optional[Any] = None,
                 own_whatsapp_number: str = "",
                 telemetry_manager: Optional[Any] = None):
        self.client = ai_client
        self.config = config
        self.reminder_manager = reminder_manager
        self.ledger_event_manager = ledger_event_manager
        self.pending_local_tool_approval_manager = pending_local_tool_approval_manager
        self.morning_mcp_locator = morning_mcp_locator
        # green_api_bot (2026-09-14): the SAME live bot instance AIHandler already
        # uses for react_to_message's real send_reaction side effect (Feature 084)
        # - shared, unmodified (REQ-063-03). None is tolerated (unit tests, or a
        # misconfigured process) - a reaction call is then a logged no-op, never
        # a crash (mirrors send_reaction's own "never raises" contract).
        self.green_api_bot = green_api_bot
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

        # Set once per get_response() call, same lifecycle/reasoning as
        # _turn_conversation_history above - read by call_capability_step's
        # backbone-tool resolution (send_progress_update/react_to_message) for
        # every step this turn makes.
        self._turn_progress_callback: Optional[Callable[[str], None]] = None
        self._turn_chat_id: Optional[str] = None
        self._turn_message_id: Optional[str] = None

        # Set once per get_response() call (2026-09-15) - the ChromaDB
        # daily_summary semantic recall for this turn's own query, appended into
        # every step's instructions the same way AIHandler appends it to
        # `constitution` (see _recall_memory's own docstring for the exact
        # parity call this mirrors). "" when memory_manager is None/recall fails/
        # nothing relevant found - never blocks the turn.
        self._turn_memory_context: str = ""

        # Accumulates every real Morning MCP tool call made by any step this
        # turn (2026-09-15) - same {"name","error","arguments","output"} shape
        # AIHandler._finalize_response already extracts (REQ-SEC-002 audit
        # logging parity) - threaded into the returned AIResponse.mcp_calls so
        # the post-turn ledger-recognition hook (denidin.py's shared
        # _run_post_turn_ledger_recognition) sees this turn's real Morning
        # activity under the flag-on path too, not an empty list.
        self._turn_mcp_calls: List[Dict[str, Any]] = []

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
        backbone + exactly ONE capability's prompt + accumulated_context + recalled
        memory + '---' + today (memory deliberately last among the dynamic parts -
        see the inline comment above its append call for why).

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
        # self._turn_memory_context (2026-09-15, position corrected 2026-09-15 -
        # a real gap found on re-audit against contracts/prompt-assembly.md's own
        # formula, which has no memory_context between backbone and capability
        # content at all): MUST be appended AFTER capability content, never
        # between backbone and load_capability_prompt(active_tag) - REQ-063-06
        # requires `backbone_content + load_capability_prompt(tag)` to form one
        # of only 9 distinct byte-stable prefixes system-wide, regardless of
        # turn/conversation. Memory recall varies per query/chat, so placing it
        # before capability content would break every call after it from ever
        # sharing a cached prefix with another call using the same tag - the
        # opposite of what SC-005's "same capability set hits cache" property
        # requires. Placed alongside accumulated_context (also turn-varying) at
        # the very end, right before the date suffix, instead - mirrors
        # AIHandler's own "constitution stays the stable prefix, everything
        # dynamic comes after" principle, just correctly extended to this
        # design's extra capability-content tier.
        if self._turn_memory_context:
            parts.append(self._turn_memory_context)
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
                              accumulated_context: str = "", *,
                              tools: Optional[List[Dict]] = None,
                              return_response: bool = False) -> Any:
        """Issues one Responses API call with Backbone + exactly one active
        capability's prompt+tools + accumulated context (R3's single-active-capability
        property). Returns the response's plain text output by default.

        return_response (2026-09-16, closing a real gap): a write-flow step (e.g.
        invoicing_write/reminders_write's propose_write) needs the raw response
        object itself - to scan for mcp_approval_request/function_call items via
        find_approval_request/extract_any_function_call - not just its
        output_text. Before this, both of those handlers' propose_write
        reimplemented this entire method inline just to get the raw response
        back, which silently dropped _turn_conversation_history and
        BACKBONE_TOOLS from their calls (the actual root cause of a real T10
        sanity-suite bug - see CAPABILITIES_SANITY.md). Pass True here instead
        of forking the call path - every capability step, write flows included,
        now goes through this one method, no exceptions."""
        instructions = self.build_instructions(tag, accumulated_context, request.timestamp)
        # self._turn_conversation_history (2026-09-14): the rolling window computed
        # ONCE in get_response() for this turn, prepended before the current
        # message - same shape/order AIHandler._call_openai_api already uses
        # (oldest-first history, then the current turn), given to every step this
        # turn makes, not just the first.
        input_items = list(self._turn_conversation_history)
        input_items.append({"role": "user", "content": request.user_prompt})
        # BACKBONE_TOOLS (2026-09-14): send_progress_update/react_to_message apply
        # to every capability step uniformly (backbone.md's own cross-cutting
        # sections), so they're attached here regardless of which tag/tools this
        # step's own capability offers - not something each capability handler
        # needs to remember to add itself.
        all_tools = list(tools) if tools else []
        all_tools.extend(BACKBONE_TOOLS)
        kwargs: Dict[str, Any] = {
            "model": request.model,
            "instructions": instructions,
            "input": input_items,
            "max_output_tokens": request.max_tokens,
            "tools": all_tools,
        }

        start = time.monotonic()
        response = self.client.responses.create(**kwargs)
        # 2026-09-15: mcp_call accumulation now happens INSIDE
        # _resolve_backbone_tool_calls, across every round of its own loop (see
        # that method's docstring) - extracting only the FINAL round's
        # response.output here, as this used to, silently dropped an mcp_call
        # made in an earlier round whenever a later round also ran (the exact
        # same bug class as AIHandler._run_local_tool_dispatch_loop's own
        # accumulated_mcp_calls fix earlier this session - see that method's
        # docstring). This step's own mcp_call items (if the very first round,
        # before any backbone-tool call, already made one) are captured here.
        self._turn_mcp_calls.extend(self._extract_mcp_call_items(response))
        response = self._resolve_backbone_tool_calls(request, response, all_tools)
        duration_ms = (time.monotonic() - start) * 1000
        usage = getattr(response, "usage", None)
        cached_tokens = getattr(getattr(usage, "input_tokens_details", None), "cached_tokens", None)
        logger.info(
            "Backbone step=%s instructions_bytes=%d duration_ms=%.0f cached_tokens=%s",
            tag.value, len(instructions.encode("utf-8")), duration_ms, cached_tokens,
        )
        # Feature 080 telemetry (2026-09-15, closing a real gap): this is the
        # single low-level OpenAI call site every capability step routes through
        # (R3's single-active-capability property), so it's the one place that
        # needs instrumenting to cover every LLM call this turn makes - mirrors
        # AIHandler's own per-call-site record_llm_call() calls.
        if self._turn_telemetry_builder is not None:
            self._turn_telemetry_builder.record_llm_call(
                int(duration_ms),
                int(getattr(usage, "input_tokens", 0) or 0),
                int(getattr(usage, "output_tokens", 0) or 0),
            )
        if return_response:
            return response
        return getattr(response, "output_text", "") or ""

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

    def _resolve_backbone_tool_calls(self, request: AIRequest, response, tools: List[Dict]) -> Any:
        """Dispatches every send_progress_update/react_to_message call this step's
        response made (real side effects: an interim WhatsApp send, a reaction),
        submitting each round's outputs via a follow-up call chained through
        `previous_response_id`, LOOPING (capped by MAX_BACKBONE_TOOL_LOOP_ITERATIONS)
        until a round comes back with no more backbone-tool calls - never assuming
        one round is enough.

        2026-09-15 (closing a real gap - a billed test caught it): this used to be
        a single, unlooped follow-up round (see this method's own prior docstring,
        now corrected) - a real turn genuinely needs more than one, e.g. round 1
        calls ONLY react_to_message (the mandatory "ack, I'm doing something" call,
        no MCP call yet, no text - reasoning models emit a function_call OR a
        final message in one turn, never both, same reasoning
        AIHandler._call_openai_reminder_followup_api's own docstring documents),
        and the ONE follow-up round then lets the model make its real MCP call,
        which can ALSO end with no trailing text. Without a loop, that second
        round's response was returned as final with response_text still empty -
        AIResponse.__post_init__'s own should_reply=True-with-no-text guard then
        raised, caught only by get_response's new top-level except (a friendly
        fallback, not a crash, but still the wrong answer for a working turn).
        Same MAX_LOCAL_TOOL_LOOP_ITERATIONS-style bounded loop shape
        AIHandler._run_local_tool_dispatch_loop already uses for the identical
        reason, reimplemented here as new code (REQ-063-07)."""
        current_response = response
        for _loop_round in range(MAX_BACKBONE_TOOL_LOOP_ITERATIONS):
            calls = extract_backbone_tool_calls(current_response)
            if not calls:
                return current_response

            outputs = []
            for call_id, tool_name, args in calls:
                if tool_name == "send_progress_update":
                    payload = dispatch_send_progress_update(
                        self._turn_progress_callback, self._turn_chat_id, args,
                    )
                else:
                    payload = dispatch_react_to_message(
                        self.green_api_bot, self._turn_chat_id,
                        request.message_id or self._turn_message_id, args,
                    )
                outputs.append({"type": "function_call_output", "call_id": call_id, "output": json.dumps(payload)})

            try:
                current_response = self.client.responses.create(
                    model=request.model,
                    input=outputs,
                    previous_response_id=getattr(current_response, "id", None),
                    max_output_tokens=request.max_tokens,
                    tools=tools,
                )
                # Each new round's response can itself carry real mcp_call items
                # (e.g. round 1 = react_to_message ack only, round 2 = the actual
                # Morning MCP call) - accumulate every round, not just the last
                # one this loop happens to return (same fix as call_capability_step's
                # own docstring above describes).
                self._turn_mcp_calls.extend(self._extract_mcp_call_items(current_response))
            except Exception as exc:  # pylint: disable=broad-except
                logger.error("Backbone-tool follow-up call failed (non-fatal): %s", exc)
                return current_response

        logger.warning(
            "Backbone-tool follow-up loop hit MAX_BACKBONE_TOOL_LOOP_ITERATIONS=%d for request %s "
            "without a final text reply - returning the last response as-is.",
            MAX_BACKBONE_TOOL_LOOP_ITERATIONS, request.request_id,
        )
        return current_response

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
        contracts/orchestration-loop.md: the turn enters Intent Identification →
        Planning like any other turn (knowing only "media attached, type X,
        caption Y" — no content), and Planning is what actually CHOOSES whether
        this turn's plan includes a media_analysis step at all; only if/when that
        step runs does `src/capabilities/media_analysis/handler.py::extract()`
        make the real vision/PDF/DOCX extraction call, via `turn_context["media"]`/
        `["media_type"]` below. media_extraction (above) and media/media_type are
        mutually exclusive in practice — a caller passes at most one.
        """
        # 2026-09-15 (closing a real gap): the ENTIRE turn below is now wrapped in
        # one top-level try/except, mirroring AIHandler._get_response_impl's own
        # APITimeoutError/RateLimitError/APIError/Exception -> friendly fallback
        # safety net exactly. Before this fix, only the two meta-steps (Intent
        # Identification/Planning) and each individual plan step self-caught their
        # own errors - anything else that raised (pending-approval resolution,
        # memory recall, session persistence, finalize) propagated straight out of
        # get_response() uncaught, crashing the turn instead of replying at all.
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
            # Long-term memory recall (2026-09-15, closing a real gap - see
            # _recall_memory's own docstring): computed once here, read by
            # build_instructions for every step this turn makes, same
            # once-per-turn/read-by-every-step lifecycle as _turn_conversation_history.
            self._turn_memory_context = self._recall_memory(
                request.user_prompt, effective_chat_id, user_phone, sender_phone,
            )
            turn_context = {
                "role": role,
                "user_phone": user_phone or sender_phone,
                "chat_id": effective_chat_id,
                "sender_phone": sender_phone,
                "media_extraction": media_extraction,
                "media": media,
                "media_type": media_type,
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
            plan = build_plan(self, request, intent_text, allowed_tags, is_media=is_media)

            # Step 3: Execution loop (empty plan => step 4 uses Intent Identification's
            # output alone, per contracts/orchestration-loop.md)
            if plan.is_empty:
                final_text = intent_text
            else:
                final_text = self._execute_plan(plan, request, intent_text, turn_context)

            return self._finalize_response(
                request, final_text, effective_chat_id, role,
                sender, recipient, user_phone, sender_phone, is_group, chat_name,
            )
        except Exception as exc:  # pylint: disable=broad-except
            logger.error(
                "Unexpected error in BackboneOrchestrator.get_response for request %s: %s",
                request.request_id, exc, exc_info=True,
            )
            return self._create_fallback_response(request.request_id, BACKBONE_UNEXPECTED_ERROR)
        finally:
            if self._turn_telemetry_builder is not None and self.telemetry_manager is not None:
                try:
                    record = self._turn_telemetry_builder.finalize(now_local().isoformat())
                    self.telemetry_manager.record(record)
                except Exception as telemetry_error:  # pylint: disable=broad-except
                    logger.warning("Feature 080 telemetry finalize/record failed: %s", telemetry_error)

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
            # 2026-09-15 (closing a real, repeatedly-observed gap - T1's original
            # failure and T10's): despite planning.md's explicit "only include
            # media_analysis when told media is attached" rule and the media_status
            # signal threaded into Planning's own context, the model has
            # demonstrably still planned a media_analysis step for a plain-text
            # turn more than once - prompt guidance alone hasn't been sufficient.
            # This is a deterministic, code-level safety net: never actually run
            # media_analysis when this turn genuinely has no media, regardless of
            # what Planning said - mirrors Planning's own fail_open_plan philosophy
            # of never trusting a single layer to hold on its own.
            if step.capability == CapabilityTag.MEDIA_ANALYSIS and turn_context.get("media") is None:
                logger.warning(
                    "Planning included a media_analysis step for request %s but this "
                    "turn has no media attached - dropping the step rather than "
                    "returning its 'no media' fallback as if it were a real answer.",
                    request.request_id,
                )
                accumulated_context += (
                    "\n\n[media_analysis] step skipped: this turn has no media attached."
                )
                continue
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

    def _finalize_response(self, request: AIRequest, final_text: str,  # pylint: disable=too-many-arguments,too-many-positional-arguments
                            effective_chat_id: Optional[str] = None,
                            role: Optional[Role] = None,
                            sender: Optional[str] = None,
                            recipient: Optional[str] = None,
                            user_phone: Optional[str] = None,
                            sender_phone: Optional[str] = None,
                            is_group: bool = False,
                            chat_name: Optional[str] = None) -> AIResponse:
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
        if effective_chat_id:
            self._persist_turn(
                request, final_text, should_reply, effective_chat_id, role,
                sender, recipient, user_phone, sender_phone, is_group, chat_name,
            )
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
        """2026-09-15 (closing a real gap): mirrors AIHandler._create_fallback_response's
        role exactly - a friendly AIResponse for the case where get_response's own
        try/except below catches something unexpected, so a turn NEVER crashes
        upward with no reply at all. Unlike the legacy fallback strings (English,
        predating this session's Hebrew-only audit), `message` here is always one
        of the Hebrew BACKBONE_* constants in error_messages.py."""
        return AIResponse(
            request_id=request_id,
            response_text=message,
            tokens_used=0,
            prompt_tokens=0,
            completion_tokens=0,
            model="error-fallback",
            finish_reason="error",
            timestamp=int(now_local().timestamp()),
            should_reply=True,
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

    def _persist_turn(self, request: AIRequest, final_text: str, should_reply: bool,  # pylint: disable=too-many-arguments,too-many-positional-arguments,too-many-locals
                       effective_chat_id: str, role: Optional[Role],
                       sender: Optional[str], recipient: Optional[str],
                       user_phone: Optional[str], sender_phone: Optional[str],
                       is_group: bool, chat_name: Optional[str]) -> None:
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
        if self.session_manager is None:
            return
        try:
            own_number_jid = f"{self.own_whatsapp_number}@c.us" if self.own_whatsapp_number else None
            resolved_sender_phone = sender_phone or user_phone or (
                effective_chat_id if not is_group else None
            )
            user_msg_recipient = effective_chat_id if is_group else own_number_jid
            user_msg_recipient_name = (chat_name or effective_chat_id) if is_group else "DeniDin"
            assistant_msg_recipient = effective_chat_id if is_group else resolved_sender_phone
            assistant_msg_recipient_name = (chat_name or effective_chat_id) if is_group else sender

            source_epoch = request.timestamp if (
                request.timestamp is not None and request.timestamp >= _MIN_PLAUSIBLE_SOURCE_EPOCH
            ) else None
            user_source_ts = None if source_epoch is None else local_from_timestamp(source_epoch)
            assistant_source_ts = None if source_epoch is None else local_from_timestamp(source_epoch)
            effective_role = role or Role.CLIENT

            self.session_manager.add_message_with_tokens(
                chat_id=effective_chat_id,
                role="user",
                content=request.user_prompt,
                user_role=effective_role,
                sender=resolved_sender_phone,
                sender_name=sender,
                recipient=user_msg_recipient,
                recipient_name=user_msg_recipient_name,
                message_id=request.message_id,
                timestamp=user_source_ts,
            )
            if should_reply:
                self.session_manager.add_message_with_tokens(
                    chat_id=effective_chat_id,
                    role="assistant",
                    content=final_text,
                    user_role=effective_role,
                    sender=own_number_jid,
                    sender_name="DeniDin",
                    recipient=assistant_msg_recipient,
                    recipient_name=assistant_msg_recipient_name,
                    mcp_calls=list(self._turn_mcp_calls),
                    timestamp=assistant_source_ts,
                )
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Failed to persist turn to session %s: %s", effective_chat_id, exc)

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
