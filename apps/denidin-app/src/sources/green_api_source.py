"""
GreenAPIMessageSource - the live WhatsApp/Green API MessageSource (Feature 043).

Wraps today's DeniDinGreenAPIBot construction + router registration
(previously module-level code in denidin.py, executed unconditionally at
`import denidin` - see research.md R3 for the incident this fixes: that
construction drains real pending Green API notifications as a side effect,
which is harmless for the live app itself but was an unnecessary, avoidable
risk for anything else that merely imports denidin.py, e.g. tests or a
future replay tool).

Construction of the real bot is deferred to `start()` via dependency
injection (`bot_factory`, defaulting to the real DeniDinGreenAPIBot - no
behavior change for production, which never passes a custom factory) -
never at `__init__`, and never as a bare module-level side effect. This is
the only MessageSource that ever touches real Green API credentials; the
player's own source (scripts/player/export_source.py) never constructs one.
"""
from typing import Any, Callable, List, Optional

from whatsapp_chatbot_python import Notification

from src.sources.message_source import MessageSource
from src.utils.green_api_bot import DeniDinGreenAPIBot, mark_message_read

# The full set of message types denidin.py's live dispatch table registers
# (see denidin.py's handler functions) - kept here so a caller that doesn't
# care about the exact list can omit `message_types` in start() and still
# get live's real coverage. denidin.py itself is the source of truth for
# which handler a given type routes to; this constant is only "which types
# exist at all," used as start()'s default.
DEFAULT_MESSAGE_TYPES: List[str] = [
    "textMessage",
    "extendedTextMessage",
    "contactMessage",
    "contactsArrayMessage",
    "imageMessage",
    "documentMessage",
    "videoMessage",
    "audioMessage",
]


class GreenAPIMessageSource(MessageSource):
    """The live Green API WhatsApp MessageSource."""

    def __init__(self, config, bot_factory: Callable[..., Any] = DeniDinGreenAPIBot):
        self._config = config
        self._bot_factory = bot_factory
        self.bot: Optional[Any] = None  # constructed only inside connect()/start()

    def connect(self) -> Any:
        """Constructs the real bot (draining pending notifications, today's
        existing behavior - unchanged) if not already connected, and returns
        it. Idempotent: a second call returns the same instance without
        constructing (and draining) a second one.

        Split out from `start()` because denidin.py's live entry point needs
        a real Green API client (`connect().api`) to pass into
        `initialize_app()` (for `_fetch_own_whatsapp_number`/
        `GroupMembershipResolver`) BEFORE the blocking listen loop begins -
        `start()` alone can't serve that need since it doesn't return until
        shutdown.
        """
        if self.bot is None:
            self.bot = self._bot_factory(
                self._config.green_api_instance_id,
                self._config.green_api_token,
            )
        return self.bot

    def start(self, dispatch: Callable[[str, Notification], None],
              message_types: Optional[List[str]] = None,
              include_catch_all: bool = True,
              user_manager: Optional[Any] = None) -> None:
        """Ensures the bot is connected (via `connect()`, a no-op if the
        live entry point already called it), registers `dispatch` against
        every requested message type in order (specific types first, so the
        underlying router's first-match-wins semantics - confirmed by
        reading whatsapp_chatbot_python's Observer/Handler.check_event
        directly, not assumed - behave exactly like today's decorator
        order), then blocks running the bot's listen loop.

        `message_types` defaults to DEFAULT_MESSAGE_TYPES - denidin.py's
        live entry point is expected to always pass its own real dispatch
        table's key list explicitly instead, so this class never needs to
        be kept in sync with denidin.py's handler registrations by hand.

        `include_catch_all`: when True (the default), also registers one
        final handler with NO type_message filter at all - matching
        denidin.py's existing `@bot.router.message()` catch-all exactly.
        This is NOT the same as registering `type_message=None`: the real
        router's Handler.check_event only skips a filter that is genuinely
        absent from self.filters; an explicit `type_message=None` entry
        would instead be checked (and fail to match) - confirmed by reading
        whatsapp_chatbot_python/manager/handler.py directly. The catch-all
        handler receives the notification's own real type_message (read
        from its event data) rather than a fixed one, since by definition
        it doesn't know its type_message ahead of registration time.

        `user_manager`: Feature 045's read-receipt hook (mark every
        non-blocked sender's incoming message as read, as early as
        possible - before route_event dispatches to any handler; see
        src/utils/green_api_bot.py's mark_message_read/
        on_notification_received) needs an is-this-sender-blocked check,
        which needs a UserManager. Wiring this here - rather than in
        denidin.py's initialize_app(), where Feature 045 originally added
        it against a module-level `bot` global - keeps GreenAPIMessageSource
        the sole owner of anything that touches the real bot instance
        (research.md R3); `initialize_app()` never receives the full bot,
        only `green_api` (the `.api` client). `None` (e.g. the player,
        which never calls this method at all) means no read-receipt hook is
        registered - there is no live bot to mark anything read on.
        """
        bot = self.connect()  # Any, not Optional - narrows cleanly for mypy below

        # NOTE: `is None`, not truthiness - message_types=[] (explicitly no
        # specific types, e.g. a catch-all-only registration) must NOT fall
        # back to DEFAULT_MESSAGE_TYPES the way `message_types or DEFAULT...`
        # would (an empty list is falsy).
        for type_message in (message_types if message_types is not None else DEFAULT_MESSAGE_TYPES):
            self._register(bot, type_message, dispatch)

        if include_catch_all:
            self._register_catch_all(bot, dispatch)

        if user_manager is not None:
            bot.on_notification_received = self._build_read_receipt_hook(bot, user_manager)

        bot.run_forever()

    @staticmethod
    def _build_read_receipt_hook(bot: Any, user_manager: Any) -> Callable[[dict], None]:
        """Feature 045: returns the notification-received hook DeniDinGreenAPIBot's
        polling loop calls for every raw notification body, before route_event
        dispatches it to any handler - see mark_message_read's own docstring for why
        this is best-effort/non-fatal."""
        def _on_notification_received(body: dict) -> None:
            chat_id = body.get("senderData", {}).get("chatId", "")
            is_blocked = bool(chat_id) and user_manager.get_user(chat_id).is_blocked
            mark_message_read(bot, body, is_blocked=is_blocked)
        return _on_notification_received

    def _register(self, bot: Any, type_message: str,
                   dispatch: Callable[[str, Notification], None]) -> None:
        @bot.router.message(type_message=type_message)
        def _handler(notification: Notification, _type_message=type_message) -> None:
            dispatch(_type_message, notification)

    def _register_catch_all(self, bot: Any, dispatch: Callable[[str, Notification], None]) -> None:
        @bot.router.message()
        def _handler(notification: Notification) -> None:
            type_message = notification.event.get("messageData", {}).get("typeMessage")
            dispatch(type_message, notification)
