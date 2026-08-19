"""
Unit tests for denidin.py's handler-dispatch table (Feature 043, tasks.md T004a).

Written BEFORE the denidin.py refactor, per TDD workflow (METHODOLOGY.md SS VI).
Locks down that the new HANDLER_REGISTRY dict + dispatch_notification() function
route every message type EXACTLY the way the pre-refactor `@bot.router.message(...)`
decorators did - a completeness check against the real, pre-existing handler list,
not a guess. Also regression-tests research.md R3's fix: importing denidin no longer
constructs any live Green API bot/MessageSource as a side effect.

See specs/in-progress/043-production-data-setup-tooling/contracts/message-source.md.
"""
from types import SimpleNamespace

import denidin as denidin_module


class TestHandlerRegistryCompleteness:
    """One assertion per message type denidin.py handled before this refactor -
    covers every @bot.router.message(...) decorator that existed pre-043."""

    def test_text_message_types_route_to_handle_text_message(self):
        assert denidin_module.HANDLER_REGISTRY["textMessage"] is denidin_module.handle_text_message
        assert denidin_module.HANDLER_REGISTRY["extendedTextMessage"] is denidin_module.handle_text_message

    def test_contact_message_routes_to_handle_contact_message(self):
        assert denidin_module.HANDLER_REGISTRY["contactMessage"] is denidin_module.handle_contact_message

    def test_contacts_array_message_routes_to_handle_contacts_array_message(self):
        assert (denidin_module.HANDLER_REGISTRY["contactsArrayMessage"]
                is denidin_module.handle_contacts_array_message)

    def test_image_message_routes_to_handle_image_message(self):
        assert denidin_module.HANDLER_REGISTRY["imageMessage"] is denidin_module.handle_image_message

    def test_document_message_routes_to_handle_document_message(self):
        assert denidin_module.HANDLER_REGISTRY["documentMessage"] is denidin_module.handle_document_message

    def test_video_message_routes_to_handle_video_message(self):
        assert denidin_module.HANDLER_REGISTRY["videoMessage"] is denidin_module.handle_video_message

    def test_audio_message_routes_to_handle_audio_message(self):
        assert denidin_module.HANDLER_REGISTRY["audioMessage"] is denidin_module.handle_audio_message

    def test_registry_contains_exactly_these_eight_types_no_more_no_less(self):
        assert set(denidin_module.HANDLER_REGISTRY.keys()) == {
            "textMessage", "extendedTextMessage", "contactMessage",
            "contactsArrayMessage", "imageMessage", "documentMessage",
            "videoMessage", "audioMessage",
        }

    def test_catch_all_handler_is_handle_unsupported_message_default(self):
        assert denidin_module.CATCH_ALL_HANDLER is denidin_module.handle_unsupported_message_default


class TestDispatchNotification:
    def test_dispatches_known_type_to_its_registered_handler(self, monkeypatch):
        calls = []
        monkeypatch.setitem(denidin_module.HANDLER_REGISTRY, "textMessage", lambda n: calls.append(n))

        fake_notification = object()
        denidin_module.dispatch_notification("textMessage", fake_notification)

        assert calls == [fake_notification]

    def test_dispatches_unknown_type_to_catch_all(self, monkeypatch):
        calls = []
        monkeypatch.setattr(denidin_module, "CATCH_ALL_HANDLER", lambda n: calls.append(n))

        fake_notification = object()
        denidin_module.dispatch_notification("someBrandNewMessageType", fake_notification)

        assert calls == [fake_notification]


