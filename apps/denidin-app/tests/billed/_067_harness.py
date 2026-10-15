"""Shared harness for the Feature 067 acceptance tests (billed + expensive).

Drives the real path a webhook takes after the poller has stored and acknowledged it: a notification is
prepared and submitted to the IntakeCoordinator exactly as DeniDinGreenAPIBot does, and a real
DeniDinDispatcher thread hands it to denidin.dispatch_notification. Only the WhatsApp send boundary is
the usual test notification stub (create_real_notification). Nothing here is mocked.
"""
import json
import logging
import re
import time
import uuid
from contextlib import contextmanager
from typing import Callable, Dict, List

from src.intake.denidin_dispatcher import DeniDinDispatcher
from src.intake.intake_coordinator import IntakeCoordinator
from src.utils.time_utils import now_local
from tests.e2e_helpers import create_real_notification, get_response

__all__ = ["IntakeRig", "WireCapture", "intake_rig"]


class WireCapture(logging.Handler):
    """Records what crossed the app's wire boundaries (the INFO wire-audit lines), so a test can
    assert on exactly what each call carried and did. Nothing is mocked: it only listens to the app's own log.

    - `calls`: every request sent to the model, `{"context", "input"}`.
    - `vision_calls`: every vision request (media analysis).
    - `morning_calls`: every Morning MCP call the model's responses reported, `{"name", "error"}`.
      Unlike `denidin_app.last_response.mcp_calls` (only the LAST handle_message call's), this spans
      the whole scenario - use it for "exactly one document was created"."""

    def __init__(self):
        super().__init__(level=logging.INFO)
        self.calls = []
        self.vision_calls = []
        self.morning_calls = []

    def emit(self, record):
        text = record.getMessage()
        if not text.startswith("[WIRE-AUDIT]"):
            return
        boundary = re.search(r"boundary='([^']*)'", text)
        direction = re.search(r"direction='([^']*)'", text)
        if not boundary or not direction or "{" not in text:
            return
        context = re.search(r"context='([^']*)'", text)
        try:
            payload = json.loads(text[text.index("{", text.index("context=")):])
        except ValueError:
            return
        boundary, direction = boundary.group(1), direction.group(1)
        if boundary == "openai" and direction == "out":
            self.calls.append({"context": context.group(1) if context else "", "input": payload.get("input", [])})
        elif boundary == "vision" and direction == "out":
            self.vision_calls.append(payload)
        elif boundary == "openai" and direction == "in":
            for item in payload.get("output") or []:
                if isinstance(item, dict) and item.get("type") == "mcp_call":
                    self.morning_calls.append({"name": item.get("name", ""), "error": item.get("error")})

    def created_documents(self):
        """Morning `create_*` calls that succeeded, over the whole scenario."""
        return [c for c in self.morning_calls if c["name"].startswith("create_") and not c["error"]]

    def conversation_calls(self):
        return [c for c in self.calls if c["context"].startswith("conversation")]

    @staticmethod
    def user_texts(call):
        """The user-message texts in one call's input, with the [HH:MM:SS dd/mm] stamp, the
        hand-back header and (in a group) the [Sender] tag removed."""
        out = []
        for item in call["input"]:
            if isinstance(item, dict) and item.get("role") == "user" and isinstance(item.get("content"), str):
                # [11:55:07 13/10] or [USER MESSAGE · ...], then in a group the sender tag [Bina]
                text = re.sub(r"^(\[[^\]]*\]\s*){1,2}", "", item["content"])
                out.append(text.strip())
        return out



class IntakeRig:
    def __init__(self, app, chat_id: str, sender: str = None, sender_name: str = "E2E Godfather"):
        self.app, self.chat_id = app, chat_id
        self.sender = sender or chat_id
        self.sender_name = sender_name
        self.notifications: List = []
        self.wire = WireCapture()
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

    def pause(self, seconds: float = 1.0) -> None:
        """Wait between a user's messages (a real person does not send them in the same instant)."""
        time.sleep(seconds)

    # -- what the test observes -------------------------------------------
    def wait_until_idle(self, timeout: float = 240.0) -> None:
        """Everything submitted has been dispatched and finished (3 consecutive quiet polls)."""
        deadline, quiet = time.time() + timeout, 0
        while time.time() < deadline:
            busy = (any(q.size() for q in self.intake.queues()) or self.intake.deferred
                    or getattr(self.intake, "_current", None) is not None)
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


def _wipe(app, chat_id: str) -> None:
    """A clean conversation for the scenario: no history from an earlier run or test."""
    from tests.e2e_helpers import wipe_chat_messages_on_disk
    wipe_chat_messages_on_disk(app.session_manager.storage_dir, chat_id)


@contextmanager
def intake_rig(app, chat_id: str, **kwargs):
    rig = IntakeRig(app, chat_id, **kwargs)
    wire_logger = logging.getLogger("src.utils.wire_log")
    previous_level = wire_logger.level
    wire_logger.setLevel(min(previous_level or logging.INFO, logging.INFO))
    wire_logger.addHandler(rig.wire)
    _wipe(app, chat_id)
    rig.dispatcher.start()
    try:
        yield rig
    finally:
        rig.dispatcher.stop()
        _wipe(app, chat_id)
        wire_logger.removeHandler(rig.wire)
        wire_logger.setLevel(previous_level)
        app.intake = None
