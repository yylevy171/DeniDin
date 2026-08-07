"""
Unit tests for the MessageSource abstraction (Feature 043, Phase 2, T003a).

Written BEFORE implementation, per TDD workflow (METHODOLOGY.md §VI). Covers
tasks.md T003a: `MessageSource` is a real ABC, and `GreenAPIMessageSource`
never constructs a live `DeniDinGreenAPIBot` (which drains real pending Green
API notifications as a side effect - src/utils/green_api_bot.py) except
inside its own `start()` call - never at `__init__`/import time.

Per CONSTITUTION SS XVII (no monkey-patching), this uses dependency injection
(an explicit `bot_factory` constructor parameter) to observe/replace bot
construction, rather than patching `DeniDinGreenAPIBot` itself. This is also
exactly the seam `GreenAPIMessageSource` needs for its own real use: the
default `bot_factory` is `DeniDinGreenAPIBot` itself, so production code
passes nothing and gets today's real behavior unchanged.

See specs/in-progress/043-production-data-setup-tooling/contracts/
message-source.md for the interface contract this implements, and
research.md R3 for the incident this design avoids (denidin.py:80
constructing DeniDinGreenAPIBot unconditionally at module import time).
"""
import pytest

from src.sources.message_source import MessageSource
from src.sources.green_api_source import GreenAPIMessageSource


class _FakeRouter:
    """Records every (filters, handler) registration `start()` makes,
    mirroring the real whatsapp_chatbot_python Observer.__call__ signature
    (**filters, no positional/defaulted type_message) exactly - so a test
    can distinguish "no type_message filter at all" (the real catch-all,
    filters == {}) from an explicit type_message=None filter (which the
    real library's Handler.check_event would actually evaluate and fail to
    match - confirmed by reading handler.py directly, not assumed)."""

    def __init__(self):
        self.registrations = []  # list of (filters: dict, handler)

    def message(self, **filters):
        def decorator(handler):
            self.registrations.append((filters, handler))
            return handler
        return decorator


class _FakeBot:
    """Stand-in for DeniDinGreenAPIBot - just enough surface (`.router`,
    `.run_forever()`) for GreenAPIMessageSource.start() to register against
    and then return from, with no network I/O. `run_forever()` is a no-op
    here (real DeniDinGreenAPIBot.run_forever() blocks forever polling Green
    API) so start()'s tests can complete instead of hanging."""

    def __init__(self):
        self.router = _FakeRouter()
        self.on_notification_received = None  # matches DeniDinGreenAPIBot's own default

    def run_forever(self):
        pass


