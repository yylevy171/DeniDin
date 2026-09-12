#!/usr/bin/env python3
"""
Feature 084 (WhatsApp reactions) - T012's expensive-tier scenario driver: runs one
named scenario from tests/expensive/reaction_judgment_pool.py through the REAL
AIHandler/denidin.py pipeline (real vision/document extraction, real OpenAI calls),
with send_reaction stubbed at the Green API boundary only, and appends one entry per
scenario to logs/reaction_tuning/<round_timestamp>.json.

Not a pytest test - a plain script, invoked directly, same idiom as
scripts/run_reaction_scenario.py (the billed-tier driver). Every invocation of this
script is itself the "real vision call" CLAUDE.md's expensive-test rules gate on - only
run this with the user's own fresh, explicit go-ahead for that specific round.

    venv/bin/python3 scripts/run_reaction_scenario_expensive.py <round_timestamp> <scenario_name> [...]

The pool's scenario `document_path` values are illustrative filenames from the spec,
not real files on disk - _FIXTURE_MAP below substitutes the closest real fixture
already used by tests/expensive/*.py (tests/fixtures/media/), noted honestly rather
than fabricating placeholder documents.
"""
import sys
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import unquote

APP_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_ROOT))

from src.models.config import AppConfiguration  # noqa: E402
from tests._reaction_capture import ReactionCaptureStub, ReactionTuningJudgmentLog  # noqa: E402
from tests.expensive.reaction_judgment_pool import EXPENSIVE_REACTION_SCENARIOS  # noqa: E402
from tests.e2e_helpers import create_real_notification  # noqa: E402

# Real fixture substitutions for the pool's illustrative document_path names (none of
# these literal filenames exist on disk - the pool file itself says so).
_FIXTURE_MAP = {
    "fee_agreement_clean.pdf": "contract_peter_adam.pdf",  # a clean, resolvable-client agreement
    "fee_agreement_missing_client.pdf": "document_no_client.pdf",  # genuinely missing a client name
    "garbled_scan.jpg": "ledger_events/not_an_agreement_personal_note.jpg",  # closest available "doesn't
    # resolve cleanly" substitute - NOT literally garbled/unreadable, honestly noted in tuning_log.md
    "receipt_photo.jpg": "receipt_cafe.jpg",
}

_HTTP_PORT = 8767

_MIME_TYPES = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _find_scenario(name):
    for scenario in EXPENSIVE_REACTION_SCENARIOS:
        if scenario["name"] == name:
            return scenario
    raise KeyError(f"no such scenario in EXPENSIVE_REACTION_SCENARIOS: {name!r}")


