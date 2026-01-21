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

# Initialize handlers
ai_handler = AIHandler(ai_client, config)
whatsapp_handler = WhatsAppHandler()


class GlobalContext:
    """
    Global context object accessible to all threads.
    Provides centralized access to all application components.
    Used by background threads (SessionManager cleanup) to transfer sessions.
    """
    def __init__(self, session_manager, memory_manager, ai_handler, config):
        self.session_manager = session_manager
        self.memory_manager = memory_manager
        self.ai_handler = ai_handler
        self.config = config


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
logger.info(f"  Max Tokens: {config.max_tokens}")
logger.info(f"  System Message: {config.system_message[:50]}...")
logger.info(f"  Poll Interval: {config.poll_interval_seconds}s")
logger.info(f"  Log Level: {config.log_level}")
logger.info(f"  Max Retries: {config.max_retries}")
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
    try:
        # Validate message type
        if not whatsapp_handler.validate_message_type(notification):
            whatsapp_handler.handle_unsupported_message(notification)
            return

        # Process notification into WhatsAppMessage (includes message_id and received_timestamp)
        message = whatsapp_handler.process_notification(notification)

        # Create tracking prefix for all logs related to this message
        tracking = f"[msg_id={message.message_id}] [recv_ts={message.received_timestamp.isoformat()}]"

        # Log incoming message with tracking
        logger.info(
            f"{tracking} Received message from {message.sender_name} ({message.sender_id}): "
            f"{message.text_content[:100]}..."
        )

        # Check if application is mentioned in group (or if 1-on-1)
        if not whatsapp_handler.is_bot_mentioned_in_group(message):
            logger.debug(f"{tracking} Skipping group message without mention")
            return

        # Create AI request
        ai_request = ai_handler.create_request(message)
        logger.debug(f"{tracking} Created AI request {ai_request.request_id}")

        # Get AI response (with retry logic and fallbacks built-in)
        # Pass sender (WhatsApp ID) and recipient ('AI') for proper message tracking
        ai_response = ai_handler.get_response(
            ai_request,
            sender=message.sender_id,
            recipient="AI"
        )
        logger.info(
            f"{tracking} AI response generated: {ai_response.tokens_used} tokens, "
            f"{len(ai_response.response_text)} chars"
        )

        # Send response (with retry logic built-in)
        whatsapp_handler.send_response(notification, ai_response)
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
    # Initialize global context and perform startup recovery
    
    logger.info("=" * 60)
    logger.info("Phase 6: Memory System Startup")
    logger.info("=" * 60)
    
    # Initialize global context if memory system enabled
    if ai_handler.memory_enabled:
        logger.info("Memory system enabled - initializing global context")
        
        global_context = GlobalContext(
            session_manager=ai_handler.session_manager,
            memory_manager=ai_handler.memory_manager,
            ai_handler=ai_handler,
            config=config
        )
        
        # Wire cleanup thread to use global context for session transfers
        # Update SessionManager's _cleanup_expired_sessions to call transfer
        original_cleanup = ai_handler.session_manager._cleanup_expired_sessions
        
        def cleanup_with_transfer():
            """Enhanced cleanup that transfers expired sessions to long-term memory."""
            from datetime import datetime, timedelta, timezone
            
            now = datetime.now(timezone.utc)
            cutoff = now - timedelta(hours=ai_handler.session_manager.session_timeout_hours)
            expired_base = ai_handler.session_manager.storage_dir / "expired"
            
            for session_dir in ai_handler.session_manager.storage_dir.iterdir():
                if not session_dir.is_dir() or session_dir.name == "expired":
                    continue
                
                session_file = session_dir / "session.json"
                if not session_file.exists():
                    continue
                
                try:
                    session = ai_handler.session_manager._load_session(session_dir.name)
                    last_active = datetime.fromisoformat(session.last_active)
                    
                    if last_active < cutoff:
                        # Transfer to long-term memory BEFORE archiving
                        logger.info(
                            f"Periodic cleanup: Transferring expired session {session.session_id} "
                            f"to long-term memory"
                        )
                        
                        try:
                            result = global_context.ai_handler.transfer_session_to_long_term_memory(
                                chat_id=session.whatsapp_chat,
                                session_id=session.session_id
                            )
                            
                            if result.get('success'):
                                logger.info(
                                    f"Successfully transferred session {session.session_id}: "
                                    f"memory_id={result.get('memory_id')}"
                                )
                            else:
                                logger.error(
                                    f"Failed to transfer session {session.session_id}: "
                                    f"{result.get('reason')}"
                                )
                        except Exception as transfer_error:
                            logger.error(
                                f"Error transferring session {session.session_id}: {transfer_error}",
                                exc_info=True
                            )
                        
                        # Now archive (original cleanup logic)
                        archive_date = last_active.strftime("%Y-%m-%d")
                        archive_dir = expired_base / archive_date
                        archive_dir.mkdir(parents=True, exist_ok=True)
                        
                        dest = archive_dir / session_dir.name
                        session_dir.rename(dest)
                        
                        # Remove from index
                        if session.whatsapp_chat in ai_handler.session_manager.chat_to_session:
                            del ai_handler.session_manager.chat_to_session[session.whatsapp_chat]
                        
                        logger.info(
                            f"Archived expired session {session.session_id} to expired/{archive_date}/"
                        )
                        
                except Exception as e:
                    logger.error(f"Failed to cleanup session {session_dir.name}: {e}")
        
        # Replace cleanup method with enhanced version
        ai_handler.session_manager._cleanup_expired_sessions = cleanup_with_transfer
        
        logger.info("Global context initialized - cleanup thread wired to transfer sessions")
        
        # Perform startup recovery (US-MEM-07)
        logger.info("Starting orphaned session recovery...")
        recovery_result = ai_handler.recover_orphaned_sessions()
        
        logger.info(
            f"Session recovery complete: "
            f"{recovery_result.get('total_found', 0)} found, "
            f"{recovery_result.get('transferred_to_long_term', 0)} transferred, "
            f"{recovery_result.get('loaded_to_short_term', 0)} loaded, "
            f"{recovery_result.get('failed', 0)} failed"
        )
    else:
        logger.info("Memory system disabled - skipping global context and recovery")
    
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
            if ai_handler.memory_enabled and ai_handler.session_manager:
                logger.info("Stopping SessionManager cleanup thread...")
                ai_handler.session_manager.stop_cleanup_thread()
            
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
            if ai_handler.memory_enabled and ai_handler.session_manager:
                logger.info("Stopping SessionManager cleanup thread...")
                ai_handler.session_manager.stop_cleanup_thread()
    except Exception as e:
        # Catch any unexpected error to prevent crash
        logger.critical(
            f"Fatal error in bot.run_forever(): {e}",
            exc_info=True
        )
        logger.error("Application stopped due to fatal error - manual restart required")
        sys.exit(1)