class _BotFactorySpy:
    """Injected in place of the real DeniDinGreenAPIBot constructor. Records
    every call (so a test can assert it was called exactly once, with the
    right args, and only from start() - never from __init__)."""

    def __init__(self):
        self.calls = []
        self.bot = _FakeBot()

    def __call__(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.bot


def _config(instance_id="test-instance", token="test-token"):
    from types import SimpleNamespace
    return SimpleNamespace(green_api_instance_id=instance_id, green_api_token=token)


class TestMessageSourceIsAnAbc:
    def test_cannot_instantiate_directly(self):
        with pytest.raises(TypeError):
            MessageSource()  # abstract - no concrete start() implementation

    def test_subclass_without_start_cannot_instantiate(self):
        class Incomplete(MessageSource):
            pass

        with pytest.raises(TypeError):
            Incomplete()

    def test_subclass_with_start_instantiates_fine(self):
        class Minimal(MessageSource):
            def start(self, dispatch):
                pass

        Minimal()  # no error


class TestGreenAPIMessageSourceConstructionDeferred:
    def test_init_does_not_call_bot_factory(self):
        """The core regression this test guards: constructing a
        GreenAPIMessageSource (which is what a bare module import would do,
        if denidin.py ever built one at module scope) must NOT construct the
        underlying bot - that only happens inside start()."""
        factory = _BotFactorySpy()
        GreenAPIMessageSource(_config(), bot_factory=factory)
        assert factory.calls == []

    def test_importing_the_module_does_not_construct_a_bot(self):
        """Merely importing src.sources.green_api_source must have zero side
        effects on any real Green API client - the module only defines a
        class. (This is a weaker, module-level companion to the __init__
        check above; both matter because the historical bug was specifically
        about *module import* triggering construction.)"""
        import importlib
        import src.sources.green_api_source as green_api_source_module

        importlib.reload(green_api_source_module)  # re-run module body
        # No assertion needed beyond "this didn't raise/hang/touch a real
        # network client" - reaching this line at all is the pass condition,
        # since a real DeniDinGreenAPIBot construction against a fake/unset
        # instance id would raise or hang attempting the startup drain.


class TestGreenAPIMessageSourceConnect:
    def test_connect_calls_bot_factory_once_and_returns_bot(self):
        factory = _BotFactorySpy()
        source = GreenAPIMessageSource(_config(), bot_factory=factory)

        result = source.connect()

        assert len(factory.calls) == 1
        assert result is factory.bot
        assert source.bot is factory.bot

    def test_connect_is_idempotent(self):
        """A second connect() (or start() calling it internally) must NOT
        construct a second bot - that would drain real Green API
        notifications twice, and denidin.py's live entry point is expected
        to call connect() itself before start()."""
        factory = _BotFactorySpy()
        source = GreenAPIMessageSource(_config(), bot_factory=factory)

        first = source.connect()
        second = source.connect()

        assert len(factory.calls) == 1
        assert first is second

    def test_start_reuses_an_already_connected_bot(self):
        factory = _BotFactorySpy()
        source = GreenAPIMessageSource(_config(), bot_factory=factory, message_types=[])

        source.connect()
        source.start(dispatch=lambda type_message, notification: None)

        assert len(factory.calls) == 1


class TestGreenAPIMessageSourceStart:
    def test_start_calls_bot_factory_exactly_once_with_config_credentials(self):
        factory = _BotFactorySpy()
        source = GreenAPIMessageSource(_config("real-instance-id", "real-token"), bot_factory=factory,
                                        message_types=["textMessage"])

        source.start(dispatch=lambda type_message, notification: None)

        assert len(factory.calls) == 1
        args, kwargs = factory.calls[0]
        assert "real-instance-id" in args or kwargs.get("green_api_instance_id") == "real-instance-id"
        assert "real-token" in args or kwargs.get("green_api_token") == "real-token"

    def test_start_registers_every_requested_message_type(self):
        factory = _BotFactorySpy()
        source = GreenAPIMessageSource(
            _config(), bot_factory=factory,
            message_types=["textMessage", "imageMessage", "documentMessage"],
            include_catch_all=False,
        )

        source.start(dispatch=lambda type_message, notification: None)

        registered_types = {filters["type_message"] for filters, _handler in factory.bot.router.registrations}
        assert registered_types == {"textMessage", "imageMessage", "documentMessage"}

    def test_registered_handler_calls_dispatch_with_type_and_notification(self):
        factory = _BotFactorySpy()
        received = []
        source = GreenAPIMessageSource(_config(), bot_factory=factory,
                                        message_types=["textMessage"], include_catch_all=False)

        source.start(dispatch=lambda type_message, notification: received.append((type_message, notification)))

        # Simulate the router firing the registered handler, exactly as
        # whatsapp_chatbot_python would on a real incoming webhook.
        _filters, handler = factory.bot.router.registrations[0]
        fake_notification = object()
        handler(fake_notification)

        assert received == [("textMessage", fake_notification)]

    def test_specific_types_registered_before_catch_all(self):
        """Registration ORDER matters: the real router's Handler list is
        matched first-match-wins (propagate_event iterates self.handlers in
        insertion order) - so specific types must be registered before the
        catch-all, exactly like today's decorator declaration order in
        denidin.py, or a specific type could get swallowed by the catch-all
        instead of its intended handler."""
        factory = _BotFactorySpy()
        source = GreenAPIMessageSource(_config(), bot_factory=factory,
                                        message_types=["textMessage", "imageMessage"])

        source.start(dispatch=lambda type_message, notification: None)

        filters_in_order = [filters for filters, _handler in factory.bot.router.registrations]
        assert filters_in_order[0] == {"type_message": "textMessage"}
        assert filters_in_order[1] == {"type_message": "imageMessage"}
        assert filters_in_order[-1] == {}  # catch-all last, no type_message filter at all

    def test_catch_all_registered_with_zero_filters_not_explicit_none(self):
        """The real regression this guards: the catch-all MUST be
        registered as router.message() with no kwargs at all (filters=={}),
        never router.message(type_message=None) - confirmed by reading
        whatsapp_chatbot_python's Handler.check_event directly: an explicit
        type_message=None entry would be evaluated by the real filter and
        fail to match, silently breaking every unsupported/catch-all
        message type live currently handles via handle_unsupported_message_default."""
        factory = _BotFactorySpy()
        source = GreenAPIMessageSource(_config(), bot_factory=factory,
                                        message_types=[], include_catch_all=True)

        source.start(dispatch=lambda type_message, notification: None)

        assert len(factory.bot.router.registrations) == 1
        filters, _handler = factory.bot.router.registrations[0]
        assert filters == {}
        assert "type_message" not in filters

    def test_is_blocked_defaults_to_none_and_no_hook_is_wired(self):
        """is_blocked is a post-construction attribute (see
        green_api_source.py's docstring for why it can't be a constructor
        param) - defaults to None, matching DeniDinGreenAPIBot.
        on_notification_received's own default-None-means-no-op idiom."""
        factory = _BotFactorySpy()
        source = GreenAPIMessageSource(_config(), bot_factory=factory, message_types=[])

        assert source.is_blocked is None

        source.start(dispatch=lambda type_message, notification: None)

        assert factory.bot.on_notification_received is None

    def test_is_blocked_set_before_start_wires_the_read_receipt_hook(self):
        factory = _BotFactorySpy()
        source = GreenAPIMessageSource(_config(), bot_factory=factory, message_types=[])
        source.is_blocked = lambda chat_id: chat_id == "blocked@c.us"

        source.start(dispatch=lambda type_message, notification: None)

        assert callable(factory.bot.on_notification_received)

    def test_catch_all_handler_extracts_real_type_from_notification(self):
        factory = _BotFactorySpy()
        received = []
        source = GreenAPIMessageSource(_config(), bot_factory=factory,
                                        message_types=[], include_catch_all=True)

        source.start(dispatch=lambda type_message, notification: received.append((type_message, notification)))

        _filters, handler = factory.bot.router.registrations[0]

        class _FakeNotification:
            event = {"messageData": {"typeMessage": "videoMessage"}}

        fake_notification = _FakeNotification()
        handler(fake_notification)

        assert received == [("videoMessage", fake_notification)]
