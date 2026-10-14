"""71-3 (Feature 071, option B: one app-wide 10 MB limit): a PDF over the size limit gets the friendly refusal, and no model call is made.

Entry point: a real documentMessage webhook -> handle_document_message -> download from a local
HTTP server -> extractor. NO MOCKING. "No model call" is proven by configuring an invalid OpenAI key:
any call to the model would fail and replace the reply with an error message instead of the refusal.
"""
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

import pytest

from src.constants.error_messages import FILE_TOO_LARGE_REFUSAL
from src.managers.media_file_manager import MediaFileManager
from src.models.config import AppConfiguration
from tests.e2e_helpers import create_real_notification, get_response

pytestmark = pytest.mark.integration


@pytest.fixture
def served_dir(tmp_path):
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(tmp_path), **kw)

        def log_message(self, *a):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield tmp_path, f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


@pytest.fixture
def app_with_invalid_model_key(tmp_path):
    config_path = Path(__file__).parent.parent.parent / "config" / "config.test.json"
    if not config_path.exists():
        pytest.skip("config.test.json not found")
    config = AppConfiguration.from_file(str(config_path))
    config.validate()
    import denidin

    previous = denidin.denidin_app
    denidin.denidin_app = denidin.initialize_app({
        "green_api_instance_id": config.green_api_instance_id, "green_api_token": config.green_api_token,
        "ai_api_key": "sk-invalid-no-model-call-expected", "ai_model": config.ai_model,
        "ai_vision_model": config.ai_vision_model, "ai_embedding_model": config.ai_embedding_model,
        "ai_reply_max_tokens": config.ai_reply_max_tokens, "log_level": config.log_level,
        "data_root": str(tmp_path / "data"), "feature_flags": config.feature_flags,
        "godfather_phone": config.godfather_phone,
        "memory": {**config.memory, "session": {**config.memory["session"], "storage_dir": str(tmp_path / "data/sessions")},
                   "longterm": {**config.memory["longterm"], "storage_dir": str(tmp_path / "data/memory")}},
        "constitution_config": config.constitution_config, "user_roles": config.user_roles,
    })
    yield config
    denidin.denidin_app = previous


def test_oversize_pdf_gets_the_friendly_refusal(served_dir, app_with_invalid_model_key):
    directory, base_url = served_dir
    (directory / "huge.pdf").write_bytes(b"%PDF-1.4\n" + b"0" * (MediaFileManager.MAX_FILE_SIZE_BYTES + 1024))
    chat = app_with_invalid_model_key.godfather_phone

    notification = create_real_notification({
        "typeWebhook": "incomingMessageReceived", "timestamp": 1706601234, "idMessage": "I071_OVERSIZE",
        "instanceData": {"idInstance": 7103000000, "wid": "972501234567@c.us", "typeInstance": "whatsapp"},
        "senderData": {"chatId": chat, "sender": chat, "senderName": "Test User"},
        "messageData": {"typeMessage": "documentMessage", "fileMessageData": {
            "downloadUrl": f"{base_url}/huge.pdf", "fileName": "huge.pdf", "mimeType": "application/pdf",
            "caption": "", "jpegThumbnail": ""}},
    })
    from denidin import handle_document_message

    handle_document_message(notification)
    reply = get_response(notification)

    assert reply is not None and FILE_TOO_LARGE_REFUSAL in reply, f"expected the friendly refusal, got: {reply!r}"
