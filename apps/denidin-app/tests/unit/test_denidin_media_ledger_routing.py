"""T024a/C1 (Feature 069, Phase 9): denidin.py `_process_media_message` routes a
recognised media ledger event (`result["ledger_stash"]`) back into the shared
conversational pipeline as a synthetic `textMessage` turn - preserving the
original chat/sender/timestamp - instead of answering with the plain media
summary.

Mocks WhatsAppHandler + `_process_conversational_message` to isolate the routing
decision; the end-to-end path is `tests/integration/
test_ledger_client_resolution_routing.py`.
"""
from unittest.mock import Mock

import pytest
from whatsapp_chatbot_python import Notification

import denidin as denidin_module


def _make_media_notification():
    notification = Notification.__new__(Notification)
    notification.event = {
        'typeWebhook': 'incomingMessageReceived',
        'idMessage': 'MEDIA1',
        'timestamp': 1755331200,
        'senderData': {
            'chatId': '972509999999@c.us',
            'sender': '972509999999@c.us',
            'senderName': 'Godfather',
        },
        'messageData': {
            'typeMessage': 'imageMessage',
            'fileMessageData': {'downloadUrl': 'https://x/y.jpg', 'fileName': 'y.jpg',
                                'mimeType': 'image/jpeg', 'caption': ''},
        },
    }
    notification._test_sent = []
    notification.answer = notification._test_sent.append
    return notification


@pytest.fixture
def app(monkeypatch):
    a = Mock()
    a.green_api_bot = None
    a.ai_handler.user_manager.get_user.return_value = Mock(is_blocked=False)
    monkeypatch.setattr(denidin_module, 'denidin_app', a)
    return a


def test_ledger_stash_result_is_routed_as_synthetic_text_turn(app, monkeypatch):
    app.whatsapp_handler.handle_media_message.return_value = {
        "success": True,
        "ledger_stash": "📸 התקבלה תמונה של אסמכתת העברה/הפקדה בנקאית.\nסכום: 9,440₪",
        "ledger_stash_source_type": "בנק",
    }
    seen = {}

    def _fake_conv(notification):
        seen['event'] = notification.event

    monkeypatch.setattr(denidin_module, '_process_conversational_message', _fake_conv)

    notification = _make_media_notification()
    denidin_module._process_media_message(notification)

    md = seen['event']['messageData']
    assert md['typeMessage'] == 'textMessage'
    assert md['textMessageData']['textMessage'].startswith("📸 התקבלה תמונה")
    assert 'fileMessageData' not in md
    # original routing context preserved for chat id / RBAC / timestamp
    assert seen['event']['senderData']['chatId'] == '972509999999@c.us'
    assert seen['event']['timestamp'] == 1755331200
    assert seen['event']['idMessage'] == 'MEDIA1'


def test_no_ledger_stash_does_not_route_a_synthetic_turn(app, monkeypatch):
    app.whatsapp_handler.handle_media_message.return_value = {"success": True, "summary": "ok"}
    called = []
    monkeypatch.setattr(denidin_module, '_process_conversational_message',
                        lambda n: called.append(n))

    denidin_module._process_media_message(_make_media_notification())

    assert called == []


def test_none_result_is_tolerated(app, monkeypatch):
    app.whatsapp_handler.handle_media_message.return_value = None
    monkeypatch.setattr(denidin_module, '_process_conversational_message',
                        lambda n: (_ for _ in ()).throw(AssertionError("should not route")))

    denidin_module._process_media_message(_make_media_notification())  # no raise
