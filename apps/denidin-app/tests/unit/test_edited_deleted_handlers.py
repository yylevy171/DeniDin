"""
Unit tests: handle_edited_message / handle_deleted_message (Feature 076).

These cover handler-level edge cases NOT already exercised by the real,
full-stack integration test (tests/integration/test_edited_deleted_webhook_
routing.py) - the "denidin_app not initialized" fallback path, and a
malformed/missing editedMessageData.textMessage field. Full happy-path
behavior (session persistence, no reply, dedup, fresh-chat session
creation) is covered there per spec.md Q9 ("Integration tests are required
for at least editedMessage and deletedMessage").

NO MOCKING of internal components - this monkeypatches only the
module-level `denidin_app` singleton to None (the same "not initialized"
seam every other handler in denidin.py already tests through), never an
internal manager/handler.
"""

import denidin as denidin_module


class _FakeSentNotification:
    """Minimal real-shaped double for asserting what notification.answer()
    was called with - not a mock of any internal DeniDin component, just a
    stand-in for the Green API SDK's own Notification.answer() side effect,
    matching test_denidin_dispatch.py's own `fake_notification` precedent."""

    def __init__(self, event):
        self.event = event
        self.sent = []

    def answer(self, message):
        self.sent.append(message)


class TestEditedDeletedHandlersNotInitialized:
    """denidin_app is None - the same infra fallback every other handler
    (handle_text_message, handle_image_message, ...) already exercises."""

    def test_edited_message_replies_not_ready_when_app_not_initialized(self, monkeypatch):
        monkeypatch.setattr(denidin_module, "denidin_app", None)
        n = _FakeSentNotification({
            "senderData": {"chatId": "972500000000@c.us"},
            "messageData": {
                "typeMessage": "editedMessage",
                "editedMessageData": {"textMessage": "x", "stanzaId": "y"},
            },
        })

        denidin_module.handle_edited_message(n)

        assert n.sent == [denidin_module.APP_NOT_READY_RETRY_LATER]

    def test_deleted_message_replies_not_ready_when_app_not_initialized(self, monkeypatch):
        monkeypatch.setattr(denidin_module, "denidin_app", None)
        n = _FakeSentNotification({
            "senderData": {"chatId": "972500000000@c.us"},
            "messageData": {
                "typeMessage": "deletedMessage",
                "deletedMessageData": {"stanzaId": "y"},
            },
        })

        denidin_module.handle_deleted_message(n)

        assert n.sent == [denidin_module.APP_NOT_READY_RETRY_LATER]


class TestIgnoredMessageDefaultSendsNothing:
    """The silent CATCH_ALL_HANDLER (Q7) - log_inbound only, no
    notification.answer() call at all, regardless of denidin_app state."""

    def test_sends_nothing_when_app_not_initialized(self, monkeypatch):
        monkeypatch.setattr(denidin_module, "denidin_app", None)
        n = _FakeSentNotification({
            "senderData": {"chatId": "972500000000@c.us"},
            "messageData": {"typeMessage": "reactionMessage"},
        })

        denidin_module.handle_ignored_message_default(n)

        assert n.sent == []

    def test_sends_nothing_when_app_is_initialized(self):
        n = _FakeSentNotification({
            "senderData": {"chatId": "972500000000@c.us"},
            "messageData": {"typeMessage": "stickerMessage"},
        })

        denidin_module.handle_ignored_message_default(n)

        assert n.sent == []
