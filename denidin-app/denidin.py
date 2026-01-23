#!/usr/bin/env python3
"""
DeniDin WhatsApp AI Application - Main Entry Point
Integrates Green API for WhatsApp messaging with OpenAI ChatGPT.
Phase 6: US4 - Configuration & Deployment
"""
import os
import sys
import signal
from whatsapp_chatbot_python import GreenAPIBot, Notification
from openai import OpenAI
from src.models.config import AppConfiguration
from src.utils.logger import get_logger
from src.handlers.ai_handler import AIHandler
from src.handlers.whatsapp_handler import WhatsAppHandler
from src.memory.session_manager import SessionManager
from src.memory.memory_manager import MemoryManager
from src.background_threads import SessionCleanupThread, run_startup_cleanup

# Configuration
CONFIG_PATH = 'config/config.json'

# Load and validate configuration
try:
    config = AppConfiguration.from_file(CONFIG_PATH)
    config.validate()
except ValueError as e:
    # Configuration validation failed - exit with clear error message
    print(f"ERROR: Invalid configuration in {CONFIG_PATH}", file=sys.stderr)
    print(f"Validation error: {e}", file=sys.stderr)
    print("Please fix the configuration file and restart the application.", file=sys.stderr)
    sys.exit(2)  # Exit code 2 = configuration error (CONSTITUTION XVI)
except FileNotFoundError:
    print(f"ERROR: Configuration file not found: {CONFIG_PATH}", file=sys.stderr)
    print("Please create config/config.json from config/config.example.json", file=sys.stderr)
    sys.exit(2)  # Exit code 2 = configuration error (CONSTITUTION XVI)
except Exception as e:
    print(f"ERROR: Failed to load configuration: {e}", file=sys.stderr)
    sys.exit(2)  # Exit code 2 = configuration error (CONSTITUTION XVI)

# Setup logging
logger = get_logger(__name__, log_level=config.log_level)


def mask_api_key(key: str) -> str:
    """
    Mask API key for secure logging.
    Shows first 4 and last 4 characters (CONSTITUTION IX).

    Args:
        key: API key to mask

    Returns:
        Masked API key string (e.g., "sk-p...z123")
    """
    if len(key) <= 8:
        return "***"  # Too short to safely show any part
    return f"{key[:4]}...{key[-4:]}"


# Initialize Green API client
bot = GreenAPIBot(
    config.green_api_instance_id,
    config.green_api_token
)

# Initialize OpenAI client
ai_client = OpenAI(
    api_key=config.ai_api_key,
    timeout=30.0
)

# Global DeniDin instance for WhatsApp message handler
# Will be populated in __main__ block after initialize_app()
denidin_app = None