class TestRecentNotificationDeduper:
    """2026-08-20: real dev incident - Green API redelivered an identical
    incomingMessageReceived notification (same idMessage/timestamp) ~32s
    after the original, landing mid an active reminder approval and being
    misread as a decline + fresh request, producing two approval prompts
    for one real user message. See RecentNotificationDeduper's own
    docstring in denidin.py for the full incident."""

    def test_first_sighting_returns_false(self):
        deduper = denidin_module.RecentNotificationDeduper()
        assert deduper.seen_recently("msg-1") is False

    def test_same_id_seen_again_within_ttl_returns_true(self):
        deduper = denidin_module.RecentNotificationDeduper()
        deduper.seen_recently("msg-1")
        assert deduper.seen_recently("msg-1") is True

    def test_different_ids_are_independent(self):
        deduper = denidin_module.RecentNotificationDeduper()
        assert deduper.seen_recently("msg-1") is False
        assert deduper.seen_recently("msg-2") is False
        assert deduper.seen_recently("msg-1") is True

    def test_entry_still_dedups_within_ttl(self, monkeypatch):
        fake_time = [1000.0]
        monkeypatch.setattr(denidin_module.time, "monotonic", lambda: fake_time[0])
        deduper = denidin_module.RecentNotificationDeduper(ttl_seconds=60.0)
        assert deduper.seen_recently("msg-1") is False
        fake_time[0] += 30.0  # still within the 60s TTL
        assert deduper.seen_recently("msg-1") is True

    def test_entry_expires_after_ttl(self, monkeypatch):
        fake_time = [1000.0]
        monkeypatch.setattr(denidin_module.time, "monotonic", lambda: fake_time[0])
        deduper = denidin_module.RecentNotificationDeduper(ttl_seconds=60.0)
        assert deduper.seen_recently("msg-1") is False
        fake_time[0] += 61.0  # past the 60s TTL
        assert deduper.seen_recently("msg-1") is False, "expired entries must be treated as new again"


class TestDispatchNotificationDeduplication:
    """dispatch_notification itself, not just the deduper class in isolation -
    proves duplicate idMessage notifications never reach a real handler."""

    def test_duplicate_id_message_is_not_dispatched_twice(self, monkeypatch):
        calls = []
        monkeypatch.setitem(denidin_module.HANDLER_REGISTRY, "textMessage", lambda n: calls.append(n))
        monkeypatch.setattr(denidin_module, "_recent_notifications", denidin_module.RecentNotificationDeduper())

        notification = SimpleNamespace(event={"idMessage": "dup-1"})
        denidin_module.dispatch_notification("textMessage", notification)
        denidin_module.dispatch_notification("textMessage", notification)

        assert len(calls) == 1, "the second, duplicate notification must not reach the handler"

    def test_different_id_messages_both_dispatch(self, monkeypatch):
        calls = []
        monkeypatch.setitem(denidin_module.HANDLER_REGISTRY, "textMessage", lambda n: calls.append(n))
        monkeypatch.setattr(denidin_module, "_recent_notifications", denidin_module.RecentNotificationDeduper())

        denidin_module.dispatch_notification("textMessage", SimpleNamespace(event={"idMessage": "a"}))
        denidin_module.dispatch_notification("textMessage", SimpleNamespace(event={"idMessage": "b"}))

        assert len(calls) == 2

    def test_notification_without_event_attribute_is_never_deduped(self, monkeypatch):
        """Matches the existing bare object() fake_notification pattern used
        elsewhere in this file - a notification with no .event at all (or no
        idMessage key) must dispatch normally every time, never crash and
        never be silently dropped."""
        calls = []
        monkeypatch.setitem(denidin_module.HANDLER_REGISTRY, "textMessage", lambda n: calls.append(n))
        monkeypatch.setattr(denidin_module, "_recent_notifications", denidin_module.RecentNotificationDeduper())

        fake_notification = object()
        denidin_module.dispatch_notification("textMessage", fake_notification)
        denidin_module.dispatch_notification("textMessage", fake_notification)

        assert len(calls) == 2

    def test_duplicate_button_tap_is_not_dispatched_twice(self, monkeypatch):
        calls = []
        monkeypatch.setattr(denidin_module, "handle_button_tap", lambda n: calls.append(n))
        monkeypatch.setattr(denidin_module, "_recent_notifications", denidin_module.RecentNotificationDeduper())

        notification = SimpleNamespace(event={"idMessage": "btn-dup-1"})
        denidin_module.dispatch_notification("interactiveButtonsResponse", notification)
        denidin_module.dispatch_notification("interactiveButtonsResponse", notification)

        assert len(calls) == 1


class TestImportDoesNotTouchGreenAPI:
    def test_module_has_no_live_bot_attribute(self):
        """Regression test for research.md R3: denidin.py must never construct
        a live Green API bot as a bare-import side effect. The strongest
        available signal without actually re-importing the module fresh (which
        pytest's own import caching makes awkward to do safely mid-suite) is
        that there is no module-level `bot` attribute at all anymore - the
        live bot only ever exists inside a GreenAPIMessageSource instance,
        constructed explicitly by the __main__ entry point."""
        assert not hasattr(denidin_module, "bot")
