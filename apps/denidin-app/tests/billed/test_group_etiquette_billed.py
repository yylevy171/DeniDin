"""
Billed E2E tests: Group Conversation Etiquette (Feature 039, US1/US5/US7).

Real, text-only OpenAI calls verifying the model's actual content-based judgment per
config/runtime_constitution.md's "Group Conversation Etiquette" section - this is
genuinely a model-behavior question, not a deterministic code path, so it can't be
unit-tested (see tasks.md Phase 10's design note).

NO MOCKING - real bot.router dispatch, real AIHandler, real OpenAI calls.

Run with: pytest tests/billed/test_group_etiquette_billed.py -m billed -v
"""

import logging
from pathlib import Path

import pytest

from src.models.config import AppConfiguration
from tests.e2e_helpers import create_real_notification, get_response, assert_hebrew_only

logger = logging.getLogger(__name__)

SENDER_CHAT_ID = '972522968679@c.us'


def _group_event(text, case_id, sender_name='Test Godfather'):
    """Each case gets its own group chat_id (never reused across cases or across
    runs, since test_data persists on disk) - a shared chat_id would accumulate
    conversation history across cases, and that history gets fed back into the
    model as context, confounding what's actually being judged for this one
    message. Each case must be evaluated on its own, single-message context."""
    import time
    group_chat_id = f'120363012345678901-{case_id}-{int(time.time())}@g.us'
    return {
        'typeWebhook': 'incomingMessageReceived',
        'timestamp': 1706601234,
        'senderData': {
            'chatId': group_chat_id,
            'sender': SENDER_CHAT_ID,
            'senderName': sender_name
        },
        'messageData': {
            'typeMessage': 'textMessage',
            'textMessageData': {'textMessage': text}
        }
    }