def _start_fixture_server():
    fixtures_dir = APP_ROOT / "tests" / "fixtures" / "media"

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(fixtures_dir), **kwargs)

        def translate_path(self, path):
            return super().translate_path(unquote(path))

        def log_message(self, fmt, *args):  # pylint: disable=redefined-builtin
            pass

    server = HTTPServer(('127.0.0.1', _HTTP_PORT), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def _boot_denidin_app():
    import denidin

    config_path = APP_ROOT / "config" / "config.test.json"
    config = AppConfiguration.from_file(str(config_path))
    config.validate()
    test_data_root = APP_ROOT / "test_data" / "reaction_tuning_manual_run_expensive"
    config.data_root = str(test_data_root)
    config.memory['session']['storage_dir'] = str(test_data_root / "sessions")
    config.memory['longterm']['storage_dir'] = str(test_data_root / "memory")

    config_dict = {
        'green_api_instance_id': config.green_api_instance_id,
        'green_api_token': config.green_api_token,
        'ai_api_key': config.ai_api_key,
        'ai_model': config.ai_model,
        'ai_reply_max_tokens': config.ai_reply_max_tokens,
        'log_level': config.log_level,
        'data_root': config.data_root,
        'feature_flags': config.feature_flags,
        'godfather_phone': config.godfather_phone,
        'memory': config.memory,
        'constitution_config': config.constitution_config,
        'user_roles': config.user_roles,
    }
    app = denidin.initialize_app(config_dict)
    denidin.denidin_app = app
    app.green_api_bot = object()  # see run_reaction_scenario.py's own comment
    app.ai_handler.green_api_bot = app.green_api_bot
    return app


def _send_document(chat_id, id_message, filename, doc_type):
    import denidin

    type_message = "imageMessage" if doc_type == "image" else "documentMessage"
    notification = create_real_notification({
        'typeWebhook': 'incomingMessageReceived',
        'timestamp': 1706601234,
        'idMessage': id_message,
        'instanceData': {'idInstance': 7103000000, 'wid': '972501234567@c.us', 'typeInstance': 'whatsapp'},
        'senderData': {'chatId': chat_id, 'sender': chat_id, 'senderName': 'Test User'},
        'messageData': {
            'typeMessage': type_message,
            'fileMessageData': {
                'downloadUrl': f'http://127.0.0.1:{_HTTP_PORT}/{filename}',
                'fileName': Path(filename).name,
                # BUG FIX (found during the 2026-09-12 expensive tuning session, Round 3):
                # whatsapp_handler.py reads mimeType (defaulting to '' if absent), which
                # produced a "data:;base64,..." URL with no MIME type - the OpenAI vision
                # call then failed with a real 400 Bad Request on both raw-image scenarios,
                # and MediaHandler's error-fallback text was mistaken for a real (constant,
                # unchanging) model judgment across multiple tuning rounds. PDF scenarios
                # were unaffected (PDFExtractor converts pages to PNG itself, bypassing this
                # lookup entirely) - only the two raw-JPG scenarios were corrupted.
                'mimeType': _MIME_TYPES.get(Path(filename).suffix.lower(), ''),
            },
        },
    })
    denidin.dispatch_notification(type_message, notification)
    return notification._test_sent_messages[0] if notification._test_sent_messages else None


def _send_text(chat_id, id_message, text):
    import denidin

    notification = create_real_notification({
        'typeWebhook': 'incomingMessageReceived',
        'timestamp': 1706601234,
        'idMessage': id_message,
        'instanceData': {'idInstance': 7103000000, 'wid': '972501234567@c.us', 'typeInstance': 'whatsapp'},
        'senderData': {'chatId': chat_id, 'sender': chat_id, 'senderName': 'Test User'},
        'messageData': {'typeMessage': 'textMessage', 'textMessageData': {'textMessage': text}},
    })
    denidin.dispatch_notification("textMessage", notification)
    return notification._test_sent_messages[0] if notification._test_sent_messages else None


def run_scenario(scenario, seq):
    illustrative_name = Path(scenario["document_path"]).name
    real_filename = _FIXTURE_MAP.get(illustrative_name, illustrative_name)
    stub = ReactionCaptureStub()
    reply_text = None
    with stub.installed():
        reply_text = _send_document(
            scenario["chat_id"], f"MANUAL_EXP_{scenario['name']}_DOC_{seq}",
            real_filename, scenario["document_type"],
        )
        if scenario.get("followup_message"):
            reply_text = _send_text(
                scenario["chat_id"], f"MANUAL_EXP_{scenario['name']}_FOLLOWUP_{seq}",
                scenario["followup_message"],
            )
    return stub.calls, reply_text, real_filename


def main():
    if len(sys.argv) < 3:
        print("usage: run_reaction_scenario_expensive.py <round_timestamp> <scenario_name> [...]",
              file=sys.stderr)
        return 2

    round_timestamp = sys.argv[1]
    scenario_names = sys.argv[2:]

    server = _start_fixture_server()
    try:
        app = _boot_denidin_app()
        del app

        log_dir = APP_ROOT / "logs" / "reaction_tuning"
        log = ReactionTuningJudgmentLog(log_dir, round_timestamp)

        for seq, name in enumerate(scenario_names):
            scenario = _find_scenario(name)
            print(f"--- running expensive scenario: {name} ---")
            calls, reply_text, real_filename = run_scenario(scenario, seq)
            log.append(name, calls, reply_text=reply_text or "")
            print(f"    fixture used: {real_filename}")
            print(f"    reactions: {[(c.source, c.reaction) for c in calls]}")
            print(f"    reply: {(reply_text or '')[:300]!r}")

        print(f"\njudgment log written: {log.path}")
    finally:
        server.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
