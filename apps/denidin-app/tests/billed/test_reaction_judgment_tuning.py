"""
Feature 084 (WhatsApp reactions) - real billed run of the reaction-judgment-tuning
harness's two permitted hard-assertion categories (contracts/reaction-judgment-tuning.md):

  (a) zero `send_reaction` calls for the two ambient-group scenarios
      (`ambient_group_chatter_lunch`, `ambient_group_chatter_debate`)
  (b) flip-targeting correctness for `react_flip_earlier_message` - the second
      `send_reaction` call's `id_message` must match the first's

No assertion anywhere asserts on emoji choice itself - that's the AI-run tuning loop's
job (T012), not a test's. `send_reaction` is stubbed at the Green API boundary only
(tests/_reaction_capture.py) - everything else (AIHandler, tool dispatch, session
persistence) runs for real, exactly like every other billed E2E test. (The deterministic
non-AI fast-path hook this docstring used to also mention was removed 2026-09-12, per
explicit user instruction - the fast ack is now produced by the model itself, as its own
first tool call, same as the resolution reaction.)

(c) `TestAgreementCreationReactionsBilled` below (added 2026-09-12): a real
    agreement-creation-via-text turn, hitting Morning MCP for real (`resolve_client_name`
    against a known, permanent sandbox client - see GROUND_TRUTH_CLIENTS.md) - not a
    reminder/local-tool stand-in. Added specifically because the reminder-based repro
    used earlier in this session's live debugging found and fixed a real code bug (an
    empty `tools` list on the reminder-confirmation follow-up call) that had nothing to
    do with the actual live failure being chased (add_client/agreement flows, which go
    through Morning MCP, not reminders at all) - this class verifies the reaction cycle
    on the actual MCP-backed flow directly, judgment-only (no hard assertion on emoji
    choice, same discipline as the rest of this file).

Run with: pytest tests/billed/test_reaction_judgment_tuning.py -m billed -v
"""
import logging
from pathlib import Path

import pytest

from src.models.config import AppConfiguration
from tests._reaction_capture import ReactionCaptureStub
from tests.billed.denidin_mcp_e2e_helpers import GODFATHER_CHAT_ID
from tests.billed.reaction_judgment_pool import BILLED_REACTION_SCENARIOS
from tests.e2e_helpers import create_real_notification, get_response, sanity_worker_data_root

logger = logging.getLogger(__name__)


def _scenario(name):
    for scenario in BILLED_REACTION_SCENARIOS:
        if scenario["name"] == name:
            return scenario
    raise KeyError(f"no such scenario in BILLED_REACTION_SCENARIOS: {name!r}")


def _send_turn(chat_id: str, id_message: str, text: str):
    """Sends one real textMessage webhook turn through the actual dispatcher and
    returns the (tracked, never-sent-to-Green-API) notification."""
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
    return notification


@pytest.mark.billed
class TestReactionJudgmentTuningHardAssertions:

    @pytest.fixture
    def config(self):
        config_path = Path(__file__).parent.parent.parent / "config" / "config.json"
        if not config_path.exists():
            pytest.skip("config.json not found")
        config = AppConfiguration.from_file(str(config_path))
        config.validate()
        test_data_root = sanity_worker_data_root()
        config.data_root = str(test_data_root)
        config.memory['session']['storage_dir'] = str(test_data_root / "sessions")
        config.memory['longterm']['storage_dir'] = str(test_data_root / "memory")
        return config

    @pytest.fixture
    def denidin_app(self, config):
        import denidin

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
        app.ai_handler.green_api_bot = app.green_api_bot
        return app

    def test_ambient_group_chatter_lunch_makes_zero_reaction_calls(self, denidin_app):
        scenario = _scenario("ambient_group_chatter_lunch")
        stub = ReactionCaptureStub()
        with stub.installed():
            for i, (role, content) in enumerate(scenario["prior_turns"]):
                if role == "user":
                    _send_turn(scenario["chat_id"], f"TUNING_LUNCH_PRIOR_{i}", content)
            notification = _send_turn(scenario["chat_id"], "TUNING_LUNCH_FINAL", scenario["message"])
            get_response(notification)  # exercised for parity with other E2E tests; not asserted on
        assert stub.calls == [], (
            f"expected zero send_reaction calls for ambient group chatter, got {stub.calls}"
        )

    def test_ambient_group_chatter_debate_makes_zero_reaction_calls(self, denidin_app):
        scenario = _scenario("ambient_group_chatter_debate")
        stub = ReactionCaptureStub()
        with stub.installed():
            for i, (role, content) in enumerate(scenario["prior_turns"]):
                if role == "user":
                    _send_turn(scenario["chat_id"], f"TUNING_DEBATE_PRIOR_{i}", content)
            notification = _send_turn(scenario["chat_id"], "TUNING_DEBATE_FINAL", scenario["message"])
            get_response(notification)
        assert stub.calls == [], (
            f"expected zero send_reaction calls for ambient group chatter, got {stub.calls}"
        )

    def test_flip_earlier_message_targets_the_same_id_message(self, denidin_app):
        scenario = _scenario("react_flip_earlier_message")
        stub = ReactionCaptureStub()
        with stub.installed():
            for i, (role, content) in enumerate(scenario["prior_turns"]):
                if role == "user":
                    _send_turn(scenario["chat_id"], f"TUNING_FLIP_PRIOR_{i}", content)
            notification = _send_turn(scenario["chat_id"], "TUNING_FLIP_FINAL", scenario["message"])
            get_response(notification)

        # This is judgment-dependent (the model may or may not choose to react at all,
        # to either turn) - the harness only asserts targeting correctness WHEN a flip
        # actually happens. Fewer than 2 calls means no flip occurred this round; that's
        # a tuning-loop observation (T012), not a hard failure here.
        if len(stub.calls) < 2:
            pytest.skip(
                f"model made {len(stub.calls)} send_reaction call(s) this round - no flip to "
                "verify targeting on; re-run as part of the AI-run tuning loop (T012)"
            )
        assert stub.calls[-1].id_message == stub.calls[0].id_message, (
            f"flip's second call should target the same id_message as the first: {stub.calls}"
        )


