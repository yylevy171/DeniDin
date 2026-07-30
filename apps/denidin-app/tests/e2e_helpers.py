"""
Shared helpers for End-to-End (expensive) tests.

Provides common utilities for WhatsApp E2E testing:
- Notification creation and response tracking
- Response validation helpers
- Text processing utilities
"""

import re
import json
import logging
from pathlib import Path
from whatsapp_chatbot_python import Notification

logger = logging.getLogger(__name__)


def create_real_notification(event_dict):
    """
    Create real SDK Notification object (not mocked).
    
    Tracks calls to answer() without actually calling Green API.
    
    Args:
        event_dict: Dictionary containing the webhook event data
        
    Returns:
        Notification object with answer() method tracked
    """
    notification = Notification.__new__(Notification)
    notification.event = event_dict
    notification._test_sent_messages = []
    
    def track_answer(message):
        """Track what would be sent to user"""
        notification._test_sent_messages.append(message)
        logger.info(f"\n📤 Would send to user: {message}...")
    
    notification.answer = track_answer
    return notification


def get_response(notification):
    """Get the response that was sent to user."""
    return notification._test_sent_messages[0] if notification._test_sent_messages else None


def assert_response_exists(response):
    """Assert: Response exists and is not empty."""
    assert response is not None, "CRITICAL: User got NO RESPONSE (silent drop)"
    assert len(response) > 0, "User got empty response"
    # Should NOT be an error message (file downloaded successfully)
    assert "שגיאה" not in response and "נכשל" not in response, f"Got error: {response}"


def strip_emails_and_domains(text):
    """Remove email addresses and web domains from text for Hebrew ratio check."""
    # Remove email addresses (user@domain.com)
    text = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '', text)
    # Remove web domains (www.domain.com, domain.com)
    text = re.sub(r'(?:www\.)?[\w\.-]+\.(?:com|co|il|org|net|edu)\b', '', text)
    # Remove isolated URLs/domains with slashes
    text = re.sub(r'https?://\S+', '', text)
    return text


def assert_hebrew_only(response):
    """Assert: Response must be in Hebrew only (>85% non-English alphabetic chars).
    
    Logic:
    - Count only English alphabetic characters (a-z)
    - Count only alphabetic characters (Hebrew + English)
    - Hebrew ratio = (alphabetic - english) / alphabetic
    - Non-alphanumeric chars (punctuation, symbols, etc.) are treated as "Hebrew" (not penalized)
    
    Returns:
        hebrew_ratio: The calculated ratio of Hebrew characters (0.0-1.0)
    """
    # Strip emails and web domains before checking ratio
    cleaned_response = strip_emails_and_domains(response)
    
    # Count English alphabetic characters
    english_chars = sum(1 for c in cleaned_response if 'a' <= c.lower() <= 'z')
    # Count all alphabetic characters (Hebrew, English, etc.)
    # Non-alphabetic chars are not counted in the denominator, so they don't hurt the ratio
    alpha_chars = sum(1 for c in cleaned_response if c.isalpha())
    # Hebrew ratio = (all_alpha - english) / all_alpha
    # This treats Hebrew + non-alphanumeric as "Hebrew"
    hebrew_ratio = (alpha_chars - english_chars) / alpha_chars if alpha_chars > 0 else 0
    assert hebrew_ratio > 0.85, f"Response must be Hebrew only - found {english_chars} English chars out of {alpha_chars} total alpha chars (after stripping emails/domains), Hebrew ratio: {hebrew_ratio:.1%}\nFull Response: {response}"
    return hebrew_ratio


def assert_summary_exists(response):
    """Assert: Summary must exist with mandatory 'סיכום:' section (required by prompt)."""
    assert "סיכום:" in response, f"Response missing 'סיכום:' section (required by prompt)\nResponse: {response}"


def assert_metadata_bullets(response):
    """Assert: Metadata bullets must be present (• or -)."""
    assert '•' in response or '-' in response, f"Response missing metadata bullets - check if extractors are returning key_points\nResponse: {response}"


