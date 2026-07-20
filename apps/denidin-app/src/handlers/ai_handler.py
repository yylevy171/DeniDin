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
from src.models.user import Role
from src.handlers.morning_mcp_locator import MorningMcpLocator

logger = get_logger(__name__)

# Roles authorized to have the Morning MCP invoicing tools attached (Feature 018)
MORNING_MCP_AUTHORIZED_ROLES = (Role.GODFATHER, Role.ADMIN)

# Maximum message length to prevent excessive API costs
MAX_MESSAGE_LENGTH = 10000


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
        
        # Build constitution file path
        filepath = Path(self.config.data_root) / 'constitution' / filename
        
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

    def _build_morning_mcp_tools(self, user_obj) -> Optional[List[Dict]]:
        """
        Build the Responses API `tools` entry for the Morning MCP server, if this
        user's role is authorized and the server is currently reachable.

        Args:
            user_obj: Resolved User (RBAC), or None if RBAC is disabled

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
            f"Attaching Morning MCP tools for role={user_obj.role}, "
            f"url_host={server_url.split('/')[2] if '//' in server_url else server_url}, "
            f"token={masked_token}"
        )

        return [{
            "type": "mcp",
            "server_label": mcp_config.get('morning_server_label', 'morning-invoices'),
            "server_url": server_url,
            "require_approval": "never",
            "headers": {"Authorization": f"Bearer {auth_token}"}
        }]

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

        # Give the model the actual current date. It has no clock of its own —
        # its training cutoff makes it default to a stale "current year", which
        # produced real wrong-year invoice lookups (e.g. resolving "7 בפברואר"
        # to 2023). This is appended at reply time, computed per call in UTC
        # (CONSTITUTION §II) — NOT templated into the constitution file.
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        instructions = (
            f"{request.constitution}\n\n---\n"
            f"THE CURRENT DATE IS {today} (UTC). Treat this as the authoritative "
            f"\"today\" when resolving any relative or partial date the user gives "
            f"(a day/month with no year, \"היום\", \"אתמול\", etc.) — never fall "
            f"back on a year from your training data."
        )

        kwargs = {
            "model": request.model,
            "instructions": instructions,
            "input": input_items,
            "max_output_tokens": request.max_tokens,
            "temperature": request.temperature
        }
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
            tools = self._build_morning_mcp_tools(user_obj) if self.rbac_enabled else None

            # Call OpenAI Responses API with retry logic, conversation history, and
            # (optionally) the Morning MCP server as a remote tool
            response = self._call_openai_api(request, conversation_history=conversation_history, tools=tools)

            # Extract response
            response_text = response.output_text
            tokens_used = response.usage.total_tokens

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
