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

from src.utils.time_utils import local_from_timestamp

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


def validate_extraction_response(response):
    """Validate a media response produced by the STRUCTURED extraction path
    (bugfix-028), returning hebrew_ratio for logging.

    Replaces validate_response_full for images and PDFs. The image extractor no
    longer emits the old prose template ("סיכום:" + bullet list + "ביטחון:") -
    it returns JSON, and what the user reads is composed afterwards from the
    extracted text plus a question when one is needed. Asserting on the old
    template would be asserting on a format that deliberately no longer exists.
    PDFs are included because PDFExtractor delegates every page to the image
    extractor.

    Checks:
    1. Response exists and is not empty
    2. Response is Hebrew-only (>85% Hebrew chars)
    3. No FILLER follow-ups

    Note on (3): unlike assert_no_followups, a trailing question mark is NOT a
    failure here. The system is now required to ASK when a document can't be
    classified or a required field is missing, so a reply legitimately ends in a
    question. Only conversational filler ("מה אני יכול לעזור") is still banned -
    that distinction is the whole point of the rule, and conflating the two
    would punish exactly the behaviour bugfix-028 set out to produce.
    """
    assert_response_exists(response)
    hebrew_ratio = assert_hebrew_only(response)

    filler = ['מה אני יכול', 'איך אני יכול', 'רוצה ש', 'צריך עזרה', 'what can', 'how can', 'need help']
    final_section = response[-200:] if len(response) > 200 else response
    found = [p for p in filler if p.lower() in final_section.lower()]
    assert not found, f"Response ends with filler follow-up(s) {found}\nResponse: {response}"

    return hebrew_ratio


class ClarificationAnswerBank:
    """
    2026-08-18 (player-review follow-up): a real, curated E2E test message's
    turn-1 model behavior can be genuinely non-deterministic - sometimes it
    captures directly, sometimes it asks a clarifying question about one or
    more specific fields first (real observed example: "is משרד הרווחה the
    payer or the related matter? is 'בית משפט השלום' what's meant?"). A test
    that only ever sends the original message can't reliably reach the
    capture it's actually trying to assert on.

    Deterministic, keyword-based answer composer for exactly this situation -
    NO second AI call, no NLP. This works because the test fixture is fixed
    and curated: the test author already knows the ground-truth correct value
    for every field the model could plausibly ask about, so "answering the
    question" reduces to "which known topic(s) does the question's own text
    touch" (keyword matching), not actually understanding free text.

    Usage:
        bank = ClarificationAnswerBank([
            {"topic": "payer_vs_matter", "keywords": ["משלם", "גורם המשלם"],
             "answer": "משרד הרווחה לא משלם, זה מקום העבודה של הלקוח"},
            {"topic": "court_name", "keywords": ["בית משפט", "משפט שלום"],
             "answer": "הכוונה ל'בית משפט השלום', כן"},
        ])
        next_message, matched_topics = bank.compose_answer(model_reply_text)

    If the question's text doesn't match ANY topic's keywords, compose_answer
    returns `fallback` (default: "לא הבנתי את השאלה, תעשה מה שאתה מבין") and an
    empty matched-topics list - lets the model proceed on its own judgment
    rather than the test guessing wrong or getting the conversation stuck. If
    it matches MULTIPLE topics (the model asking about more than one field at
    once), every matched topic's answer is included, joined with "; ".
    """

    DEFAULT_FALLBACK = "לא הבנתי את השאלה, תעשה מה שאתה מבין"

    def __init__(self, topics, fallback=None):
        """
        topics: list of {"topic": str, "keywords": [str, ...], "answer": str}
            - one entry per field/ambiguity this test's fixture message could
            plausibly raise a question about. Extend with a new entry the
            moment a real run surfaces a question no existing topic matches -
            never widen an existing topic's keywords to cover it by
            coincidence, that risks a false match on an unrelated future
            question.
        fallback: sent when no topic matches; defaults to DEFAULT_FALLBACK.
        """
        self.topics = topics
        self.fallback = fallback if fallback is not None else self.DEFAULT_FALLBACK

    def compose_answer(self, question_text):
        """Returns (answer_text, matched_topics) - matched_topics is [] exactly
        when the fallback was used, so callers can log/assert on whether a
        real match happened vs. the safety-net fired."""
        matched_topics = []
        matched_answers = []
        for entry in self.topics:
            if any(keyword in question_text for keyword in entry["keywords"]):
                matched_topics.append(entry["topic"])
                matched_answers.append(entry["answer"])
        if not matched_answers:
            return self.fallback, []
        return "; ".join(matched_answers), matched_topics


