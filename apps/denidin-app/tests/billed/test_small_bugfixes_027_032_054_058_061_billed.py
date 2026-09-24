"""Reproduction tests (one per bug) for the small-bugfixes batch:
bugfix-027, bugfix-032, bugfix-054, bugfix-058. (bugfix-061 is covered by the
existing Feature 069 test test_us2_morning_create_is_captured_synchronously, whose
prompt no longer states VAT.)

Each test asserts the CORRECT behavior described in its spec, so it is RED on
current code and turns GREEN once the bug is fixed. Nothing here has been run
yet - written per Bug-Driven Development ("failing test" step), awaiting human
approval before any fix is designed.

Real webhook -> real OpenAI Responses API -> real Morning MCP server/sandbox
where relevant. NO MOCKING. The one stand-in is bugfix-054's local HTTP fixture
server that speaks Green API's notification-queue protocol (CONSTITUTION §V
permits local HTTP fixture servers; the real DeniDinGreenAPIBot and the real
dispatch path run against it unchanged).

@pytest.mark.billed: real OpenAI billing on every run.
"""
from __future__ import annotations

import copy
import http.server
import json
import re
import threading
import time

import pytest

from src.sources.green_api_source import GreenAPIMessageSource
from src.utils.green_api_bot import DeniDinGreenAPIBot
from tests.billed.denidin_mcp_e2e_helpers import (
    GODFATHER_CHAT_ID,
    _calls_for,
    _is_genuine_document_creation,
    _seed_client,
    _send_turn,
    _send_turn_and_approve,
    build_text_webhook,
    pick_existing_client,
)
from tests.e2e_helpers import create_real_notification, get_response

pytestmark = pytest.mark.billed


# ------------------------------------------------------------------ bugfix-027
# PRECONDITION: a Morning SANDBOX client whose name is stored (as returned by Morning's API) with
# a plain ASCII apostrophe - see the test docstring - added to
# tests/fixtures/morning_sandbox_clients.json (see that file's `note`). Mirrors production
# client "מג'די עטילה" (8 Sep 2026).
_APOSTROPHE_CLIENT_NAME = "כג'די בלבואה"


def test_bugfix_027_client_stored_with_ascii_apostrophe_can_get_a_document(denidin_app):
    """Production 2026-09-08 (chat 12e158e2, "מג'די עטילה"): the client Morning's API returns
    carries an ASCII apostrophe (the bot's own "found client X" sentence and the ledger event
    reconciled from the hand-made Morning document both show U+0027). DeniDin normalises every
    name it searches with to the Hebrew geresh, so the exact lookup document creation requires
    finds nothing - even when the operator types the apostrophe form - although
    resolve_client_name/list_clients do surface the client. The operator confirmed the client
    ~10 times and the invoice was never created. Expected: ask once, approve once ("כן"), and
    the document is created."""
    client = pick_existing_client(name=_APOSTROPHE_CLIENT_NAME)
    assert "'" in client["name"], "precondition: the stored name must contain an ASCII apostrophe"

    text = f"{client['name']} שילם 47 שח היום עבור שכר טרחה כולל מע\"מ. תפיק חשבונית מס קבלה"
    (ask_reply, _), (reply, ai_response) = _send_turn_and_approve(
        GODFATHER_CHAT_ID, text, id_prefix="BF027",
    )

    calls = _calls_for(ai_response, "create_combo_document")
    assert any(_is_genuine_document_creation(c) for c in calls), (
        f"bugfix-027: no combo document was created for the client stored as "
        f"{client['name']!r} after one ask + one approval. Ask reply: {ask_reply!r}; "
        f"approve reply: {reply!r}; mcp_calls={ai_response.mcp_calls if ai_response else None!r}"
    )


# ------------------------------------------------------------------ bugfix-032
def test_bugfix_032_phone_without_leading_zero_is_normalised_not_rejected(denidin_app):
    """`50-822-5928` (9 digits, leading zero dropped) is an unambiguous Israeli
    mobile number. add_client must normalise it to 050-8225928 - not carry it
    through an approval prompt and then reject it as "invalid"."""
    raw_phone = "50-822-5928"
    try:
        client_name, response, ai_response = _seed_client(
            GODFATHER_CHAT_ID, "BF032_ADD_CLIENT", phone=raw_phone,
        )
    except Exception as exc:  # pylint: disable=broad-except
        pytest.fail(
            f"bugfix-032: add_client flow with phone {raw_phone!r} did not complete "
            f"(expected normalisation to 050-8225928): {exc!r}"
        )

    add_calls = _calls_for(ai_response, "add_client")
    assert add_calls and add_calls[0]["error"] is None, (
        f"bugfix-032: add_client did not succeed for phone {raw_phone!r}: "
        f"{ai_response.mcp_calls if ai_response else None!r}; reply={response!r}"
    )

    time.sleep(3)  # Morning search-index lag, same as the sibling add_client test
    details_response, _ = _send_turn(
        chat_id=GODFATHER_CHAT_ID,
        text=f"פרטים על הלקוח {client_name}",
        id_prefix="BF032_VERIFY",
    )
    digits = re.sub(r"\D", "", details_response or "")
    assert "0508225928" in digits, (
        f"bugfix-032: expected the normalised phone 050-8225928 in the details "
        f"reply, got: {details_response!r}"
    )


# ------------------------------------------------------------------ bugfix-054
class _FakeGreenAPIServer(http.server.ThreadingHTTPServer):
    """Local Green API stand-in speaking just the notification-queue protocol:
    receiveNotification (GET) pops the queue, deleteNotification (DELETE) records
    the delete, and any POST (sendMessage, ...) is recorded as an outbound send."""

    daemon_threads = True

    def __init__(self):
        super().__init__(("127.0.0.1", 0), _FakeGreenAPIHandler)
        self.lock = threading.Lock()
        self.queue: list = []
        self.deleted: list = []
        self.sent: list = []

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server_address[1]}"


