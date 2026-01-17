#!/usr/bin/env python3
"""
DeniDin WhatsApp AI Chatbot - Main Entry Point
Integrates Green API for WhatsApp messaging with OpenAI ChatGPT.
"""
import os
from pathlib import Path
from whatsapp_chatbot_python import GreenAPIBot, Notification
from openai import OpenAI
from src.models.config import BotConfiguration
from src.utils.logger import get_logger

# Configuration
CONFIG_PATH = os.getenv('CONFIG_PATH', 'config/config.json')

# Load configuration
config = BotConfiguration.from_file(CONFIG_PATH)
config.validate()

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

# Log startup information
logger.info(f"DeniDin bot starting...")
logger.info(f"Green API Instance: {config.green_api_instance_id}")
logger.info(f"AI Model: {config.ai_model}")
logger.info(f"Poll Interval: {config.poll_interval_seconds}s")
logger.info(f"Log Level: {config.log_level}")


@bot.router.message(type_message="textMessage")
def handle_text_message(notification: Notification) -> None:
    """
    Handle incoming text messages from WhatsApp.
    
    Args:
        notification: Green API notification object containing message data
    """
    try:
        # Extract message data
        message_text = notification.event['messageData']['textMessageData']['textMessage']
        sender_name = notification.event['senderData'].get('senderName', 'Unknown')
        sender_id = notification.event['senderData']['sender']
        
        # Log incoming message
        logger.info(f"Received message from {sender_name} ({sender_id}): {message_text}")
        
        # Prepare OpenAI API request
        messages = [
            {"role": "system", "content": config.system_message},
            {"role": "user", "content": message_text}
        ]
        
        logger.debug(f"Sending request to OpenAI API with model {config.ai_model}")
        
        # Call OpenAI API
        completion = openai_client.chat.completions.create(
            model=config.ai_model,
            messages=messages,
            max_tokens=config.max_tokens,
            temperature=config.temperature
        )
        
        # Extract AI response
        ai_response = completion.choices[0].message.content
        tokens_used = completion.usage.total_tokens
        
        logger.info(f"AI response generated ({tokens_used} tokens): {ai_response[:100]}...")
        logger.debug(f"Full AI response: {ai_response}")
        
        # Send response back to WhatsApp
        notification.answer(ai_response)
        logger.info(f"Response sent to {sender_name}")
        
    except Exception as e:
        # Log error with full traceback
        logger.error(f"Error processing message: {e}", exc_info=True)
        
        # Send fallback message to user
        fallback_message = "Sorry, I encountered an error. Please try again."
        notification.answer(fallback_message)
        logger.info("Fallback message sent to user")


if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("DeniDin bot is now running!")
    logger.info("Waiting for WhatsApp messages...")
    logger.info("Press Ctrl+C to stop")
    logger.info("=" * 50)
    
    # Start the bot (blocking call)
    bot.run_forever()