class DeniDin:
    """
    DeniDin application instance.
    Provides programmatic API for testing and direct access.
    Used by integration tests to interact with the app without WhatsApp layer.
    Also serves as global context for background threads (e.g., session cleanup).
    """
    def __init__(self, ai_handler, config, whatsapp_handler, cleanup_thread=None):
        self.ai_handler = ai_handler
        self.config = config
        self.whatsapp_handler = whatsapp_handler
        self.cleanup_thread = cleanup_thread
        # Add references for background thread access
        self.session_manager = ai_handler.session_manager if ai_handler.memory_enabled else None
        self.memory_manager = ai_handler.memory_manager if ai_handler.memory_enabled else None
        self._logger = get_logger(__name__)
    
    def handle_message(self, chat_id: str, content: str) -> dict:
        """
        Send a message to the AI and get response.
        
        Args:
            chat_id: WhatsApp chat ID (e.g., "972522968679@c.us")
            content: Message text content
            
        Returns:
            dict with keys: response_text, tokens_used, session_id
        """
        from datetime import datetime, timezone
        from src.models.message import WhatsAppMessage
        
        # Create fake WhatsApp message for testing
        timestamp = int(datetime.now(timezone.utc).timestamp())
        message = WhatsAppMessage(
            message_id=f"test_{timestamp}",
            chat_id=chat_id,
            sender_id=chat_id,
            sender_name="Test User",
            text_content=content,
            timestamp=timestamp,
            message_type="textMessage",
            is_group=False,
            received_timestamp=datetime.now(timezone.utc)
        )
        
        # Create AI request
        ai_request = self.ai_handler.create_request(message)
        
        # Get AI response
        ai_response = self.ai_handler.get_response(
            ai_request,
            sender=chat_id,
            recipient="AI"
        )
        
        # Get session_id from session manager
        session = None
        if self.ai_handler.memory_enabled:
            session = self.ai_handler.session_manager.get_session(chat_id)
        
        return {
            'response_text': ai_response.response_text,
            'tokens_used': ai_response.tokens_used,
            'session_id': session.session_id if session else None
        }
    
    def get_collection(self):
        """
        Get ChromaDB collection for testing assertions.
        
        Returns:
            ChromaDB Collection object or None if memory disabled
        """
        if not self.ai_handler.memory_enabled:
            return None
        
        return self.ai_handler.memory_manager.client.get_collection(
            name=self.config.memory['longterm']['collection_name']
        )
    
    def get_session(self, chat_id: str):
        """
        Get active session for a chat ID.
        
        Args:
            chat_id: WhatsApp chat ID
            
        Returns:
            Session object or None
        """
        if not self.ai_handler.memory_enabled:
            return None
        
        return self.ai_handler.session_manager.get_session(chat_id)
    
    def shutdown(self):
        """
        Gracefully shutdown the app context.
        Stops cleanup thread if running.
        """
        if self.cleanup_thread:
            self._logger.info("Stopping session cleanup thread...")
            self.cleanup_thread.stop()
            self._logger.info("Cleanup thread stopped")

def initialize_app(config_dict: dict) -> DeniDin:
    """
    Initialize DeniDin app with provided configuration.
    Used by integration tests to create app instance programmatically.
    
    Args:
        config_dict: Configuration dictionary (from JSON)
        
    Returns:
        DeniDin instance with handle_message(), get_collection(), shutdown() APIs
    """
    # Create AppConfiguration from dict (using from_dict for proper filtering)
    # Note: We need to write config to temp file and load it properly
    # OR filter unknown keys here similar to from_file()
    from dataclasses import fields
    valid_fields = {f.name for f in fields(AppConfiguration)}
    filtered_config = {k: v for k, v in config_dict.items() if k in valid_fields}
    
    config = AppConfiguration(**filtered_config)
    config.validate()
    
    # Initialize OpenAI client
    ai_client = OpenAI(
        api_key=config.ai_api_key,
        timeout=30.0
    )
    
    # Initialize AI handler
    ai_handler = AIHandler(ai_client, config)
    
    # Initialize WhatsApp handler
    whatsapp_handler = WhatsAppHandler()
    
    # Create DeniDin instance (will be used as context for background threads)
    denidin = DeniDin(ai_handler, config, whatsapp_handler, cleanup_thread=None)
    
    # Initialize memory system if enabled
    if ai_handler.memory_enabled:
        # Run startup cleanup using denidin as context
        run_startup_cleanup(denidin)
        
        # Start cleanup thread - get interval from nested config structure
        cleanup_interval = 3600  # Default
        if hasattr(config, 'memory') and isinstance(config.memory, dict):
            session_config = config.memory.get('session', {})
            cleanup_interval = session_config.get('cleanup_interval_seconds', 3600)
        elif hasattr(config, 'session_cleanup_interval_seconds'):
            cleanup_interval = config.session_cleanup_interval_seconds
        
        cleanup_thread = SessionCleanupThread(denidin, cleanup_interval)
        cleanup_thread.start()
        
        # Update denidin with cleanup thread reference
        denidin.cleanup_thread = cleanup_thread
    
    return denidin


# Initialize global context (will be populated after startup recovery)
global_context = None

