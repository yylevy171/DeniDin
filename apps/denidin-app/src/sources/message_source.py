"""
MessageSource - abstract input-listener interface (Feature 043).

Extracted from denidin.py's previously-hardwired Green API coupling
(research.md R3, specs/in-progress/043-production-data-setup-tooling):
denidin.py used to construct a live DeniDinGreenAPIBot unconditionally at
module import time, and every handler function was decorated
`@bot.router.message(...)` at module scope - coupling handler definition to
that live bot object existing. Neither is true anymore: handler functions
are plain, undecorated functions; whichever MessageSource is active supplies
notifications to them via `dispatch`, in whatever order/cadence is natural
to that source.

Two implementations: GreenAPIMessageSource (src/sources/green_api_source.py -
today's live behavior, unchanged, just relocated so it's constructed only
when live listening actually starts) and a player-side source
(player/export_source.py - PlayerExportSource) that replays a parsed
WhatsApp export. Downstream processing (WhatsAppMessage parsing, AIHandler,
MediaHandler, LedgerEventManager) is identical regardless of which source is
active - this interface's only job is producing Notification-shaped objects
whose `.event` dict has the same shape WhatsAppMessage.from_notification
already parses.

See specs/in-progress/043-production-data-setup-tooling/contracts/
message-source.md for the full contract both implementations must honor.
"""
from abc import ABC, abstractmethod
from typing import Callable

from whatsapp_chatbot_python import Notification


class MessageSource(ABC):
    """Supplies Notification-shaped objects to a dispatch callable."""

    @abstractmethod
    def start(self, dispatch: Callable[[str, Notification], None]) -> None:
        """Begin supplying notifications. `dispatch(type_message,
        notification)` is called once per notification, synchronously, in
        the source's natural order. Returns when the source is exhausted
        (a replay/player source) or blocks indefinitely (a live source)."""
        raise NotImplementedError