@pytest.mark.billed
class TestAgreementCreationReactionsBilled:
    """Added 2026-09-12, per explicit user request after the reminder-based repro used
    earlier in this session's live debugging turned out to test the wrong flow entirely
    (reminders are a local tool, no Morning MCP involved - the user's actual live
    complaint was about add_client/agreement flows, which DO hit Morning MCP). This
    class sends one real agreement-creation text message, against a known, permanent
    sandbox client (`זהבית צור` - see GROUND_TRUTH_CLIENTS.md, chosen specifically because
    it carries no invoice-number dependency, so accumulating documents across repeated
    runs of this test is safe), so `resolve_client_name` succeeds via a real Morning MCP
    round-trip within the SAME conversational turn `react_to_message` is attached to -
    no multi-turn clarification needed, so both the ask-side fast ack and the
    resolution reaction have a genuine chance to fire in one turn.

    Deliberately reuses `tests/billed/conftest.py`'s own `denidin_app`/`live_morning_tunnel`
    fixtures (config.test.json + GODFATHER_CHAT_ID) rather than this file's OTHER classes'
    hand-rolled `config`/`denidin_app` fixtures (config/config.json) - those omit `mcp` from
    `config_dict` entirely, a real, separate, pre-existing gap found while writing this test:
    Morning MCP tools silently never attach under that fixture, for any test using it,
    regardless of role - `_build_morning_mcp_tools` reads `self.config.mcp`, which is never
    populated because config.json's own `mcp` block never gets forwarded into `config_dict`.
    Not fixed in the other classes here (out of scope for this addition; `test_flip_earlier_
    message_targets_the_same_id_message`, godfather-role, has never actually exercised a
    Morning MCP call as a result) - flagging for whoever revisits that class next.

    Judgment-only, same discipline as the rest of this file - no assertion on emoji
    choice itself; only that at least one real `react_to_message` call happened
    (evidence the ask/resolution reaction mechanism is reachable on this real MCP-backed
    flow, not proof of any specific emoji judgment).
    """

    def test_agreement_creation_via_text_reacts_on_ask_and_resolution(
        self, denidin_app, live_morning_tunnel,
    ):
        chat_id = GODFATHER_CHAT_ID
        stub = ReactionCaptureStub()
        with stub.installed():
            notification = _send_turn(
                chat_id,
                "AGREEMENT_REACT_BILLED_1",
                "תעד הסכם שכר טרחה עם זהבית צור על 750 שח",
            )
            response = get_response(notification)

        logger.info(
            "test_agreement_creation_via_text_reacts_on_ask_and_resolution: "
            f"reply={getattr(response, 'response_text', None)!r}, calls={stub.calls!r}"
        )
        assert stub.calls, (
            "expected at least one real react_to_message call on a real Morning-MCP-"
            f"backed agreement-creation turn (fast ack and/or resolution) - got zero. "
            f"reply was: {getattr(response, 'response_text', None)!r}"
        )
