"""Shared helpers for Backbone tests.

make_backbone (REQ-063-08): the Backbone takes the DeniDin object and reads everything
through it - so tests build a DeniDin with the same real objects initialize_app builds
(denidin.build_denidin_objects), on a throwaway data root, and replace whichever ones
the test cares about. Long-term memory is off unless the test passes its own
memory_manager.
"""
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from src.backbone.backbone import Backbone
from src.models.config import AppConfiguration
from tests.denidin_test_support import make_app_denidin, make_session_manager, with_storage

__all__ = ["FakeBot", "make_backbone", "make_session_manager"]


class FakeBot:
    """The Green API bot's sending side (the external boundary): records every plain message
    (`sent`) and every approval-buttons message (`buttons`), accepts all of them. Set it as
    `backbone.denidin.green_api_bot` so the model's sends go out through the real DeniDin and
    WhatsAppHandler. `sent_texts` is every text that reached the user, in order."""

    def __init__(self) -> None:
        self.sent: list = []
        self.buttons: list = []
        # Feature 102: every uploaded file as (chat_id, file_name, content bytes read at upload time - the
        # temp file is deleted right after), and `events` - everything sent, in order, as ("text", text) /
        # ("buttons", body) / ("file", file_name).
        self.files: list = []
        self.events: list = []
        self.file_error: Any = None  # an exception to raise from sendFileByUpload
        self.api = SimpleNamespace(sending=SimpleNamespace(
            sendMessage=self._send_message, sendInteractiveButtons=self._send_buttons,
            sendFileByUpload=self._send_file_by_upload))

    def _send_message(self, chat_id: str, text: str, *args: Any) -> Any:
        self.sent.append((chat_id, text))
        self.events.append(("text", text))
        return SimpleNamespace(code=200, data={"idMessage": f"SENT{len(self.sent)}"})

    def _send_buttons(self, chat_id: str, body: str, buttons: Any, header: Any, footer: Any) -> Any:
        self.buttons.append((chat_id, body, buttons))
        self.events.append(("buttons", body))
        return SimpleNamespace(code=200, data={"idMessage": f"BTN{len(self.buttons)}"})

    def _send_file_by_upload(self, chat_id: str, path: str, fileName: str = "", caption: str = "") -> Any:
        if self.file_error is not None:
            raise self.file_error
        with open(path, "rb") as handle:
            self.files.append((chat_id, fileName, handle.read()))
        self.events.append(("file", fileName))
        return SimpleNamespace(code=200, data={"idMessage": f"FILE{len(self.files)}"})

    @property
    def sent_texts(self) -> list:
        return [text for _chat, text in self.sent] + [body for _chat, body, _buttons in self.buttons]


def make_backbone(ai_client: Any, config: AppConfiguration, *, backbone_class: type = Backbone,
                  **overrides: Any) -> Backbone:
    """A Backbone (or `backbone_class`, a Backbone subclass) on a DeniDin holding real
    objects built on a throwaway data root; `overrides` replace any of them (e.g.
    session_manager=..., telemetry_manager=...). The DeniDin is `backbone.denidin`."""
    data_root = Path(tempfile.mkdtemp(prefix="backbone_data_"))
    app = make_app_denidin(ai_client, with_storage(config, data_root, longterm_enabled=False), **overrides)
    app.ai_manager = backbone_class(app)
    return app.ai_manager