def assert_no_followups(response):
    """Assert: No follow-up questions AT THE END (response is informational only).
    
    Only check the last section after the final metadata/notes, to ignore
    OCR garbage and extracted text that may contain stray question marks.
    """
    # Get the last section - everything after the final "הערות:" (notes) section
    # This ensures we only check the bot's actual final response, not OCR garbage
    if "הערות:" in response:
        # Find the last occurrence of "הערות:" and check what comes after
        last_notes_idx = response.rfind("הערות:")
        final_section = response[last_notes_idx:]
    else:
        # If no notes section, check the last 200 chars
        final_section = response[-200:] if len(response) > 200 else response
    
    # Check for conversational question patterns at the end
    question_patterns = ['מה אני יכול', 'איך אני יכול', 'רוצה ש', 'צריך עזרה', 'what can', 'how can', 'need help']
    found_questions = [p for p in question_patterns if p.lower() in final_section.lower()]
    
    # Also check if response ends with a question mark (after trimming whitespace)
    ends_with_question = final_section.rstrip().endswith('?')
    
    assert len(found_questions) == 0 and not ends_with_question, \
        f"Response should end with information, not questions. Found: {found_questions if found_questions else 'ends with ?'}\nFinal section: {final_section}"


def validate_response_full(response):
    """Validate response against all assertions and return hebrew_ratio for logging.
    
    Runs all validation checks:
    1. Response exists and is not empty
    2. Response is in Hebrew only (>85% Hebrew chars)
    3. Summary section exists with 'סיכום:'
    4. Metadata bullets present
    5. No follow-up questions at end
    
    Returns:
        hebrew_ratio: The calculated ratio of Hebrew characters (0.0-1.0)
    """
    assert_response_exists(response)
    hebrew_ratio = assert_hebrew_only(response)
    assert_summary_exists(response)
    assert_metadata_bullets(response)
    assert_no_followups(response)
    return hebrew_ratio


def assert_image_path_persisted(denidin_app, chat_id):
    """bugfix-009 (reopened 2026-07-30): assert the real, persisted-to-disk session
    for chat_id has, as its MOST RECENT `user` message, an `image_path` that's set
    and resolves to a real file under data_root - not just that a session/summary
    exists (bugfix-017's own coverage), which said nothing about image_path
    specifically and is exactly how this regressed silently.

    Checks only the most recent user message rather than "any user message in this
    chat_id's whole history", since several tests in the same class-scoped session
    share one chat_id/session across many turns - a stale image_path from an earlier
    turn would otherwise mask a real regression on the turn this call actually cares
    about. Call this immediately after the turn under test completes.

    Reads session.json/message files directly off disk (not the in-memory Session
    object) so this proves genuine persistence, matching the pattern used for ledger
    event assertions in test_ledger_event_capture_e2e.py.

    Returns the resolved absolute Path to the image file, for further assertions
    (e.g. checking it's non-empty) if a caller wants them.
    """
    session_manager = denidin_app.ai_handler.session_manager
    session_id = session_manager.chat_to_session[chat_id]
    messages_dir = Path(session_manager.storage_dir) / session_id / "messages"

    with open(Path(session_manager.storage_dir) / session_id / "session.json", encoding='utf-8') as f:
        session_data = json.load(f)

    last_user_message = None
    for message_id in session_data["message_ids"]:
        with open(messages_dir / f"{message_id}.json", encoding='utf-8') as f:
            message_data = json.load(f)
        if message_data["role"] == "user":
            last_user_message = message_data

    assert last_user_message is not None, (
        f"No user session message found at all for chat_id={chat_id!r}"
    )
    assert last_user_message.get("image_path"), (
        f"Most recent user session message for chat_id={chat_id!r} has no image_path "
        f"(bugfix-009 regression: media turns are stored, but without image_path). "
        f"Message: {last_user_message}"
    )

    resolved = Path(denidin_app.config.data_root) / last_user_message["image_path"]
    assert resolved.is_file(), (
        f"Persisted image_path {last_user_message['image_path']!r} does not resolve "
        f"to a real file on disk (resolved: {resolved})"
    )
    return resolved