@pytest.mark.billed
class TestGroupEtiquetteBilled:
    """
    Group vs. GreenApi.getGroupData: since these test group chat_ids don't correspond
    to a real WhatsApp group, GroupMembershipResolver's real API call will fail
    (expected, handled gracefully - see GroupMembershipResolver.resolve's
    failure-returns-None path) and RBAC falls back to sender-only resolution. This
    doesn't affect the etiquette judgment under test here, which is entirely
    prompt-driven.
    """

    @pytest.fixture
    def config(self):
        # bugfix-024: was config.json, whose Green API instance is unauthorized
        # (stateInstance="notAuthorized", no phone linked) - confirmed live 2026-08-05,
        # which made case7's own_whatsapp_number fetch always fail open and skip.
        # config.test.json matches every other billed test file's convention and its
        # instance is confirmed authorized (used successfully throughout this session's
        # dev-environment testing).
        config_path = Path(__file__).parent.parent.parent / "config" / "config.test.json"
        if not config_path.exists():
            pytest.skip("config.test.json not found")

        config = AppConfiguration.from_file(str(config_path))
        config.validate()
        test_data_root = Path(__file__).parent.parent.parent / "test_data"
        config.data_root = str(test_data_root)
        config.memory['session']['storage_dir'] = str(test_data_root / "sessions")
        config.memory['longterm']['storage_dir'] = str(test_data_root / "memory")
        return config

    @pytest.fixture
    def denidin_app(self, config):
        import denidin
        if denidin.denidin_app is None:
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
                'user_roles': config.user_roles
            }
            denidin.denidin_app = denidin.initialize_app(config_dict)
        return denidin.denidin_app

    def test_case1_default_address_gets_substantive_reply(self, denidin_app):
        """US1: a plain group message, no "@" pattern, no signal it's for someone
        else - should get a normal, substantive reply."""
        from denidin import handle_text_message

        notification = create_real_notification(
            _group_event('מה המצב עם התיק של דוד כהן?', case_id='case1')
        )
        handle_text_message(notification)
        response = get_response(notification)

        logger.info(f"Case 1 (default address) response: {response!r}")
        assert response is not None, "Expected a substantive reply, got no reply at all"
        assert_hebrew_only(response)

    def test_case2_clearly_for_someone_else_gets_no_reply(self, denidin_app):
        """US5: a message clearly directed at another human by name, no "@" pattern
        - should get no reply at all (not a clarifying question). Deliberately a
        neutral, non-actionable question (not a task/reminder-shaped request) - to
        isolate whether addressee recognition itself works, separate from whether
        task-shaped requests specifically pull DeniDin toward "I can help with this"."""
        from denidin import handle_text_message

        notification = create_real_notification(
            _group_event('רותי, את יודעת איזה יום היום?', case_id='case2')
        )
        handle_text_message(notification)
        response = get_response(notification)

        logger.info(f"Case 2 (clearly for someone else) response: {response!r}")
        assert response is None, f"Expected no reply at all, got: {response!r}"

    def test_case3_genuinely_unclear_gets_clarifying_question(self, denidin_app):
        """US5: genuinely ambiguous whether directed at DeniDin or another
        participant, no "@" pattern - should get a short clarifying question, not
        silence and not a substantive answer."""
        from denidin import handle_text_message

        notification = create_real_notification(
            _group_event('אתה יכול לבדוק את זה ולחזור אליי?', case_id='case3')
        )
        handle_text_message(notification)
        response = get_response(notification)

        logger.info(f"Case 3 (genuinely unclear) response: {response!r}")
        assert response is not None, "Expected a clarifying question, got no reply at all"
        assert_hebrew_only(response)
        assert '?' in response, f"Expected a clarifying question (containing '?'), got: {response!r}"

    def test_case4_ordinary_message_negative_control(self, denidin_app):
        """US5 negative control: an ordinary message with no ambiguity signal must
        get a normal reply - neither the silent nor the ask-a-question path should
        fire on typical traffic."""
        from denidin import handle_text_message

        notification = create_real_notification(
            _group_event('תודה רבה על העזרה!', case_id='case4')
        )
        handle_text_message(notification)
        response = get_response(notification)

        logger.info(f"Case 4 (ordinary message) response: {response!r}")
        assert response is not None, "Expected a substantive reply, got no reply at all"
        assert_hebrew_only(response)

    def test_case5a_at_name_not_denidin_real_name_gets_no_reply(self, denidin_app):
        """US7: an "@Name" pattern naming a real participant (not DeniDin) - should
        get no reply, regardless of what the rest of the message says."""
        from denidin import handle_text_message

        notification = create_real_notification(
            _group_event('@רותי תבדקי את זה בבקשה', case_id='case5a')
        )
        handle_text_message(notification)
        response = get_response(notification)

        logger.info(f"Case 5a (@ real name, not DeniDin) response: {response!r}")
        assert response is None, f"Expected no reply at all, got: {response!r}"

    def test_case5b_at_name_not_denidin_arbitrary_text_gets_no_reply(self, denidin_app):
        """US7: an "@Name" pattern with arbitrary text that isn't a real participant's
        name either - must behave identically to case 5a, proving the check is
        self-referential only, not a roster lookup."""
        from denidin import handle_text_message

        notification = create_real_notification(
            _group_event('@lalalal תבדקי את זה בבקשה', case_id='case5b')
        )
        handle_text_message(notification)
        response = get_response(notification)

        logger.info(f"Case 5b (@ arbitrary text) response: {response!r}")
        assert response is None, f"Expected no reply at all, got: {response!r}"

    def test_case6_at_denidin_overrides_ambiguous_content(self, denidin_app):
        """US7: ambiguous-looking content, but an explicit @DeniDin tag - should get
        a substantive reply despite the ambiguity, no clarifying question."""
        from denidin import handle_text_message

        notification = create_real_notification(
            _group_event('אתה יכול לבדוק את זה? @DeniDin', case_id='case6')
        )
        handle_text_message(notification)
        response = get_response(notification)

        logger.info(f"Case 6 (@DeniDin overrides ambiguity) response: {response!r}")
        assert response is not None, "Expected a substantive reply, got no reply at all"
        assert_hebrew_only(response)

    def test_case7_native_mention_by_own_phone_number_gets_substantive_reply(self, denidin_app):
        """bugfix-024: a REAL WhatsApp native @-mention picker inserts the mentioned
        contact's raw phone number into message text, never a display name (confirmed
        live via a real Green API getWaSettings call, not assumed from docs - see
        CONSTITUTION.md "NO UNVERIFIED THIRD-PARTY ASSUMPTIONS"). This reproduces that
        exact real shape - "@<own bare-digit number>" - using denidin_app's own,
        actually-resolved own_whatsapp_number (never a hardcoded guess), and must get
        a substantive reply, same as case6's manually-typed "@DeniDin" - proving
        AIHandler.create_request's self-mention normalization (_normalize_self_mentions)
        correctly rewrites it before the model ever sees the raw digits."""
        from denidin import handle_text_message

        own_number = denidin_app.ai_handler.own_whatsapp_number
        if not own_number:
            pytest.skip(
                "own_whatsapp_number not resolved this run (startup getWaSettings call "
                "failed or was unreachable) - can't reproduce the real native-mention "
                "shape without it"
            )

        notification = create_real_notification(
            _group_event(f'@{own_number} מי אתה?', case_id='case7')
        )
        handle_text_message(notification)
        response = get_response(notification)

        logger.info(f"Case 7 (native @-mention by own phone number) response: {response!r}")
        assert response is not None, (
            f"Expected a substantive reply (own number {own_number!r} was @-mentioned - "
            f"this IS DeniDin being addressed), got no reply at all"
        )
        assert_hebrew_only(response)
