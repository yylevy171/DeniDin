"""
AIHandler - Handles OpenAI API interactions with retry logic and error handling
Phase 5: US3 - Error Handling & Resilience
Phase 5 (002+007): Memory system integration
Phase 6: RBAC (Role-Based Access Control)
"""
import time
from datetime import datetime, timezone
from typing import Optional, List, Dict

from openai import OpenAI, APITimeoutError, RateLimitError, APIError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_fixed,
    retry_if_exception_type
)
from src.models.config import AppConfiguration
from src.models.message import WhatsAppMessage, AIRequest, AIResponse
from src.utils.logger import get_logger
from src.managers.session_manager import SessionManager, Session
from src.managers.memory_manager import MemoryManager
from src.managers.user_manager import UserManager
from src.managers.pending_approval_manager import PendingApprovalManager, PendingApproval
from src.models.user import Role
from src.handlers.morning_mcp_locator import MorningMcpLocator

logger = get_logger(__name__)

# Roles authorized to have the Morning MCP invoicing tools attached (Feature 018)
MORNING_MCP_AUTHORIZED_ROLES = (Role.GODFATHER, Role.ADMIN)

# MCP tool names whose execution creates a document in Morning (Feature 022):
# these require explicit human approval before they actually execute.
# `update_invoice_status` is gated as a whole tool even though its "unpaid"
# branch creates nothing - OpenAI's require_approval filters by tool name
# only, not argument value, and "unpaid" is a pure idempotent no-op/error
# with no real reversal mechanism, so gating it too has no real downside.
DOCUMENT_CREATING_MCP_TOOLS = ("create_invoice", "update_invoice_status")

# The remaining Morning MCP tools (reads + add_client) - explicitly listed as
# "never" require approval. Confirmed empirically (2026-07-23, real E2E run)
# that a `require_approval` filter with ONLY an "always" key does NOT leave
# unlisted tools defaulting to no-approval as assumed from docs/smoke-testing
# - `download_invoice_pdf` (not in DOCUMENT_CREATING_MCP_TOOLS) still came
# back as a pending mcp_approval_request. Being fully explicit about both
# sides of the filter avoids relying on that unconfirmed default.
NON_DOCUMENT_CREATING_MCP_TOOLS = (
    "list_invoices", "get_invoice_details", "get_financial_summary",
    "download_invoice_pdf", "add_client",
)

# Free-form affirmative replies recognized as approval of a pending MCP
# document-creation request (Feature 022) - matched against the trimmed,
# casefolded message (or its leading token), not as a substring-anywhere
# check, to avoid false positives on unrelated longer sentences.
_AFFIRMATIVE_REPLIES = {
    "yes", "yep", "yeah", "sure", "ok", "okay", "go ahead",
    "כן", "אישור", "בסדר", "אוקיי", "אוקי",
}


def _is_affirmative_reply(text: str) -> bool:
    """Whether `text` reads as a free-form yes/no approval of a pending
    document-creation request (Feature 022) - matched as the whole trimmed
    message or its leading token, not a substring-anywhere check, to avoid
    false positives on longer unrelated sentences (e.g. one that happens to
    contain "כן" as a substring of another word).
    """
    normalized = text.strip().casefold()
    if not normalized:
        return False
    if normalized in _AFFIRMATIVE_REPLIES:
        return True
    leading_token = normalized.split()[0].strip(".,!?")
    return leading_token in _AFFIRMATIVE_REPLIES

# Maximum message length to prevent excessive API costs
MAX_MESSAGE_LENGTH = 10000

# Models confirmed (real API 400 response) to reject a custom `temperature`
# parameter entirely - not a guess/generalization to the wider 5.6 family,
# only models actually observed to fail this way.
MODELS_WITHOUT_TEMPERATURE_SUPPORT = {"gpt-5.6-luna"}


