#!/usr/bin/env python3
"""
Feature 084 (WhatsApp reactions) - T012's actual scenario driver: runs one or more
named scenarios from tests/billed/reaction_judgment_pool.py (or, with --expensive,
tests/expensive/reaction_judgment_pool.py) through the REAL AIHandler/denidin.py
pipeline, with send_reaction stubbed at the Green API boundary only
(tests/_reaction_capture.py), and appends one entry per scenario to
logs/reaction_tuning/<round_timestamp>.json.

Not a pytest test (contracts/reaction-judgment-tuning.md: "the tuning loop, performed
by the AI agent, not a human") - a plain script, invoked directly:

    venv/bin/python3 scripts/run_reaction_scenario.py <round_timestamp> <scenario_name> [<scenario_name> ...]

Uses config/config.json (real OpenAI key) + an isolated data_root under test_data/,
same as the billed E2E tests - no production data touched.
"""
import json
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP_ROOT))

from src.models.config import AppConfiguration  # noqa: E402
from tests._reaction_capture import ReactionCaptureStub, ReactionTuningJudgmentLog  # noqa: E402
from tests.billed.reaction_judgment_pool import BILLED_REACTION_SCENARIOS  # noqa: E402
from tests.expensive.reaction_judgment_pool import EXPENSIVE_REACTION_SCENARIOS  # noqa: E402
from tests.e2e_helpers import create_real_notification  # noqa: E402


def _find_scenario(name, expensive):
    pool = EXPENSIVE_REACTION_SCENARIOS if expensive else BILLED_REACTION_SCENARIOS
    for scenario in pool:
        if scenario["name"] == name:
            return scenario
    raise KeyError(f"no such scenario ({'expensive' if expensive else 'billed'} pool): {name!r}")


def _boot_denidin_app():
    import denidin

    config_path = APP_ROOT / "config" / "config.json"
    config = AppConfiguration.from_file(str(config_path))
    config.validate()
    test_data_root = APP_ROOT / "test_data" / "reaction_tuning_manual_run"
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
    # ai_handler.react_to_message needs a non-None bot object to call send_reaction on
    # (only __main__ sets a real one). This manual driver stubs send_reaction() itself
    # (ReactionCaptureStub), so any non-None placeholder is fine here.
    app.green_api_bot = object()
    app.ai_handler.green_api_bot = app.green_api_bot
    return app


def _send_turn(chat_id: str, id_message: str, text: str):
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


def _apply_scenario_role(app, scenario):
    """The pool's chat_id values are made-up test numbers that don't match
    config/config.json's real godfather_phone/admin_phones - so a scenario's
    documented "role" field alone was never actually enforced (a bug found while
    testing the fast-ack constitution fix, 2026-09-12: "godfather"-labeled
    scenarios were silently resolving to CLIENT, so Morning MCP / reminder tools
    were never actually attached, no matter what the constitution said). Point
    UserManager's real role lists at this scenario's own chat_id for the
    duration of this run so its declared role is the role that's actually
    resolved - never mutates config/config.json itself.
    """
    phone = scenario["chat_id"].split("@")[0]
    user_manager = app.ai_handler.user_manager
    role = scenario.get("role")
    if role == "godfather":
        user_manager.godfather_phone = phone
        user_manager._godfather_phone_normalized = phone  # pylint: disable=protected-access
    elif role == "admin":
        user_manager.admin_phones = [phone]
        user_manager._admin_phones_normalized = {phone}  # pylint: disable=protected-access
    elif role == "client":
        # Ensure a fake chat_id that happens to collide with a real
        # godfather/admin/blocked number from a PRIOR scenario's override in
        # the same process doesn't leak into this one.
        if user_manager._godfather_phone_normalized == phone:  # pylint: disable=protected-access
            user_manager.godfather_phone = None
            user_manager._godfather_phone_normalized = None  # pylint: disable=protected-access
        user_manager._admin_phones_normalized.discard(phone)  # pylint: disable=protected-access
    user_manager._user_cache.pop(scenario["chat_id"], None)  # pylint: disable=protected-access


def run_scenario(scenario, seq):
    import denidin

    _apply_scenario_role(denidin.denidin_app, scenario)
    stub = ReactionCaptureStub()
    reply_text = None
    with stub.installed():
        for i, (role, content) in enumerate(scenario["prior_turns"]):
            if role == "user":
                _send_turn(scenario["chat_id"], f"MANUAL_{scenario['name']}_PRIOR_{i}_{seq}", content)
        reply_text = _send_turn(scenario["chat_id"], f"MANUAL_{scenario['name']}_FINAL_{seq}", scenario["message"])
    return stub.calls, reply_text


def main():
    if len(sys.argv) < 3:
        print("usage: run_reaction_scenario.py <round_timestamp> <scenario_name> [...] [--expensive]",
              file=sys.stderr)
        return 2

    args = sys.argv[1:]
    expensive = "--expensive" in args
    if expensive:
        args.remove("--expensive")
    round_timestamp = args[0]
    scenario_names = args[1:]

    app = _boot_denidin_app()
    del app

    log_dir = APP_ROOT / "logs" / "reaction_tuning"
    log = ReactionTuningJudgmentLog(log_dir, round_timestamp)

    for seq, name in enumerate(scenario_names):
        scenario = _find_scenario(name, expensive)
        print(f"--- running scenario: {name} ---")
        calls, reply_text = run_scenario(scenario, seq)
        log.append(name, calls, reply_text=reply_text or "")
        print(f"    reactions: {[(c.source, c.reaction) for c in calls]}")
        print(f"    reply: {(reply_text or '')[:200]!r}")

    print(f"\njudgment log written: {log.path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
