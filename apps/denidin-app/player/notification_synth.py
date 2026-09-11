"""
Notification synthesizer (Feature 043, tasks.md T010).

Converts a ParsedMessage (export_parser.py's own input shape) into a
Green-API-shaped `event` dict - the same shape WhatsAppMessage.from_notification
(src/models/message.py) already parses today, matching the pattern already
established by tests/e2e_helpers.py's create_real_notification. This is the
boundary that lets the player drive DeniDin's real, unmodified live handler
functions (denidin.py) without ever needing a live Green API connection.

See contracts/message-source.md for the full contract.
"""
import mimetypes
import uuid
from pathlib import Path
from typing import Optional, Tuple

from player.export_parser import ParsedMessage

# Extension -> Green API typeMessage, matching src/managers/media_file_manager.py's
# own SUPPORTED_IMAGE_FORMATS + pdf/docx routing exactly (not re-derived from a
# second, possibly-inconsistent table).
_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png"}
_DOCUMENT_EXTENSIONS = {"pdf", "docx"}

# Fallback MIME types for the extensions we actually support - mimetypes.guess_type
# already handles these correctly on every platform this runs on, but an explicit
# fallback avoids ever depending on the host's mimetypes database being complete.
_MIME_FALLBACKS = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _guess_mime_type(filename: str) -> str:
    guessed, _encoding = mimetypes.guess_type(filename)
    if guessed:
        return guessed
    ext = Path(filename).suffix.lower().lstrip('.')
    return _MIME_FALLBACKS.get(ext, "application/octet-stream")


def synthesize_notification(
    msg: ParsedMessage,
    chat_id: str,
    sender_id: str,
    media_base_url: Optional[str] = None,
) -> Optional[Tuple[dict, str]]:
    """
    Builds a Green-API-shaped `event` dict for one ParsedMessage.

    Args:
        msg: the parsed export message to synthesize.
        chat_id: the real chat's JID (operator-supplied, per contracts/player-cli.md -
            an export identifies a conversation by name only, never a JID).
        sender_id: this message's sender's JID (resolved via the operator-supplied
            --sender-map, per contracts/message-source.md - never guessed).
        media_base_url: base URL of the player's LocalMediaServer, required
            whenever `msg` has an attachment (used to build `downloadUrl`).

    Returns:
        (event, type_message) tuple, or None if `msg`'s attachment extension
        isn't one DeniDin's live pipeline handles (voice notes, video, etc.) -
        per contracts/message-source.md, these are never synthesized; the
        caller routes them to a "not-qualifying: unsupported-type" outcome
        without calling dispatch at all.
    """
    timestamp = int(msg.timestamp.timestamp())
    sender_data = {
        "chatId": chat_id,
        "sender": sender_id,
        "senderName": msg.sender_display_name,
    }
    base_event = {
        "typeWebhook": "incomingMessageReceived",
        "timestamp": timestamp,
        # Feature 069: marks this as a replayed (not live) message. `timestamp`
        # above is the message's ORIGINAL conversation time; WhatsAppMessage
        # .from_notification reads this flag so AIHandler dates the bot's own
        # reply just after that original moment rather than at wall-clock now.
        "replay": True,
        # 2026-08-20: a real random UUID, not a caller-supplied sequence number.
        # Used to be `f"player-{idmessage_seq}"`, a per-call-site counter that
        # restarted at 1 for every fresh PlayerExportSource instance - harmless
        # while idMessage was purely cosmetic/unused downstream (see below), but
        # dangerous once denidin.py's new RecentNotificationDeduper (fa5c974,
        # keyed on idMessage, 10-minute TTL) started actively suppressing repeat
        # idMessage values before any handler runs: _dispatch_with_clarification_loop
        # constructs a fresh single-message PlayerExportSource for the original
        # dispatch AND every clarification follow-up round, so every one of them
        # got idMessage="player-1" - collapsing an entire player run to roughly
        # one real dispatch per 10-minute window, silently. A UUID is guaranteed-
        # unique per call with no bookkeeping required, which is what actually
        # matters now that idMessage is a real dedup key, not cosmetic filler.
        #
        # Deferred design note (2026-08-20, human decision - not implemented
        # here): ParsedMessage.raw_line_no (export_parser.py) is the real,
        # meaningful position of this message in its source conversation - in
        # principle THAT, not SessionManager's own session-relative
        # message_counter, should drive the persisted Message.order_num
        # (session_manager.py) for a player-replayed message, so a replayed
        # session's ordering stays traceable back to the original export. Not
        # done now - would need SessionManager.add_message to accept an
        # optional order_num override, a bigger change than this fix.
        "idMessage": f"player-{uuid.uuid4()}",
        "instanceData": {"idInstance": 0, "wid": chat_id, "typeInstance": "whatsapp"},
        "senderData": sender_data,
    }

    if not msg.attachments:
        base_event["messageData"] = {
            "typeMessage": "textMessage",
            "textMessageData": {"textMessage": msg.text},
        }
        return base_event, "textMessage"

    # Per spec.md's Scope: only the first attachment of a message is played -
    # export_parser.py already keeps a multi-image burst as separate
    # ParsedMessages (never multiple attachments on one), so this is always
    # exactly one in practice; documented here rather than silently ignoring
    # extras if that assumption is ever violated.
    attachment_path = msg.attachments[0]
    ext = attachment_path.suffix.lower().lstrip('.')

    if ext in _IMAGE_EXTENSIONS:
        type_message = "imageMessage"
    elif ext in _DOCUMENT_EXTENSIONS:
        type_message = "documentMessage"
    else:
        return None

    if media_base_url is None:
        raise ValueError(
            f"media_base_url is required to synthesize a {type_message} notification "
            f"for {attachment_path.name!r} - the player's LocalMediaServer must be "
            f"running before any media message is played"
        )

    base_event["messageData"] = {
        "typeMessage": type_message,
        "fileMessageData": {
            "downloadUrl": f"{media_base_url}/{attachment_path.name}",
            "fileName": attachment_path.name,
            "mimeType": _guess_mime_type(attachment_path.name),
            "caption": msg.text,
        },
    }
    return base_event, type_message
