#!/usr/bin/env python3
"""
DeniDin WhatsApp AI Chatbot - Main Entry Point
Integrates Green API for WhatsApp messaging with OpenAI ChatGPT.
Phase 6: US4 - Configuration & Deployment
"""
import os
import sys
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

# Log startup information
logger.info(f"DeniDin bot starting...")
logger.info(f"Green API Instance: {config.green_api_instance_id}")
logger.info(f"AI Model: {config.ai_model}")
logger.info(f"Poll Interval: {config.poll_interval_seconds}s")
logger.info(f"Log Level: {config.log_level}")
logger.info(f"Handlers initialized: AIHandler, WhatsAppHandler")


@bot.router.message(type_message="textMessage")
def handle_text_message(notification: Notification) -> None:
    """
    Handle incoming text messages from WhatsApp with comprehensive error handling.
    Phase 5: US3 - Error Handling & Resilience
    
    Args:
        notification: Green API notification object containing message data
    """
    try:
        # Validate message type
        if not whatsapp_handler.validate_message_type(notification):
            whatsapp_handler.handle_unsupported_message(notification)
            return
        
        # Process notification into WhatsAppMessage
        message = whatsapp_handler.process_notification(notification)
        
        # Log incoming message
        logger.info(
            f"Received message from {message.sender_name} ({message.sender_id}): "
            f"{message.text_content[:100]}..."
        )
        
        # Check if bot is mentioned in group (or if 1-on-1)
        if not whatsapp_handler.is_bot_mentioned_in_group(message):
            logger.debug(f"Skipping group message without mention: {message.message_id}")
            return
        
        # Create AI request
        ai_request = ai_handler.create_request(message)
        logger.debug(f"Created AI request {ai_request.request_id}")
        
        # Get AI response (with retry logic and fallbacks built-in)
        ai_response = ai_handler.get_response(ai_request)
        logger.info(
            f"AI response generated: {ai_response.tokens_used} tokens, "
            f"{len(ai_response.response_text)} chars"
        )
        
        # Send response (with retry logic built-in)
        whatsapp_handler.send_response(notification, ai_response)
        logger.info(f"Response sent to {message.sender_name}")
        
    except Exception as e:
        # Global exception handler - catches anything not handled by specific handlers
        logger.error(
            f"Unexpected error processing message: {e}",
            exc_info=True  # Full traceback
        )
        
        # Send generic fallback message to user
        try:
            fallback_message = (
                "Sorry, I encountered an error processing your message. "
                "Please try again."
            )
            notification.answer(fallback_message)
            logger.info("Generic fallback message sent to user")
        except Exception as fallback_error:
            # Even fallback failed - log and continue
            logger.error(
                f"Failed to send fallback message: {fallback_error}",
                exc_info=True
            )



if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("DeniDin bot is now running!")
    logger.info("Waiting for WhatsApp messages...")
    logger.info("Press Ctrl+C to stop")
    logger.info("=" * 50)
    
    try:
        # Start the bot (blocking call)
        # This is wrapped in try-catch to ensure the app never crashes
        # except on explicit signals (SIGINT/SIGTERM)
        bot.run_forever()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal (Ctrl+C)")
        logger.info("DeniDin bot shutting down gracefully...")
    except Exception as e:
        # Catch any unexpected error to prevent crash
        logger.critical(
            f"Fatal error in bot.run_forever(): {e}",
            exc_info=True
        )
        logger.error("Bot stopped due to fatal error - manual restart required")
        import sys
        sys.exit(1)
