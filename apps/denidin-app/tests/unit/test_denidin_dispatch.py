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