class AIHandler:
    """
    Handles AI operations including request creation and OpenAI API calls.
    Implements retry logic with exponential backoff for transient failures.
    """

    def __init__(self, ai_client: OpenAI, config: AppConfiguration, cleanup_interval_seconds: Optional[int] = None):
        """
        Initialize AI handler with OpenAI client and configuration.

        Args:
            ai_client: Configured AI client instance (OpenAI)
            config: Application configuration with AI settings
            cleanup_interval_seconds: Optional override for session cleanup interval (for testing)
        """
        self.client = ai_client
        self.config = config
        
        # Constitution loading state (mtime-based caching)
        self._constitution_content: Optional[str] = None
        self._constitution_mtime: Optional[float] = None

        # Memory system and RBAC are always on (2026-07-14 decision: both
        # graduated from feature flags to permanent behavior).
        self.memory_enabled = True
        self.session_manager = None
        self.memory_manager = None

        self.rbac_enabled = True
        self.user_manager = None

        logger.info("RBAC enabled - initializing UserManager")
        godfather_phone = getattr(config, 'godfather_phone', None)
        user_roles = getattr(config, 'user_roles', {})
        admin_phones = user_roles.get('admin_phones', [])
        blocked_phones = user_roles.get('blocked_phones', [])
        logger.debug(
            "UserManager config: godfather_phone_set=%s, admin_phones=%d, blocked_phones=%d",
            bool(godfather_phone),
            len(admin_phones),
            len(blocked_phones)
        )

        self.user_manager = UserManager(
            godfather_phone=godfather_phone,
            admin_phones=admin_phones,
            blocked_phones=blocked_phones
        )
        logger.info(f"UserManager initialized with godfather: {godfather_phone}, admins: {len(admin_phones)}, blocked: {len(blocked_phones)}")

        logger.info("Initializing SessionManager and MemoryManager")

        # Initialize SessionManager
        session_config = config.memory.get('session', {})

        # Note: cleanup_interval_seconds moved to app-level background thread
        # SessionManager no longer runs its own cleanup thread

        self.session_manager = SessionManager(
            storage_dir=session_config.get('storage_dir', 'data/sessions'),
            session_timeout_hours=session_config.get('session_timeout_hours', 24)
        )

        # Store token limits for later use in conversation retrieval
        self.max_tokens_by_role = session_config.get('max_tokens_by_role', {
            'client': 4000,
            'godfather': 100000
        })

        # Initialize MemoryManager
        longterm_config = config.memory.get('longterm', {})
        if longterm_config.get('enabled', True):
            self.memory_manager = MemoryManager(
                storage_dir=longterm_config.get('storage_dir', 'data/memory'),
                embedding_model=config.ai_embedding_model,
                ai_client=self.client
            )

            # Store collection name and query params for later use
            self.memory_collection_name = longterm_config.get('collection_name', 'godfather_memory')
            self.memory_top_k = longterm_config.get('top_k_results', 5)
            self.memory_min_similarity = longterm_config.get('min_similarity', 0.7)

            logger.info(f"MemoryManager initialized with collection: {self.memory_collection_name}")
        else:
            logger.info("Long-term memory disabled in config")

        # Morning MCP integration (Feature 018): locate the current tunnel URL via
        # the shared status file the morning-mcp-app publishes. No cross-app import.
        self.morning_mcp_locator = MorningMcpLocator(getattr(config, 'mcp', {}) or {})

        # Feature 022: tracks, per chat_id, an MCP document-creation call
        # currently held pending the user's explicit approval. In-memory only
        # (see PendingApprovalManager docstring for why).
        self.pending_approval_manager = PendingApprovalManager()

        # Most recent successful AIResponse, for observability/E2E test verification.
        self.last_response: Optional[AIResponse] = None

        logger.debug(
            f"AIHandler initialized with models: text={config.ai_model}, "
            f"vision={config.ai_vision_model}, embedding={config.ai_embedding_model}"
        )

    def _load_constitution(self) -> str:
        """
        Load constitution file with mtime-based caching.
        Reads constitution file only when modified (checks mtime).
        
        Returns:
            Constitution content if file exists and is configured, 
            otherwise fallback to config.system_message
        """
        from pathlib import Path
        
        # Get constitution file from config (support both 'file' and legacy 'files' keys)
        constitution_config = self.config.constitution_config
        filename = constitution_config.get('file')
        
        # Backward compatibility: if 'file' not found, try 'files' array and use first
        if not filename:
            files_array = constitution_config.get('files', [])
            if files_array:
                filename = files_array[0]
        
        # If no constitution file configured, fallback to system_message
        if not filename:
            return ""
        
        # Build constitution file path. Defaults to config/ (same base as
        # CONFIG_PATH='config/config.json' in denidin.py), not data_root -
        # the constitution isn't per-environment data, it's shared config
        # content, identical for dev/prod/test alike. Overridable via
        # constitution_config.base_dir (e.g. tests pointing at a tmp_path).
        base_dir = constitution_config.get('base_dir', 'config')
        filepath = Path(base_dir) / filename
        
        # Check if file exists
        if not filepath.exists():
            logger.warning(f"Constitution file not found: {filepath}, using system_message fallback")
            return ""
        
        # Check file modification time
        try:
            current_mtime = filepath.stat().st_mtime
            
            # Reload if file changed or not yet cached
            if self._constitution_mtime != current_mtime:
                self._constitution_content = filepath.read_text(encoding='utf-8').strip()
                self._constitution_mtime = current_mtime
                logger.debug(f"Constitution loaded: {filename} ({len(self._constitution_content)} chars, mtime: {current_mtime})")
            
            # If constitution is empty after loading, fallback to system_message
            if not self._constitution_content:
                logger.warning(f"Constitution file is empty: {filepath}, using system_message fallback")
                return ""
            
            return self._constitution_content
            
        except Exception as e:
            logger.error(f"Failed to load constitution file {filepath}: {e}", exc_info=True)
            return ""

    def create_request(self, message: WhatsAppMessage, chat_id: Optional[str] = None,
                       user_role: str = 'client', user_phone: Optional[str] = None) -> AIRequest:
        """
        Create an AIRequest from a WhatsApp message.
        Validates and truncates message length if needed.

        Args:
            message: WhatsApp message to convert
            chat_id: Optional chat ID for memory recall (uses message.chat_id if not provided)
            user_role: User role for token limits ('client' or 'godfather') - DEPRECATED when RBAC enabled
            user_phone: User's phone number for RBAC (uses message.sender_id if not provided)

        Returns:
            AIRequest ready for OpenAI API with optional memory context

        Raises:
            PermissionError: If user is blocked (when RBAC enabled)
        """
        # Use provided chat_id or fall back to message.chat_id
        effective_chat_id = chat_id or message.chat_id

        # RBAC: Check if user is blocked
        if self.rbac_enabled and self.user_manager:
            effective_user_phone = user_phone or message.sender_id
            user = self.user_manager.get_user(effective_user_phone)

            if user.is_blocked:
                logger.warning(f"Blocked user attempted to create request: {effective_user_phone}")
                raise PermissionError(f"User is blocked: {effective_user_phone}")

        # Validate and truncate message length
        user_prompt = message.text_content
        if len(user_prompt) > MAX_MESSAGE_LENGTH:
            logger.warning(
                f"Message length {len(user_prompt)} exceeds maximum {MAX_MESSAGE_LENGTH} chars. "
                f"Truncating from sender {message.sender_name}"
            )
            user_prompt = user_prompt[:MAX_MESSAGE_LENGTH]

        # Build system message with constitution (if configured) + optional memory context
        constitution = self._load_constitution()

        # Add recalled memories if memory system enabled
        if self.memory_enabled and self.memory_manager:
            try:
                # Recall relevant long-term memories
                collection_name = f"memory_{effective_chat_id.replace('@c.us', '')}"

                # RBAC: Use RBAC-filtered recall if enabled
                if self.rbac_enabled and self.user_manager:
                    effective_user_phone = user_phone or message.sender_id
                    user = self.user_manager.get_user(effective_user_phone)

                    recalled_memories = self.memory_manager.recall_with_rbac_filter(
                        query=user_prompt,
                        collection_names=[collection_name],
                        user_phone=effective_user_phone,
                        allowed_scopes=user.allowed_memory_scopes,
                        can_see_all_memories=user.can_see_all_memories,
                        top_k=self.memory_top_k,
                        min_similarity=self.memory_min_similarity
                    )
                else:
                    # Existing behavior: regular recall without RBAC
                    recalled_memories = self.memory_manager.recall(
                        query=user_prompt,
                        collection_names=[collection_name],
                        top_k=self.memory_top_k,
                        min_similarity=self.memory_min_similarity
                    )

                if recalled_memories:
                    memory_context = "\n\nRECALLED MEMORIES (from past conversations):\n"
                    for mem in recalled_memories:
                        memory_context += f"- {mem['content']} (relevance: {mem['similarity']:.2f})\n"

                    constitution += memory_context
                    logger.info(f"Added {len(recalled_memories)} recalled memories to system prompt")
            except Exception as e:
                logger.error(f"Failed to recall memories: {e}", exc_info=True)

        # Create AI request
        request = AIRequest(
            user_prompt=user_prompt,
            constitution=constitution,
            max_tokens=self.config.ai_reply_max_tokens,
            temperature=self.config.temperature,
            model=self.config.ai_model,
            chat_id=message.chat_id,
            message_id=message.message_id
        )

        logger.debug(f"Created AIRequest {request.request_id} for message {message.message_id}")
        return request

    def _build_morning_mcp_tools(self, user_obj, correlation_id: str) -> Optional[List[Dict]]:
        """
        Build the Responses API `tools` entry for the Morning MCP server, if this
        user's role is authorized and the server is currently reachable.

        Args:
            user_obj: Resolved User (RBAC), or None if RBAC is disabled
            correlation_id: The AIRequest's request_id, for REQ-SEC-002 audit
                logging (ties this attachment to the request's other log lines).

        Returns:
            A one-item `tools` list registering the Morning MCP server as a remote
            tool, or None if the tools should not be attached (unauthorized role,
            RBAC disabled, or the server is currently unavailable).
        """
        if user_obj is None or user_obj.role not in MORNING_MCP_AUTHORIZED_ROLES:
            return None

        server_url = self.morning_mcp_locator.current_server_url()
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
            f"Attaching Morning MCP tools for request={correlation_id}, role={user_obj.role}, "
            f"url_host={server_url.split('/')[2] if '//' in server_url else server_url}, "
            f"token={masked_token}"
        )

        return [{
            "type": "mcp",
            "server_label": mcp_config.get('morning_server_label', 'morning-invoices'),
            "server_url": server_url,
            # Feature 022: any tool that creates a Morning document requires
            # explicit human approval before it executes; everything else
            # (reads, add_client) proceeds immediately as before. Both sides
            # of the filter are listed explicitly - see
            # NON_DOCUMENT_CREATING_MCP_TOOLS's comment for why.
            "require_approval": {
                "always": {"tool_names": list(DOCUMENT_CREATING_MCP_TOOLS)},
                "never": {"tool_names": list(NON_DOCUMENT_CREATING_MCP_TOOLS)},
            },
            "headers": {"Authorization": f"Bearer {auth_token}"}
        }]

    def _build_instructions(self, request: AIRequest) -> str:
        """
        Build the `instructions` string (constitution + current-date suffix)
        for a Responses API call. Used by both a normal turn's call and the
        Feature 022 approval-resolution follow-up call — `previous_response_id`
        chains the prior conversation's input/output, but NOT the `instructions`
        parameter itself (confirmed empirically, same as `tools` needing to be
        re-passed - see `_call_openai_approval_api`), so every call needs its
        own full instructions to keep following the constitution's guidance.
        """
        # Give the model the actual current date. It has no clock of its own —
        # its training cutoff makes it default to a stale "current year", which
        # produced real wrong-year invoice lookups (e.g. resolving "7 בפברואר"
        # to 2023). This is appended at reply time, computed per call in UTC
        # (CONSTITUTION §II) — NOT templated into the constitution file.
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return (
            f"{request.constitution}\n\n---\n"
            f"THE CURRENT DATE IS {today} (UTC). Treat this as the authoritative "
            f"\"today\" when resolving any relative or partial date the user gives "
            f"(a day/month with no year, \"היום\", \"אתמול\", etc.) — never fall "
            f"back on a year from your training data."
        )

    @retry(
        retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIError)),
        stop=stop_after_attempt(2),  # Initial attempt + 1 retry = 2 total
        wait=wait_fixed(1),  # 1 second wait between retries
        reraise=True
    )
    def _call_openai_api(self, request: AIRequest, conversation_history: Optional[List[Dict]] = None,
                         tools: Optional[List[Dict]] = None):
        """
        Make the actual OpenAI Responses API call with retry logic.
        Retries ONCE (max 2 attempts) on transient failures, waits 1 second.

        Args:
            request: AI request to send
            conversation_history: Optional conversation history to include
            tools: Optional Responses API `tools` list (e.g. Morning MCP server)

        Returns:
            OpenAI Responses API response

        Raises:
            RateLimitError: After 2 attempts (1 retry)
            APITimeoutError: After 2 attempts (1 retry)
            APIError: After 2 attempts (1 retry)
        """
        logger.debug(f"Calling OpenAI Responses API for request {request.request_id}")

        # Build input array with optional conversation history (same shape as
        # conversation_history: list of {"role": ..., "content": ...})
        input_items = []
        if conversation_history:
            input_items.extend(conversation_history)
            logger.debug(f"Including {len(conversation_history)} messages from conversation history")
        input_items.append({"role": "user", "content": request.user_prompt})

        kwargs = {
            "model": request.model,
            "instructions": self._build_instructions(request),
            "input": input_items,
            "max_output_tokens": request.max_tokens,
        }
        if request.model not in MODELS_WITHOUT_TEMPERATURE_SUPPORT:
            kwargs["temperature"] = request.temperature
        if tools:
            kwargs["tools"] = tools

        response = self.client.responses.create(**kwargs)

        return response

    def get_response(self, request: AIRequest, chat_id: Optional[str] = None,
                     user_role: str = 'client', sender: Optional[str] = None,
                     recipient: Optional[str] = None, user_phone: Optional[str] = None) -> AIResponse:
        """
        Get AI response for a request with error handling and fallbacks.
        Includes memory system integration for session storage.

        Args:
            request: AI request to process
            chat_id: Optional chat ID for session management (uses request.chat_id if not provided)
            user_role: User role for token limits ('client' or 'godfather') - DEPRECATED when RBAC enabled
            sender: WhatsApp sender ID for message storage
            recipient: WhatsApp recipient ID for message storage
            user_phone: User's phone number for RBAC (uses sender if not provided)

        Returns:
            AIResponse with generated text or fallback message

        Raises:
            PermissionError: If user is blocked (when RBAC enabled)
        """
        # Use provided chat_id or fall back to request.chat_id
        effective_chat_id = chat_id or request.chat_id

        # RBAC: Check if user is blocked
        user_obj = None
        if self.rbac_enabled and self.user_manager:
            effective_user_phone = user_phone or sender
            if effective_user_phone:
                user_obj = self.user_manager.get_user(effective_user_phone)

                if user_obj.is_blocked:
                    logger.warning(f"Blocked user attempted to get response: {effective_user_phone}")
                    raise PermissionError(f"User is blocked: {effective_user_phone}")

        # Feature 022: if a document-creation MCP call is pending approval for
        # this chat, this turn resolves it (approve/decline) instead of being
        # processed as a normal new request. Returns None only for the decline
        # case, meaning: fall through and process this message as a fresh turn.
        logger.info(
            f"[022] get_response: effective_chat_id={effective_chat_id!r}, "
            f"user_obj={'present' if user_obj else None}, "
            f"user_prompt={request.user_prompt!r}"
        )
        pending = self.pending_approval_manager.get(effective_chat_id) if user_obj else None
        logger.info(f"[022] pending_approval_manager.get({effective_chat_id!r}) -> {pending!r}")
        if pending is not None:
            logger.info(
                f"[022] Pending approval FOUND for chat={effective_chat_id!r} - "
                f"routing to _resolve_pending_approval instead of a normal turn"
            )
            resolved = self._resolve_pending_approval(
                pending, request, effective_chat_id, user_obj, user_role, sender, recipient
            )
            logger.info(
                f"[022] _resolve_pending_approval returned "
                f"{'an AIResponse (approved)' if resolved is not None else 'None (declined - falling through to a normal turn)'}"
            )
            if resolved is not None:
                return resolved
        else:
            logger.info(f"[022] No pending approval for chat={effective_chat_id!r} - normal turn processing")

        # Retrieve conversation history if memory enabled
        conversation_history = None
        if self.memory_enabled and self.session_manager and effective_chat_id:
            try:
                # RBAC: Use user's token limit if enabled
                if self.rbac_enabled and user_obj:
                    max_tokens = user_obj.token_limit
                else:
                    # Existing behavior: use role-based token limits
                    max_tokens = self.max_tokens_by_role.get(user_role, 4000)

                conversation_history = self.session_manager.get_conversation_history(
                    whatsapp_chat=effective_chat_id,
                    max_tokens=max_tokens
                )
                if conversation_history:
                    logger.info(f"Retrieved {len(conversation_history)} messages from session history")
            except Exception as e:
                logger.error(f"Failed to retrieve conversation history: {e}", exc_info=True)

        try:
            # Morning MCP tools (Feature 018): attach only for authorized roles when
            # the server is currently reachable; None for clients/blocked or when down.
            tools = self._build_morning_mcp_tools(user_obj, request.request_id) if self.rbac_enabled else None

            # Call OpenAI Responses API with retry logic, conversation history, and
            # (optionally) the Morning MCP server as a remote tool
            response = self._call_openai_api(request, conversation_history=conversation_history, tools=tools)

            return self._finalize_response(
                request, response, effective_chat_id, user_obj, user_role, sender, recipient, tools
            )

        except APITimeoutError as e:
            logger.error(
                f"OpenAI API timeout for request {request.request_id} after retries: {e}",
                exc_info=True
            )
            return self._create_fallback_response(
                request.request_id,
                "Sorry, I'm having trouble connecting to my AI service. Please try again later."
            )

        except RateLimitError as e:
            logger.error(
                f"OpenAI rate limit exceeded for request {request.request_id} after retries: {e}",
                exc_info=True
            )
            return self._create_fallback_response(
                request.request_id,
                "I'm currently at capacity. Please try again in a minute."
            )

        except APIError as e:
            logger.error(
                f"OpenAI API error for request {request.request_id} after retries: {e}",
                exc_info=True
            )
            return self._create_fallback_response(
                request.request_id,
                "Sorry, I encountered an error processing your request. Please try again."
            )

        except Exception as e:
            logger.error(
                f"Unexpected error in get_response for request {request.request_id}: {e}",
                exc_info=True
            )
            return self._create_fallback_response(
                request.request_id,
                "Sorry, I encountered an unexpected error. Please try again."
            )

    def _finalize_response(self, request: AIRequest, response, effective_chat_id: Optional[str],
                           user_obj, user_role: str, sender: Optional[str],
                           recipient: Optional[str], tools: Optional[List[Dict]]) -> AIResponse:
        """
        Shared post-API-call logic: extract mcp_calls, detect a new pending
        approval (Feature 022), store messages in session, build the final
        AIResponse. Used by both the normal turn path and the pending-approval
        resolution path in `get_response`/`_resolve_pending_approval`.
        """
        # Extract response
        response_text = response.output_text
        tokens_used = response.usage.total_tokens

        logger.info(
            f"[022] _finalize_response: response.id={getattr(response, 'id', None)!r}, "
            f"effective_chat_id={effective_chat_id!r}, "
            f"output item types={[getattr(i, 'type', None) for i in (response.output or [])]!r}, "
            f"output_text={response_text!r}"
        )

        # Extract Morning MCP tool calls, if any (REQ-SEC-002 audit logging;
        # also lets E2E tests verify tool usage without a second AI call).
        # Includes arguments/output for diagnosability (e.g. confirming
        # which invoice_id the model actually passed to a follow-up tool
        # call) - never logged/returned with secrets, just tool I/O.
        mcp_calls = [
            {
                "name": item.name,
                "error": item.error,
                "arguments": item.arguments,
                "output": item.output
            }
            for item in (response.output or [])
            if getattr(item, "type", None) == "mcp_call"
        ]
        if mcp_calls:
            logger.info(f"MCP calls for request {request.request_id}: {mcp_calls}")
        elif tools and any(
            phrase in response_text
            for phrase in ("הוצאה בהצלחה", "סומנה כשולמה", "בוטלה בהצלחה", "נוסף בהצלחה")
        ):
            # Invoicing tools were offered this turn and the reply reads like
            # a state-changing confirmation, but no mcp_call was made - the
            # model may have pattern-completed a fabricated success from
            # earlier turns instead of actually calling the tool. Log only;
            # this is a detection safety net, not a behavior change.
            logger.warning(
                f"Possible hallucinated invoicing confirmation for request "
                f"{request.request_id}: reply text suggests a state-changing "
                f"action succeeded, but no MCP tool was called. "
                f"Reply: {response_text!r}"
            )

        # Feature 022: a document-creation tool call may come back as an
        # mcp_approval_request instead of an mcp_call - nothing executed on
        # the Morning side yet. Track it so the next turn can resolve it.
        approval_requests = [
            item for item in (response.output or [])
            if getattr(item, "type", None) == "mcp_approval_request"
        ]
        logger.info(
            f"[022] approval_requests found in response.output: {len(approval_requests)} "
            f"(effective_chat_id={effective_chat_id!r})"
        )
        if approval_requests and effective_chat_id:
            ar = approval_requests[0]
            new_pending = PendingApproval(
                response_id=response.id,
                approval_request_id=ar.id,
                tool_name=ar.name,
                arguments=ar.arguments,
                server_label=ar.server_label,
                created_at=datetime.now(timezone.utc).isoformat(),
            )
            self.pending_approval_manager.set(effective_chat_id, new_pending)
            logger.info(
                f"[022] pending_approval_manager.set({effective_chat_id!r}, {new_pending!r}) - "
                f"store id now: {id(self.pending_approval_manager)}"
            )
            logger.info(
                f"Pending MCP approval created for chat={effective_chat_id}, "
                f"tool={ar.name}, request={request.request_id}"
            )
            if not response_text.strip():
                # Observed live (smoke test, 2026-07-23): a turn that produces
                # an mcp_approval_request can come back with NO message output
                # item at all (response.output_text == "") - the constitution
                # tells the model to narrate before asking, but that's prompt
                # guidance, not a guarantee. Without this fallback, the user
                # would get a silent/empty WhatsApp reply while the action
                # sits pending - never leave them with no signal at all.
                response_text = (
                    "יש פעולה הממתינה לאישורך לפני שהיא מתבצעת. "
                    "השב/י \"כן\" כדי לאשר, או כל תשובה אחרת כדי לבטל."
                )
                logger.warning(
                    f"Model produced no narrating text alongside a pending "
                    f"approval for request {request.request_id} - using "
                    f"fallback confirmation prompt."
                )
        elif approval_requests and not effective_chat_id:
            logger.warning(
                f"[022] mcp_approval_request found but effective_chat_id is falsy "
                f"({effective_chat_id!r}) - pending approval NOT stored, this request will be lost!"
            )

        logger.info(
            f"AI response generated for request {request.request_id}: "
            f"{tokens_used} tokens, {len(response_text)} chars"
        )
        logger.debug(f"Full response: {response_text[:200]}...")

        # Store messages in session if memory enabled
        if self.memory_enabled and self.session_manager and effective_chat_id:
            try:
                # RBAC: Use token limit enforcement if enabled
                if self.rbac_enabled and user_obj:
                    # Store user message with token limit
                    self.session_manager.add_message_with_token_limit(
                        chat_id=effective_chat_id,
                        role="user",
                        content=request.user_prompt,
                        user_role=user_obj.role,
                        token_limit=user_obj.token_limit,
                        sender=sender or effective_chat_id,
                        recipient=recipient or "AI"
                    )

                    # Store AI response with token limit
                    self.session_manager.add_message_with_token_limit(
                        chat_id=effective_chat_id,
                        role="assistant",
                        content=response_text,
                        user_role=user_obj.role,
                        token_limit=user_obj.token_limit,
                        sender=recipient or "AI",
                        recipient=sender or effective_chat_id
                    )
                else:
                    # Existing behavior: regular add_message without token limits
                    # Store user message
                    # sender should be WhatsApp ID (or test identifier), recipient is always 'AI' (or 'AI_test')
                    self.session_manager.add_message(
                        chat_id=effective_chat_id,
                        role="user",
                        content=request.user_prompt,
                        user_role=user_role or "client",
                        sender=sender or effective_chat_id,
                        recipient=recipient or "AI"
                    )

                    # Store AI response
                    # sender is always 'AI' (or 'AI_test'), recipient is WhatsApp ID (or test identifier)
                    self.session_manager.add_message(
                        chat_id=effective_chat_id,
                        role="assistant",
                        content=response_text,
                        user_role=user_role or "client",
                        sender=recipient or "AI",  # AI is the sender
                        recipient=sender or effective_chat_id  # Reply goes to original sender
                    )

                logger.debug(f"Stored user + assistant messages in session {effective_chat_id}")
            except Exception as e:
                logger.error(f"Failed to store messages in session: {e}", exc_info=True)

        # Create response object.
        # Responses API has no per-choice finish_reason; derive from
        # incomplete_details when present, else "stop".
        finish_reason = "stop"
        if getattr(response, "incomplete_details", None) is not None:
            finish_reason = response.incomplete_details.reason or "incomplete"

        ai_response = AIResponse(
            request_id=request.request_id,
            response_text=response_text,
            tokens_used=tokens_used,
            prompt_tokens=response.usage.input_tokens,
            completion_tokens=response.usage.output_tokens,
            model=response.model,
            finish_reason=finish_reason,
            timestamp=int(time.time()),
            is_truncated=False,
            mcp_calls=mcp_calls
        )

        # Check if response needs truncation for WhatsApp
        if len(response_text) > 4000:
            ai_response = ai_response.truncate_for_whatsapp()
            logger.warning("Response truncated to 4000 chars for WhatsApp")

        # Retain the most recent response for observability (audit logging,
        # E2E test verification of mcp_calls) - purely additive, read-only
        # for callers; does not change get_response's behavior or return value.
        self.last_response = ai_response

        return ai_response

    @retry(
        retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIError)),
        stop=stop_after_attempt(2),
        wait=wait_fixed(1),
        reraise=True
    )
    def _call_openai_approval_api(self, request: AIRequest, pending: PendingApproval,
                                  approve: bool, tools: Optional[List[Dict]] = None):
        """
        Resolve a pending MCP approval request (Feature 022) via a follow-up
        Responses API call chained to the original call via `previous_response_id`,
        so OpenAI resolves the approval against its own server-side state
        rather than requiring the full prior input/output to be replayed.
        """
        approval_item = {
            "type": "mcp_approval_response",
            "approval_request_id": pending.approval_request_id,
            "approve": approve,
        }
        kwargs = {
            "model": request.model,
            "instructions": self._build_instructions(request),
            "input": [approval_item],
            "previous_response_id": pending.response_id,
            "max_output_tokens": request.max_tokens,
        }
        if request.model not in MODELS_WITHOUT_TEMPERATURE_SUPPORT:
            kwargs["temperature"] = request.temperature
        if tools:
            kwargs["tools"] = tools

        logger.info(f"[022] _call_openai_approval_api: approve={approve}, kwargs={kwargs!r}")
        response = self.client.responses.create(**kwargs)
        logger.info(
            f"[022] _call_openai_approval_api response: id={getattr(response, 'id', None)!r}, "
            f"output item types={[getattr(i, 'type', None) for i in (response.output or [])]!r}, "
            f"output_text={response.output_text!r}"
        )
        return response

    def _resolve_pending_approval(self, pending: PendingApproval, request: AIRequest,
                                  effective_chat_id: str, user_obj, user_role: str,
                                  sender: Optional[str], recipient: Optional[str]) -> Optional[AIResponse]:
        """
        Resolve a pending document-creation MCP approval (Feature 022) using
        this turn's message as the yes/no reply.

        Returns:
            The final AIResponse if the user approved (the gated tool actually
            executes now). None if declined or unrecognized - the caller
            should then process this same message as a normal fresh turn
            (the decline itself is still explicitly reported to OpenAI so its
            server-side state for that response is closed out cleanly).
        """
        tools = self._build_morning_mcp_tools(user_obj, request.request_id) if self.rbac_enabled else None
        is_affirmative = _is_affirmative_reply(request.user_prompt)
        logger.info(
            f"[022] _resolve_pending_approval: chat={effective_chat_id!r}, "
            f"pending={pending!r}, user_prompt={request.user_prompt!r}, "
            f"is_affirmative={is_affirmative}, tools_attached={bool(tools)}"
        )

        if is_affirmative:
            response = self._call_openai_approval_api(request, pending, approve=True, tools=tools)
            self.pending_approval_manager.clear(effective_chat_id)
            logger.info(f"[022] Approved and cleared pending for chat={effective_chat_id!r}")
            return self._finalize_response(
                request, response, effective_chat_id, user_obj, user_role, sender, recipient, tools
            )

        # Not a recognized affirmative: decline, close out OpenAI's
        # server-side state, then let the caller process this message as a
        # normal fresh turn (it may itself be a new, unrelated request).
        logger.info(
            f"[022] '{request.user_prompt}' not recognized as affirmative - "
            f"declining pending approval for chat={effective_chat_id!r}"
        )
        try:
            self._call_openai_approval_api(request, pending, approve=False, tools=tools)
        except Exception as e:
            logger.error(
                f"Failed to submit decline for pending approval (chat={effective_chat_id}, "
                f"tool={pending.tool_name}): {e}", exc_info=True
            )
        self.pending_approval_manager.clear(effective_chat_id)
        logger.info(
            f"Pending MCP approval declined for chat={effective_chat_id}, "
            f"tool={pending.tool_name} - falling through to a fresh turn"
        )
        return None

    def _create_fallback_response(self, request_id: str, message: str) -> AIResponse:
        """
        Create a fallback AIResponse for error cases.

        Args:
            request_id: Original request ID
            message: Fallback message to send

        Returns:
            AIResponse with fallback content
        """
        return AIResponse(
            request_id=request_id,
            response_text=message,
            tokens_used=0,
            prompt_tokens=0,
            completion_tokens=0,
            model="error-fallback",
            finish_reason="error",
            timestamp=int(time.time()),
            is_truncated=False
        )

    # Memory System Integration Methods (Feature 002+007)

    def transfer_session_to_long_term_memory(self, session: Session) -> Dict:
        """
        Transfer an expired session to long-term memory.

        Workflow:
        1. Retrieve conversation history from session
        2. Ask AI to summarize the conversation
        3. Store summary in ChromaDB with metadata
        4. NO FILTERING - store ALL sessions regardless of length
        5. Graceful degradation: if AI fails, store raw conversation

        Args:
            session: Session object to transfer

        Returns:
            Dict with transfer status and details
        """
        if not self.memory_enabled or not self.memory_manager:
            logger.warning(f"Transfer requested but memory system disabled: {session.session_id}")
            return {"success": False, "reason": "memory_disabled"}

        try:
            # Get conversation history directly from session object
            conversation = self.session_manager.get_conversation_history_for_session(session)
            if not conversation:
                logger.warning(f"No conversation history for session {session.session_id}")
                return {"success": False, "reason": "empty_conversation"}

            # Try to summarize with AI
            summary_text = None
            used_fallback = False

            try:
                # Build summarization prompt
                conv_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in conversation])
                summarizer_instructions = (
                    "You are a conversation summarizer that extracts both explicit and implicit "
                    "information. Start your summary by listing key facts as bullet points (e.g., "
                    "names, preferences, decisions, entities mentioned). Then provide context, "
                    "relationships, and logical deductions. Make information easily retrievable "
                    "for future questions. Keep summaries under 500 words."
                )

                summary_response = self.client.responses.create(
                    model=self.config.ai_model,
                    instructions=summarizer_instructions,
                    input=f"Summarize this conversation, leading with facts then inferences:\n\n{conv_text}",
                    max_output_tokens=1000,
                    temperature=0.3
                )

                summary_text = summary_response.output_text
                logger.info(f"AI summarized session {session.session_id}: {len(summary_text)} chars")

            except Exception as e:
                # Graceful degradation: use raw conversation
                logger.error(f"AI summarization failed for {session.session_id}: {e}. Using raw conversation fallback.")
                summary_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in conversation])
                used_fallback = True

            # Store in ChromaDB
            collection_name = f"memory_{session.whatsapp_chat.replace('@c.us', '')}"
            logger.info(f"Starting ChromaDB storage for session {session.session_id} in collection {collection_name}")

            # Use whatsapp_chat directly as user_phone for RBAC filtering (includes @c.us)
            user_phone = session.whatsapp_chat

            metadata = {
                "type": "session_summary_fallback" if used_fallback else "session_summary",
                "session_id": session.session_id,
                "whatsapp_chat": session.whatsapp_chat,
                "user_phone": user_phone,  # Required for RBAC filtering (must match sender_id format)
                "session_start": session.created_at,
                "session_end": session.last_active,
                "message_count": len(session.message_ids),
                "summarization_failed": used_fallback
            }

            memory_id = self.memory_manager.remember(
                content=summary_text,
                collection_name=collection_name,
                metadata=metadata
            )

            logger.info(f"ChromaDB storage completed for session {session.session_id}: memory_id={memory_id}")

            # Verify storage
            collection = self.memory_manager.client.get_collection(name=collection_name)
            count = collection.count()
            logger.info(f"ChromaDB collection '{collection_name}' now has {count} item(s)")

            logger.info(f"Session {session.session_id} transferred to long-term memory: {memory_id}")

            return {
                "success": True,
                "memory_id": memory_id,
                "used_fallback": used_fallback,
                "summary_length": len(summary_text)
            }

        except Exception as e:
            logger.error(f"Failed to transfer session {session.session_id}: {e}", exc_info=True)
            return {"success": False, "reason": "transfer_error", "error": str(e)}

    def recover_orphaned_sessions(self) -> Dict:
        """
        STARTUP PROCEDURE: Recover sessions not transferred due to crashes/shutdowns.

        Scans for active sessions, checks expiration status:
        - Expired (>24h inactive) → transfer to long-term memory
        - Active (<24h inactive) → load to short-term memory

        Returns:
            Dict with recovery summary
        """
        if not self.memory_enabled or not self.session_manager:
            logger.info("Session recovery skipped: memory system disabled")
            return {"total_found": 0, "transferred_to_long_term": 0, "loaded_to_short_term": 0}

        try:
            orphaned_sessions = self.session_manager.find_orphaned_sessions()

            if not orphaned_sessions:
                logger.info("No orphaned sessions found - clean startup")
                return {"total_found": 0, "transferred_to_long_term": 0, "loaded_to_short_term": 0}

            logger.info(f"Found {len(orphaned_sessions)} orphaned sessions - starting recovery")

            long_term_sessions = []
            short_term_sessions = []
            failed_sessions = []

            for session in orphaned_sessions:
                try:
                    is_expired = self.session_manager.is_session_expired(session)

                    if is_expired:
                        # Transfer to long-term memory
                        result = self.transfer_session_to_long_term_memory(session)

                        if result.get("success"):
                            long_term_sessions.append(session.session_id)
                            logger.info(f"Recovered expired session to long-term: {session.session_id}")
                        else:
                            failed_sessions.append(session.session_id)
                            logger.error(f"Failed to transfer expired session: {session.session_id}")
                    else:
                        # Load to short-term memory (still active)
                        short_term_sessions.append(session.session_id)
                        logger.info(f"Recovered active session to short-term: {session.session_id}")

                except Exception as e:
                    logger.error(f"Error recovering session {session.session_id}: {e}", exc_info=True)
                    failed_sessions.append(session.session_id)

            logger.info(
                f"Session recovery complete: {len(long_term_sessions)} transferred, "
                f"{len(short_term_sessions)} loaded, {len(failed_sessions)} failed"
            )

            return {
                "total_found": len(orphaned_sessions),
                "transferred_to_long_term": len(long_term_sessions),
                "loaded_to_short_term": len(short_term_sessions),
                "failed": len(failed_sessions),
                "long_term_sessions": long_term_sessions,
                "short_term_sessions": short_term_sessions,
                "failed_sessions": failed_sessions
            }

        except Exception as e:
            logger.error(f"Session recovery failed: {e}", exc_info=True)
            return {"total_found": 0, "transferred_to_long_term": 0, "loaded_to_short_term": 0, "error": str(e)}
