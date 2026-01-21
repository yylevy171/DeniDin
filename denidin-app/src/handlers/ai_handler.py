"""
AIHandler - Handles OpenAI API interactions with retry logic and error handling
Phase 5: US3 - Error Handling & Resilience
Phase 5 (002+007): Memory system integration
Phase 6: RBAC (Role-Based Access Control)
"""
import time
from typing import Optional, List, Dict
from datetime import datetime
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
from src.memory.session_manager import SessionManager
from src.memory.memory_manager import MemoryManager
from src.utils.user_manager import UserManager

logger = get_logger(__name__)

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
        
        # Initialize memory managers if feature enabled
        # Handle configs without feature_flags (backward compatibility)
        self.memory_enabled = getattr(config, 'feature_flags', {}).get('enable_memory_system', False)
        self.session_manager = None
        self.memory_manager = None
        
        # Initialize RBAC if feature enabled
        self.rbac_enabled = getattr(config, 'feature_flags', {}).get('enable_rbac', False)
        self.user_manager = None
        
        if self.rbac_enabled:
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
        else:
            logger.info("RBAC disabled by feature flag")
        
        if self.memory_enabled:
            logger.info("Memory system enabled - initializing SessionManager and MemoryManager")
            
            # Initialize SessionManager
            session_config = config.memory.get('session', {})
            
            # Use provided cleanup_interval or default from config
            if cleanup_interval_seconds is None:
                cleanup_interval_seconds = session_config.get('cleanup_interval_seconds', 3600)
            
            self.session_manager = SessionManager(
                storage_dir=session_config.get('storage_dir', 'data/sessions'),
                session_timeout_hours=session_config.get('session_timeout_hours', 24),
                cleanup_interval_seconds=cleanup_interval_seconds
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
                    embedding_model=longterm_config.get('embedding_model', 'text-embedding-3-small'),
                    ai_client=self.client
                )
                
                # Store collection name and query params for later use
                self.memory_collection_name = longterm_config.get('collection_name', 'godfather_memory')
                self.memory_top_k = longterm_config.get('top_k_results', 5)
                self.memory_min_similarity = longterm_config.get('min_similarity', 0.7)
                
                logger.info(f"MemoryManager initialized with collection: {self.memory_collection_name}")
            else:
                logger.info("Long-term memory disabled in config")
        else:
            logger.info("Memory system disabled by feature flag")
        
        logger.debug(f"AIHandler initialized with model: {config.ai_model}")
    
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
        
        # Build system message with optional memory context
        system_message = self.config.system_message
        
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
                    
                    system_message += memory_context
                    logger.info(f"Added {len(recalled_memories)} recalled memories to system prompt")
            except Exception as e:
                logger.error(f"Failed to recall memories: {e}", exc_info=True)
        
        # Create AI request
        request = AIRequest(
            user_prompt=user_prompt,
            system_message=system_message,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            model=self.config.ai_model,
            chat_id=message.chat_id,
            message_id=message.message_id
        )
        
        logger.debug(f"Created AIRequest {request.request_id} for message {message.message_id}")
        return request
    
    @retry(
        retry=retry_if_exception_type((RateLimitError, APITimeoutError, APIError)),
        stop=stop_after_attempt(2),  # Initial attempt + 1 retry = 2 total
        wait=wait_fixed(1),  # 1 second wait between retries
        reraise=True
    )
    def _call_openai_api(self, request: AIRequest, conversation_history: Optional[List[Dict]] = None):
        """
        Make the actual OpenAI API call with retry logic.
        Retries ONCE (max 2 attempts) on transient failures, waits 1 second.
        
        Args:
            request: AI request to send
            conversation_history: Optional conversation history to include
            
        Returns:
            OpenAI completion response
            
        Raises:
            RateLimitError: After 2 attempts (1 retry)
            APITimeoutError: After 2 attempts (1 retry)
            APIError: After 2 attempts (1 retry)
        """
        logger.debug(f"Calling OpenAI API for request {request.request_id}")
        
        # Build messages array with optional conversation history
        messages = [{"role": "system", "content": request.system_message}]
        
        # Add conversation history if provided
        if conversation_history:
            messages.extend(conversation_history)
            logger.debug(f"Including {len(conversation_history)} messages from conversation history")
        
        # Add current user prompt
        messages.append({"role": "user", "content": request.user_prompt})
        
        completion = self.client.chat.completions.create(
            model=request.model,
            messages=messages,
            max_tokens=request.max_tokens,
            temperature=request.temperature
        )
        
        return completion
    
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
            # Call OpenAI API with retry logic and conversation history
            completion = self._call_openai_api(request, conversation_history=conversation_history)
            
            # Extract response
            response_text = completion.choices[0].message.content
            tokens_used = completion.usage.total_tokens
            
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
            
            # Create response object
            response = AIResponse(
                request_id=request.request_id,
                response_text=response_text,
                tokens_used=tokens_used,
                prompt_tokens=completion.usage.prompt_tokens,
                completion_tokens=completion.usage.completion_tokens,
                model=completion.model,
                finish_reason=completion.choices[0].finish_reason,
                timestamp=int(time.time()),
                is_truncated=False
            )
            
            # Check if response needs truncation for WhatsApp
            if len(response_text) > 4000:
                response = response.truncate_for_whatsapp()
                logger.warning(f"Response truncated to 4000 chars for WhatsApp")
            
            return response
            
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
    
    def transfer_session_to_long_term_memory(self, chat_id: str, session_id: str) -> Dict:
        """
        Transfer an expired session to long-term memory.
        
        Workflow:
        1. Retrieve session and conversation history
        2. Ask AI to summarize the conversation
        3. Store summary in ChromaDB with metadata
        4. NO FILTERING - store ALL sessions regardless of length
        5. Graceful degradation: if AI fails, store raw conversation
        
        Args:
            chat_id: WhatsApp chat ID
            session_id: Session UUID to transfer
            
        Returns:
            Dict with transfer status and details
        """
        if not self.memory_enabled or not self.memory_manager:
            logger.warning(f"Transfer requested but memory system disabled: {session_id}")
            return {"success": False, "reason": "memory_disabled"}
        
        try:
            # Get session and conversation
            session = self.session_manager.get_session(chat_id)
            if not session or session.session_id != session_id:
                logger.error(f"Session not found for transfer: {session_id}")
                return {"success": False, "reason": "session_not_found"}
            
            conversation = self.session_manager.get_conversation_history(chat_id, max_messages=1000)
            if not conversation:
                logger.warning(f"No conversation history for session {session_id}")
                return {"success": False, "reason": "empty_conversation"}
            
            # Try to summarize with AI
            summary_text = None
            used_fallback = False
            
            try:
                # Build summarization prompt
                conv_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in conversation])
                summary_prompt = [
                    {"role": "system", "content": "You are a helpful assistant that summarizes conversations concisely. Focus on key topics, decisions, and action items. Keep summaries under 500 words."},
                    {"role": "user", "content": f"Please summarize this conversation:\n\n{conv_text}"}
                ]
                
                completion = self.client.chat.completions.create(
                    model=self.config.ai_model,
                    messages=summary_prompt,
                    max_tokens=1000,
                    temperature=0.3
                )
                
                summary_text = completion.choices[0].message.content
                logger.info(f"AI summarized session {session_id}: {len(summary_text)} chars")
                
            except Exception as e:
                # Graceful degradation: use raw conversation
                logger.error(f"AI summarization failed for {session_id}: {e}. Using raw conversation fallback.")
                summary_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in conversation])
                used_fallback = True
            
            # Store in ChromaDB
            metadata = {
                "type": "session_summary_fallback" if used_fallback else "session_summary",
                "session_id": session_id,
                "whatsapp_chat": chat_id,
                "session_start": session.created_at,
                "session_end": session.last_active,
                "message_count": len(session.message_ids),
                "summarization_failed": used_fallback
            }
            
            memory_id = self.memory_manager.remember(
                content=summary_text,
                collection_name=f"memory_{chat_id.replace('@c.us', '')}",
                metadata=metadata
            )
            
            logger.info(f"Session {session_id} transferred to long-term memory: {memory_id}")
            
            return {
                "success": True,
                "memory_id": memory_id,
                "used_fallback": used_fallback,
                "summary_length": len(summary_text)
            }
            
        except Exception as e:
            logger.error(f"Failed to transfer session {session_id}: {e}", exc_info=True)
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
                        result = self.transfer_session_to_long_term_memory(
                            chat_id=session.whatsapp_chat,
                            session_id=session.session_id
                        )
                        
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