# Log startup information with masked API keys
logger.info("=" * 60)
logger.info("DeniDin application starting...")
logger.info("Configuration:")
logger.info(f"  Green API Instance: {config.green_api_instance_id}")
logger.info(f"  Green API Token: {mask_api_key(config.green_api_token)}")
logger.info(f"  AI API Key: {mask_api_key(config.ai_api_key)}")
logger.info(f"  AI Model: {config.ai_model}")
logger.info(f"  Temperature: {config.temperature}")
logger.info(f"  Max Tokens: {config.ai_reply_max_tokens}")
logger.info(f"  Log Level: {config.log_level}")
logger.info("Handlers initialized: AIHandler, WhatsAppHandler")
logger.info("=" * 60)


@bot.router.message(type_message="textMessage")
def handle_text_message(notification: Notification) -> None:
    """
    Handle incoming text messages from WhatsApp with comprehensive error handling.
    Phase 6: Memory System Integration

    Args:
        notification: Green API notification object containing message data
    """
    # Ensure denidin_app is initialized
    if denidin_app is None:
        logger.error("CRITICAL: denidin_app not initialized - cannot process WhatsApp messages")
        try:
            notification.answer("Sorry, the application is not ready. Please try again in a moment.")
        except Exception:
            pass
        return
    
    try:
        # Validate message type
        if not denidin_app.whatsapp_handler.validate_message_type(notification):
            denidin_app.whatsapp_handler.handle_unsupported_message(notification)
            return

        # Process notification into WhatsAppMessage (includes message_id and received_timestamp)
        message = denidin_app.whatsapp_handler.process_notification(notification)

        # Create tracking prefix for all logs related to this message
        tracking = f"[msg_id={message.message_id}] [recv_ts={message.received_timestamp.isoformat()}]"

        # Log incoming message with tracking
        logger.info(
            f"{tracking} Received message from {message.sender_name} ({message.sender_id}): "
            f"{message.text_content[:100]}..."
        )

        # Check if application is mentioned in group (or if 1-on-1)
        if not denidin_app.whatsapp_handler.is_bot_mentioned_in_group(message):
            logger.debug(f"{tracking} Skipping group message without mention")
            return

        # Create AI request
        ai_request = denidin_app.ai_handler.create_request(message)
        logger.debug(f"{tracking} Created AI request {ai_request.request_id}")

        # Get AI response (with retry logic and fallbacks built-in)
        # Pass sender (WhatsApp ID) and recipient ('AI') for proper message tracking
        ai_response = denidin_app.ai_handler.get_response(
            ai_request,
            sender=message.sender_id,
            recipient="AI"
        )
        logger.info(
            f"{tracking} AI response generated: {ai_response.tokens_used} tokens, "
            f"{len(ai_response.response_text)} chars"
        )

        # Send response (with retry logic built-in)
        denidin_app.whatsapp_handler.send_response(notification, ai_response)
        logger.info(f"{tracking} Response sent to {message.sender_name}")

    except Exception as e:
        # Global exception handler - catches anything not handled by specific handlers
        # Try to include tracking if message was processed
        try:
            tracking = f"[msg_id={message.message_id}] [recv_ts={message.received_timestamp.isoformat()}]"
            logger.error(
                f"{tracking} Unexpected error processing message: {e}",
                exc_info=True  # Full traceback
            )
        except (NameError, AttributeError):
            # message not yet defined or missing tracking fields
            logger.error(
                f"Unexpected error processing message (no tracking available): {e}",
                exc_info=True
            )

        # Send generic fallback message to user
        try:
            fallback_message = (
                "Sorry, I encountered an error processing your message. "
                "Please try again."
            )
            notification.answer(fallback_message)
            try:
                logger.info(f"{tracking} Generic fallback message sent to user")
            except (NameError, AttributeError):
                logger.info("Generic fallback message sent to user (no tracking available)")
        except Exception as fallback_error:
            # Even fallback failed - log and continue
            try:
                logger.error(
                    f"{tracking} Failed to send fallback message: {fallback_error}",
                    exc_info=True
                )
            except (NameError, AttributeError):
                logger.error(
                    f"Failed to send fallback message (no tracking available): {fallback_error}",
                    exc_info=True
                )



