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
player's own source (player/export_source.py) never constructs one.
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
    """The live Green API WhatsApp MessageSource.

    `message_types`/`include_catch_all` are constructor-injected - `start(dispatch)`
    must have the exact same signature as `PlayerExportSource.start(dispatch)` (and
    the abstract `MessageSource.start`), so denidin.py's caller never needs to know
    or care which concrete MessageSource it's holding. `is_blocked` (see below) is
    the one exception, set as a public attribute AFTER construction rather than
    passed to __init__ - not by choice, but because of a real ordering constraint:
    see its own docstring.
    """

    def __init__(self, config, bot_factory: Callable[..., Any] = DeniDinGreenAPIBot,
                 message_types: Optional[List[str]] = None,
                 include_catch_all: bool = True):
        """
        Args:
            message_types: which message types to register `dispatch`
                against; defaults to DEFAULT_MESSAGE_TYPES. denidin.py's
                live entry point is expected to always pass its own real
                dispatch table's key list explicitly instead, so this class
                never needs to be kept in sync with denidin.py's handler
                registrations by hand.
            include_catch_all: when True (the default), also registers one
                final handler with NO type_message filter at all - matching
                denidin.py's existing `@bot.router.message()` catch-all
                exactly. This is NOT the same as registering
                `type_message=None`: the real router's Handler.check_event
                only skips a filter that is genuinely absent from
                self.filters; an explicit `type_message=None` entry would
                instead be checked (and fail to match) - confirmed by
                reading whatsapp_chatbot_python/manager/handler.py
                directly. The catch-all handler receives the notification's
                own real type_message (read from its event data) rather
                than a fixed one, since by definition it doesn't know its
                type_message ahead of registration time.
        """
        self._config = config
        self._bot_factory = bot_factory
        self._message_types = message_types
        self._include_catch_all = include_catch_all
        self.bot: Optional[Any] = None  # constructed only inside connect()/start()

        # Feature 045's read-receipt hook (mark every non-blocked sender's incoming
        # message as read, as early as possible - before route_event dispatches to
        # any handler; see src/utils/green_api_bot.py's mark_message_read/
        # on_notification_received) needs a single is-this-chat-id-blocked
        # predicate - deliberately NOT the whole UserManager, which also does role
        # resolution/token limits/memory scope this class has no business touching.
        # This can't be a constructor param: denidin.py's live entry point must
        # construct this class and call connect() BEFORE `denidin`/its UserManager
        # exist at all (connect() -> initialize_app(green_api=...) -> denidin) - so
        # it's set as a plain public attribute once denidin does exist, same idiom
        # as DeniDinGreenAPIBot.on_notification_received itself (also set
        # post-construction, defaults to None/no-op). `None` (the default) means no
        # read-receipt hook is registered - correct both before it's been set yet,
        # and permanently for the player, which never constructs this class at all.
        self.is_blocked: Optional[Callable[[str], bool]] = None

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

    def start(self, dispatch: Callable[[str, Notification], None]) -> None:
        """Ensures the bot is connected (via `connect()`, a no-op if the
        live entry point already called it), registers `dispatch` against
        every message type from `__init__`'s `message_types` in order
        (specific types first, so the underlying router's first-match-wins
        semantics - confirmed by reading whatsapp_chatbot_python's
        Observer/Handler.check_event directly, not assumed - behave exactly
        like today's decorator order), wires the read-receipt hook if
        `self.is_blocked` was set, then blocks running the bot's listen
        loop. Same signature as `PlayerExportSource.start` - see this
        class's own docstring for why.
        """
        bot = self.connect()  # Any, not Optional - narrows cleanly for mypy below

        # NOTE: `is None`, not truthiness - message_types=[] (explicitly no
        # specific types, e.g. a catch-all-only registration) must NOT fall
        # back to DEFAULT_MESSAGE_TYPES the way `message_types or DEFAULT...`
        # would (an empty list is falsy).
        types = self._message_types if self._message_types is not None else DEFAULT_MESSAGE_TYPES
        for type_message in types:
            self._register(bot, type_message, dispatch)

        if self._include_catch_all:
            self._register_catch_all(bot, dispatch)

        if self.is_blocked is not None:
            bot.on_notification_received = self._build_read_receipt_hook(bot, self.is_blocked)

        bot.run_forever()

    @staticmethod
    def _build_read_receipt_hook(bot: Any, is_blocked: Callable[[str], bool]) -> Callable[[dict], None]:
        """Feature 045: returns the notification-received hook DeniDinGreenAPIBot's
        polling loop calls for every raw notification body, before route_event
        dispatches it to any handler - see mark_message_read's own docstring for why
        this is best-effort/non-fatal."""
        def _on_notification_received(body: dict) -> None:
            chat_id = body.get("senderData", {}).get("chatId", "")
            blocked = bool(chat_id) and is_blocked(chat_id)
            mark_message_read(bot, body, is_blocked=blocked)
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
