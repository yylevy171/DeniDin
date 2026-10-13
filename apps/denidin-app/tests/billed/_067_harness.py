"""Shared harness for the Feature 067 acceptance tests (billed + expensive).

Drives the real path a webhook takes after the poller has stored and acknowledged it: a notification is
prepared and submitted to the IntakeCoordinator exactly as DeniDinGreenAPIBot does, and a real
DeniDinDispatcher thread hands it to denidin.dispatch_notification. Only the WhatsApp send boundary is
the usual test notification stub (create_real_notification). Nothing here is mocked.
"""
import time
import uuid
from contextlib import contextmanager
from typing import Callable, Dict, List

from src.intake.denidin_dispatcher import DeniDinDispatcher
from src.intake.intake_coordinator import IntakeCoordinator
from src.utils.time_utils import now_local
from tests.e2e_helpers import create_real_notification, get_response

__all__ = ["IntakeRig", "intake_rig"]


class IntakeRig:
    def __init__(self, app, chat_id: str, sender: str = None, sender_name: str = "E2E Godfather"):
        self.app, self.chat_id = app, chat_id
        self.sender = sender or chat_id
        self.sender_name = sender_name
        self.notifications: List = []
        self.intake = IntakeCoordinator(app)
        app.intake = self.intake
        import denidin
        self.dispatcher = DeniDinDispatcher(self.intake, denidin.dispatch_notification, poll_seconds=0.1)

    # -- what a user does -------------------------------------------------
    def _event(self, type_message: str, body: Dict, sender=None, sender_name=None) -> Dict:
        return {"typeWebhook": "incomingMessageReceived", "idMessage": f"067_{uuid.uuid4().hex[:10]}",
                "timestamp": int(now_local().timestamp()),
                "senderData": {"chatId": self.chat_id, "sender": sender or self.sender,
                               "senderName": sender_name or self.sender_name},
                "messageData": {"typeMessage": type_message, **body}}

    def _submit(self, event: Dict):
        notification = create_real_notification(event)
        self.notifications.append(notification)
        self.intake.submit(self.intake.prepare(notification))
        return notification

    def send_text(self, text: str, **who):
        return self._submit(self._event("textMessage", {"textMessageData": {"textMessage": text}}, **who))

    def send_tap(self, selected_id: str, stanza_id: str):
        return self._submit(self._event("interactiveButtonsResponse", {"interactiveButtonsResponse": {
            "stanzaId": stanza_id, "selectedIndex": 0, "selectedId": selected_id,
            "selectedDisplayText": "כן" if selected_id == "denidin_approve" else "לא"}}))

    def send_image(self, file_name: str, caption: str, download_url: str):
        return self._submit(self._event("imageMessage", {"fileMessageData": {
            "downloadUrl": download_url, "caption": caption, "fileName": file_name,
            "mimeType": "image/jpeg"}}))

    # -- what the test observes -------------------------------------------
    def wait_until_idle(self, timeout: float = 240.0) -> None:
        """Everything submitted has been dispatched and finished (3 consecutive quiet polls)."""
        deadline, quiet = time.time() + timeout, 0
        while time.time() < deadline:
            busy = (any(q.size() for q in self.intake.queues()) or self.intake.deferred
                    or self.app._busy_chats or getattr(self.intake, "_current", None) is not None)
            quiet = 0 if busy else quiet + 1
            if quiet >= 3:
                return
            time.sleep(1.0)
        raise AssertionError("handling did not finish in time")

    def sent_texts(self) -> List[str]:
        return [m for n in self.notifications for m in n._test_sent_messages]

    def last_reply(self) -> str:
        for n in reversed(self.notifications):
            reply = get_response(n)
            if reply:
                return reply
        return ""

    def approval_message_id(self) -> str:
        for n in reversed(self.notifications):
            if n._test_button_sends:
                return n._test_button_sends[-1]["idMessage"]
        return ""

    def stored_user_messages(self) -> List[str]:
        sm = self.app.session_manager
        session = sm.get_session(self.chat_id)
        rows = [m for _mid, m in sm._iter_persisted_messages(session)]
        return [m["content"] for m in rows if (m.get("ai_required_role") or m.get("role")) == "user"]


@contextmanager
def intake_rig(app, chat_id: str, **kwargs):
    rig = IntakeRig(app, chat_id, **kwargs)
    rig.dispatcher.start()
    try:
        yield rig
    finally:
        rig.dispatcher.stop()
        app.intake = None