class _FakeGreenAPIHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):  # silence stderr noise
        pass

    def _reply(self, payload) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        path = self.path.split("?")[0]
        if "/receiveNotification/" in path:
            with self.server.lock:
                item = self.server.queue.pop(0) if self.server.queue else None
            if item is None:
                time.sleep(0.3)  # keep the bot's idle poll loop from spinning hot
            self._reply(item)
        elif "/getSettings/" in path:
            # GreenAPIBot.__init__ reads these three keys before doing anything else.
            self._reply({
                "incomingWebhook": "yes",
                "outgoingMessageWebhook": "yes",
                "outgoingAPIMessageWebhook": "yes",
            })
        else:
            self._reply({})

    def do_DELETE(self):  # noqa: N802
        path = self.path.split("?")[0]
        if "/deleteNotification/" in path:
            with self.server.lock:
                self.server.deleted.append(path.rsplit("/", 1)[-1])
        self._reply({"result": True})

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            payload = json.loads(raw) if raw else {}
        except ValueError:
            payload = {}
        with self.server.lock:
            self.server.sent.append({"path": self.path, "payload": payload})
        self._reply({"idMessage": "FAKE_SENT_ID"})


def test_bugfix_054_message_queued_while_bot_was_down_is_answered_after_startup(
    denidin_app, denidin_config
):
    """A WhatsApp message that reached Green API's queue while the bot was down
    must be dispatched and answered once the bot starts. Today the startup
    drain (DeniDinGreenAPIBot._drain_startup_notifications) deletes every queued
    notification without routing it, so the sender never gets a reply."""
    import denidin

    server = _FakeGreenAPIServer()
    threading.Thread(target=server.serve_forever, daemon=True).start()

    queued_body = build_text_webhook(
        chat_id=GODFATHER_CHAT_ID,
        sender_name="E2E Godfather",
        text="ענה לי במילה אחת בלבד: שלום",
        message_id=f"BF054_QUEUED_{int(time.time())}",
    )
    with server.lock:
        server.queue.append({"receiptId": 1, "body": queued_body})

    def _bot_factory(*_args, **_kwargs):
        return DeniDinGreenAPIBot("1101000001", "fake-token", host=server.url, media=server.url)

    source = GreenAPIMessageSource(denidin_config, bot_factory=_bot_factory)
    threading.Thread(
        target=source.start, args=(denidin.dispatch_notification,), daemon=True,
    ).start()

    deadline = time.time() + 90
    replies: list = []
    while time.time() < deadline:
        with server.lock:
            replies = [s for s in server.sent if s["payload"].get("chatId") == GODFATHER_CHAT_ID]
            deleted = list(server.deleted)
        if replies:
            break
        time.sleep(1)

    assert replies, (
        f"bugfix-054: the message queued before startup was never answered. "
        f"notifications deleted by the bot without routing: {deleted!r}; "
        f"all outbound sends: {server.sent!r}"
    )


# ------------------------------------------------------------------ bugfix-058
def test_bugfix_058_error_reply_sent_to_user_is_persisted_in_session(
    denidin_config, tmp_path
):
    """When the OpenAI call fails and the user gets the fallback error message,
    that exact message must be recorded in the chat's session history. Failure
    is produced for real: an app configured with an invalid OpenAI API key."""
    import denidin

    memory = copy.deepcopy(denidin_config.memory)
    memory["session"]["storage_dir"] = str(tmp_path / "sessions")
    memory["longterm"]["storage_dir"] = str(tmp_path / "memory")
    config_dict = {
        "green_api_instance_id": denidin_config.green_api_instance_id,
        "green_api_token": denidin_config.green_api_token,
        "ai_api_key": "sk-" + "invalid" * 8,
        "ai_model": denidin_config.ai_model,
        "ai_vision_model": denidin_config.ai_vision_model,
        "ai_embedding_model": denidin_config.ai_embedding_model,
        "ai_reply_max_tokens": denidin_config.ai_reply_max_tokens,
        "log_level": denidin_config.log_level,
        "data_root": str(tmp_path),
        "feature_flags": denidin_config.feature_flags,
        "godfather_phone": denidin_config.godfather_phone,
        "memory": memory,
        "constitution_config": denidin_config.constitution_config,
        "user_roles": denidin_config.user_roles,
        "mcp": denidin_config.mcp,
    }

    original_app = getattr(denidin, "denidin_app", None)
    try:
        broken_app = denidin.initialize_app(config_dict)
        denidin.denidin_app = broken_app
        if broken_app.green_api_bot is None:
            broken_app.green_api_bot = object()
        broken_app.ai_handler.green_api_bot = broken_app.green_api_bot

        notification = create_real_notification(build_text_webhook(
            chat_id=GODFATHER_CHAT_ID,
            sender_name="E2E Godfather",
            text="שלום, מה שלומך?",
            message_id=f"BF058_{int(time.time())}",
        ))
        denidin.handle_text_message(notification)
        reply = get_response(notification)

        assert reply, "the user received no message at all (expected the fallback error text)"
        window = broken_app.ai_handler.session_manager.get_rolling_window(GODFATHER_CHAT_ID)
        persisted = json.dumps(window, ensure_ascii=False)
        assert reply in persisted, (
            f"bugfix-058: the error message the user saw was not persisted in the "
            f"session. user saw: {reply!r}; session window: {persisted!r}"
        )
    finally:
        denidin.denidin_app = original_app