if __name__ == "__main__":
    # Phase 6: Memory System Integration
    # Initialize app using shared initialization function
    
    logger.info("=" * 60)
    logger.info("Phase 6: Memory System Startup")
    logger.info("=" * 60)
    
    # Convert config to dict for initialize_app
    config_dict = {
        'green_api_instance_id': config.green_api_instance_id,
        'green_api_token': config.green_api_token,
        'ai_api_key': config.ai_api_key,
        'ai_model': config.ai_model,
        'ai_reply_max_tokens': config.ai_reply_max_tokens,
        'temperature': config.temperature,
        'log_level': config.log_level,
        'data_root': config.data_root,
        'feature_flags': config.feature_flags,
        'godfather_phone': config.godfather_phone,
        'memory': config.memory,
        'constitution_config': config.constitution_config,
        'user_roles': config.user_roles
    }
    
    # Initialize app (handles memory system, cleanup thread, recovery)
    denidin = initialize_app(config_dict)
    
    # Set global denidin_app for WhatsApp message handler
    denidin_app = denidin
    
    # Perform orphaned session recovery if memory enabled
    if denidin.ai_handler.memory_enabled:
        logger.info("Starting orphaned session recovery...")
        recovery_result = denidin.ai_handler.recover_orphaned_sessions()
        
        logger.info(
            f"Session recovery complete: "
            f"{recovery_result.get('total_found', 0)} found, "
            f"{recovery_result.get('transferred_to_long_term', 0)} transferred, "
            f"{recovery_result.get('loaded_to_short_term', 0)} loaded, "
            f"{recovery_result.get('failed', 0)} failed"
        )
    
    logger.info("=" * 60)
    
    # Track if shutdown has been requested (to avoid duplicate logging)
    shutdown_requested = [False]  # Use list to allow modification in nested function

    def signal_handler(signum, frame):
        """Handle SIGINT (Ctrl+C) and SIGTERM (systemd stop) gracefully."""
        if not shutdown_requested[0]:
            shutdown_requested[0] = True
            signal_name = "SIGTERM" if signum == signal.SIGTERM else "SIGINT"
            logger.info(f"Received shutdown signal ({signal_name})")
            logger.info("DeniDin application shutting down gracefully...")
            
            # Stop cleanup thread if memory enabled
            if denidin.ai_handler.memory_enabled and denidin.cleanup_thread:
                logger.info("Stopping session cleanup thread...")
                denidin.cleanup_thread.stop()
            
            # Raise KeyboardInterrupt to break out of bot.run_forever()
            raise KeyboardInterrupt()

    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logger.info("=" * 50)
    logger.info("DeniDin application is now running!")
    logger.info("Waiting for WhatsApp messages...")
    logger.info("Press Ctrl+C to stop")
    logger.info("=" * 50)

    try:
        # Start the WhatsApp message listener (blocking call)
        # Signal handlers will raise KeyboardInterrupt for graceful shutdown
        bot.run_forever()
    except KeyboardInterrupt:
        # This is raised by signal handlers or user Ctrl+C
        # Message already logged by signal handler or is implicit from Ctrl+C
        if not shutdown_requested[0]:
            logger.info("Received shutdown signal (Ctrl+C)")
            logger.info("DeniDin application shutting down gracefully...")
            
            # Stop cleanup thread if not already stopped
            if denidin.ai_handler.memory_enabled and denidin.cleanup_thread:
                logger.info("Stopping session cleanup thread...")
                denidin.cleanup_thread.stop()
    except Exception as e:
        # Catch any unexpected error to prevent crash
        logger.critical(
            f"Fatal error in bot.run_forever(): {e}",
            exc_info=True
        )
        logger.error("Application stopped due to fatal error - manual restart required")
        sys.exit(1)
