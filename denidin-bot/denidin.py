#!/usr/bin/env python3
"""
DeniDin WhatsApp AI Chatbot - Main Entry Point
Integrates Green API for WhatsApp messaging with OpenAI ChatGPT.
Phase 6: US4 - Configuration & Deployment
"""
import os
import sys
import signal
from pathlib import Path
from whatsapp_chatbot_python import GreenAPIBot, Notification
from openai import OpenAI
from src.models.config import BotConfiguration
from src.utils.logger import get_logger
from src.handlers.ai_handler import AIHandler
from src.handlers.whatsapp_handler import WhatsAppHandler

# Configuration
CONFIG_PATH = os.getenv('CONFIG_PATH', 'config/config.json')

# Load and validate configuration
try:
    config = BotConfiguration.from_file(CONFIG_PATH)
    config.validate()
except ValueError as e:
    # Configuration validation failed - exit with clear error message
    print(f"ERROR: Invalid configuration in {CONFIG_PATH}", file=sys.stderr)
    print(f"Validation error: {e}", file=sys.stderr)
    print("Please fix the configuration file and restart the bot.", file=sys.stderr)
    sys.exit(1)
except FileNotFoundError:
    print(f"ERROR: Configuration file not found: {CONFIG_PATH}", file=sys.stderr)
    print("Please create config/config.json from config/config.example.json", file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f"ERROR: Failed to load configuration: {e}", file=sys.stderr)
    sys.exit(1)

# Setup logging
logger = get_logger(__name__, log_level=config.log_level)


def mask_api_key(key: str) -> str:
    """
    Mask API key for secure logging.
    Shows first 10 characters followed by '...'
    
    Args:
        key: API key to mask
        
    Returns:
        Masked API key string
    """
    if len(key) > 10:
        return key[:10] + "..."
    return key


# Initialize Green API bot
bot = GreenAPIBot(
    config.green_api_instance_id,
    config.green_api_token
)

# Initialize OpenAI client
openai_client = OpenAI(
    api_key=config.openai_api_key,
    timeout=30.0
)

# Initialize handlers
ai_handler = AIHandler(openai_client, config)
whatsapp_handler = WhatsAppHandler()

# Log startup information with masked API keys
logger.info("=" * 60)
logger.info("DeniDin bot starting...")
logger.info("Configuration:")
logger.info(f"  Green API Instance: {config.green_api_instance_id}")
logger.info(f"  Green API Token: {mask_api_key(config.green_api_token)}")
logger.info(f"  OpenAI API Key: {mask_api_key(config.openai_api_key)}")
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
    Phase 6: US4 - Configuration & Deployment
    
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
        
        # Check if bot is mentioned in group (or if 1-on-1)
        if not whatsapp_handler.is_bot_mentioned_in_group(message):
            logger.debug(f"{tracking} Skipping group message without mention")
            return
        
        # Create AI request
        ai_request = ai_handler.create_request(message)
        logger.debug(f"{tracking} Created AI request {ai_request.request_id}")
        
        # Get AI response (with retry logic and fallbacks built-in)
        ai_response = ai_handler.get_response(ai_request)
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
    # Track if shutdown has been requested (to avoid duplicate logging)
    shutdown_requested = [False]  # Use list to allow modification in nested function
    
    def signal_handler(signum, frame):
        """Handle SIGINT (Ctrl+C) and SIGTERM (systemd stop) gracefully."""
        if not shutdown_requested[0]:
            shutdown_requested[0] = True
            signal_name = "SIGTERM" if signum == signal.SIGTERM else "SIGINT"
            logger.info(f"Received shutdown signal ({signal_name})")
            logger.info("DeniDin bot shutting down gracefully...")
            # Raise KeyboardInterrupt to break out of bot.run_forever()
            raise KeyboardInterrupt()
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("=" * 50)
    logger.info("DeniDin bot is now running!")
    logger.info("Waiting for WhatsApp messages...")
    logger.info("Press Ctrl+C to stop")
    logger.info("=" * 50)
    
    try:
        # Start the bot (blocking call)
        # Signal handlers will raise KeyboardInterrupt for graceful shutdown
        bot.run_forever()
    except KeyboardInterrupt:
        # This is raised by signal handlers or user Ctrl+C
        # Message already logged by signal handler or is implicit from Ctrl+C
        if not shutdown_requested[0]:
            logger.info("Received shutdown signal (Ctrl+C)")
            logger.info("DeniDin bot shutting down gracefully...")
    except Exception as e:
        # Catch any unexpected error to prevent crash
        logger.critical(
            f"Fatal error in bot.run_forever(): {e}",
            exc_info=True
        )
        logger.error("Bot stopped due to fatal error - manual restart required")
        sys.exit(1)