def converse_until_ledger_events_captured(
    *, handle_text_message, chat_id, first_message_text, answer_bank,
    events_for_chat, base_timestamp, base_id_message, sender_data,
    instance_data=None, max_turns=4, turn_interval_seconds=30, test_logger=None,
):
    """
    Generic multi-turn E2E driver (2026-08-18) for a real ledger-capture test
    whose model behavior on the first turn is non-deterministic (sometimes
    captures directly, sometimes asks a clarifying question first). Sends
    first_message_text; after EACH turn, checks events_for_chat(chat_id) - the
    moment it returns anything, stops and returns those events immediately
    (never sends a further turn once real capture has happened - sending an
    unconditional follow-up after a turn that already captured is exactly what
    caused a real observed DOUBLE capture, 6 events instead of 3, in this
    mechanism's first version). If still empty, treats that turn's own reply
    as a clarifying question, runs it through answer_bank.compose_answer(),
    and sends the composed answer as the next turn - up to max_turns total.

    Args:
        handle_text_message: the real denidin.handle_text_message callable.
        chat_id: this conversation's chat id.
        first_message_text: the real fixture message to send on turn 1.
        answer_bank: a ClarificationAnswerBank instance.
        events_for_chat: callable(chat_id) -> list of persisted ledger event
            dicts for this chat (e.g. a test class's own _events_for_chat).
        base_timestamp: turn 1's Green API notification timestamp (unix
            epoch seconds, fixed not wall-clock - see REQ-ID-002/003 in any
            caller's own bucket-cleanup code). Turn N uses
            base_timestamp + (N-1) * turn_interval_seconds.
        base_id_message: prefix for each turn's synthetic idMessage
            (suffixed "_<turn_num>").
        sender_data / instance_data: passed straight into
            create_real_notification's senderData/instanceData - instance_data
            defaults to the same fixed test instance every E2E test already
            uses.
        max_turns: safety cap - never loops forever waiting for a capture that
            isn't coming.
        turn_interval_seconds: spacing between synthetic turn timestamps.
        test_logger: optional logger for GIVEN/WHEN/THEN-style progress lines
            (falls back to this module's own logger).

    Returns:
        (events, transcript) - events is whatever events_for_chat returned the
        turn capture was detected (never empty). transcript is
        [{"turn": int, "sent": str, "reply": str, "matched_topics": [str,...]}]
        in turn order, for logging/debugging - matched_topics is [] on a turn
        that used the fallback (or on the final captured turn, which never
        composes an answer at all).

    Raises:
        AssertionError if no events exist for chat_id after max_turns turns.
    """
    log = test_logger or logger
    transcript = []
    events = []
    text = first_message_text
    ts = base_timestamp

    for turn_num in range(1, max_turns + 1):
        notification = create_real_notification({
            'typeWebhook': 'incomingMessageReceived',
            'timestamp': ts,
            'idMessage': f"{base_id_message}_{turn_num}",
            'instanceData': instance_data or {
                'idInstance': 7103000000, 'wid': '972501234567@c.us', 'typeInstance': 'whatsapp'
            },
            'senderData': sender_data,
            'messageData': {
                'typeMessage': 'textMessage',
                'textMessageData': {'textMessage': text},
            },
        })
        log.info(f"GIVEN turn {turn_num}: {text!r}")
        handle_text_message(notification)
        reply = get_response(notification)
        assert_response_exists(reply)
        log.info(f"THEN turn {turn_num} reply: {reply!r}")

        events = events_for_chat(chat_id)
        entry = {"turn": turn_num, "sent": text, "reply": reply, "matched_topics": []}
        transcript.append(entry)

        if events:
            log.info(f"Ledger events detected after turn {turn_num} - stopping the conversation here")
            return events, transcript

        text, matched_topics = answer_bank.compose_answer(reply)
        entry["matched_topics"] = matched_topics
        log.info(f"No events yet - composed next turn from matched_topics={matched_topics!r}: {text!r}")
        ts += turn_interval_seconds

    raise AssertionError(
        f"No ledger events captured for chat_id={chat_id!r} after {max_turns} turn(s) - "
        f"transcript: {transcript!r}"
    )


def reserve_ledger_event_bucket_prefixes(base_timestamp, max_turns, turn_interval_seconds=30, letter="A"):
    """The full set of event_id bucket prefixes (letter+DDMMYY+HHMM) a
    converse_until_ledger_events_captured call COULD produce across ALL its
    possible turns, regardless of how many turns actually run on a given real
    run - for a caller's before/after cleanup. LedgerEventManager._next_seq
    scans real files on disk for REQ-ID-002's collision check, never cleaned
    automatically between test runs (a real, order-independent failure,
    2026-08-03 - see any caller's own docstring for the incident)."""
    return {
        f"{letter}{local_from_timestamp(base_timestamp + i * turn_interval_seconds).strftime('%d%m%y%H%M')}"
        for i in range(max_turns)
    }
