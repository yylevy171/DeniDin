"""
PlayerExportSource (Feature 043, tasks.md T012) - the player's own MessageSource.

Takes an already parsed/date-range-filtered/chronologically-sorted list of
ParsedMessage (export_parser.py) and, for each, synthesizes a Green-API-shaped
notification (notification_synth.py) and calls dispatch(type_message,
notification) directly - no live bot, no Green API credentials touched at
any point (research.md R3). start() never blocks: it processes the fixed
list once, in order, and returns.

See contracts/message-source.md for the full interface contract.
"""
from typing import Callable, Dict, List, Optional

from player.export_parser import ParsedMessage
from player.notification_synth import synthesize_notification
from src.sources.message_source import MessageSource


class _PlayerNotification:
    """Minimal stand-in for whatsapp_chatbot_python.Notification - just
    `.event` (read by WhatsAppMessage.from_notification) and `.answer(text)`
    (called by every denidin.py handler to send a reply). The real SDK
    Notification's own `.answer()` would attempt a real Green API call -
    deliberately NOT reused here; this class's `.answer()` only records the
    text for the run summary, exactly the "player" framing (spec.md):
    replayed messages are processed for their ledger-capture side effects,
    never actually sent anywhere."""

    def __init__(self, event: dict):
        self.event = event
        self.last_answer: Optional[str] = None

    def answer(self, text: str) -> None:
        self.last_answer = text


class PlayerExportSource(MessageSource):
    """The player's MessageSource - see this module's docstring."""

    def __init__(
        self,
        messages: List[ParsedMessage],
        chat_id: str,
        sender_map: Dict[str, str],
        media_base_url: Optional[str] = None,
    ):
        self._messages = messages
        self._chat_id = chat_id
        self._sender_map = sender_map
        self._media_base_url = media_base_url
        self.outcomes: List[Dict] = []  # populated during start(), one entry per message

    def start(self, dispatch: Callable[[str, object], None]) -> None:
        for msg in self._messages:
            sender_id = self._sender_map.get(msg.sender_display_name)
            if sender_id is None:
                self.outcomes.append({
                    "status": "unmapped-sender",
                    "raw_line_no": msg.raw_line_no,
                    "sender_display_name": msg.sender_display_name,
                })
                continue

            # 2026-08-20: idMessage is now a real UUID, generated inside
            # synthesize_notification itself - no per-batch sequence number to
            # thread through here anymore (see that function's own docstring
            # for why an enumerate()-based counter was actively dangerous once
            # denidin.py's RecentNotificationDeduper started keying off it).
            result = synthesize_notification(
                msg, chat_id=self._chat_id, sender_id=sender_id,
                media_base_url=self._media_base_url,
            )
            if result is None:
                self.outcomes.append({
                    "status": "unsupported-type",
                    "raw_line_no": msg.raw_line_no,
                    "attachments": [str(p) for p in msg.attachments],
                })
                continue

            event, type_message = result
            notification = _PlayerNotification(event)
            dispatch(type_message, notification)
            self.outcomes.append({
                "status": "dispatched",
                "raw_line_no": msg.raw_line_no,
                "type_message": type_message,
                "timestamp": msg.timestamp.isoformat(),
            })
