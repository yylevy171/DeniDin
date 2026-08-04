"""Unit tests for bugfix-022: an approval-resolution call to OpenAI
(`_call_openai_approval_api`, Feature 022) must NEVER be automatically
retried at any layer, since a retry means dispatching an already-approved
document-creating MCP tool call a second time against the real Morning API.

Real incidents (2026-08-03, see specs/bugfixes/bugfix-022-...) showed this
happening via the OpenAI SDK's own auto-retry (fixed via max_retries=0), and
then recurring even with that fix in place - root-caused here to a leftover
tenacity `@retry(...)` decorator on `_call_openai_approval_api` itself, which
transparently re-invokes the whole method (a second real `responses.create()`
call) on RateLimitError/APITimeoutError/APIError before the exception ever
reaches `_resolve_pending_approval`'s own single-attempt error handling.

Only the OpenAI client is a stand-in (external service, per CONSTITUTION
SS I) - AIHandler, PendingApprovalManager are real.
"""
from unittest.mock import Mock, MagicMock

import pytest
from openai import RateLimitError

from src.constants.error_messages import APPROVAL_FAILED_TRY_AGAIN
from src.handlers.ai_handler import AIHandler
from src.managers.pending_approval_manager import PendingApproval
from src.models.config import AppConfiguration
from src.models.message import AIRequest


@pytest.fixture
def mock_config(tmp_path):
    config = Mock(spec=AppConfiguration)
    config.ai_model = "gpt-4o-mini"
    config.ai_reply_max_tokens = 500
    config.constitution_config = {}
    config.data_root = str(tmp_path / "data")
    config.memory = {
        'session': {'storage_dir': str(tmp_path / "data" / "sessions")},
        'longterm': {'enabled': False}
    }
    config.user_roles = {}
    config.godfather_phone = None
    return config


@pytest.fixture
def mock_ai_client():
    return MagicMock()


@pytest.fixture
def ai_handler(mock_config, mock_ai_client):
    return AIHandler(mock_ai_client, mock_config)


@pytest.fixture
def pending_approval():
    return PendingApproval(
        response_id="resp_original_123",
        approval_request_id="mcp_approval_req_456",
        tool_name="create_invoice",
        arguments='{"client_name": "דנה כהן", "amount": 500}',
        server_label="morning",
        created_at="2026-08-04T00:00:00+00:00",
    )


@pytest.fixture
def approval_request():
    return AIRequest(
        user_prompt="כן", constitution="", max_tokens=500,
        model="gpt-4o-mini", chat_id="972500000000@c.us", message_id="msg-approve-1",
        timestamp=1770000000,
    )


class TestApprovalResolutionNeverAutoRetries:
    def test_rate_limit_error_makes_exactly_one_call(
        self, ai_handler, mock_ai_client, pending_approval, approval_request
    ):
        """A 429 on the approval-resolution call must surface after exactly one
        attempt - it must never be silently retried at any layer (SDK or our
        own), since a retry means a second real dispatch of the
        already-approved tool call. This is the exact scenario from Incident 2
        (bugfix-022): the SDK's own retry was already disabled (max_retries=0)
        but a real retry still happened via a leftover tenacity decorator."""
        # _call_openai_approval_api calls self.client.with_options(max_retries=0)
        # first (see ai_handler.py) - the mock for the actual create() call
        # this reaches is therefore on .with_options.return_value, not on the
        # top-level client mock directly.
        scoped_create = mock_ai_client.with_options.return_value.responses.create
        scoped_create.side_effect = RateLimitError(
            "Rate limit exceeded", response=Mock(), body={}
        )

        result = ai_handler._resolve_pending_approval(
            pending_approval, approval_request, effective_chat_id="972500000000@c.us",
            user_obj=None, user_role="godfather", sender="972500000000@c.us",
            recipient=None,
        )

        assert scoped_create.call_count == 1, (
            "the approval-resolution call must be single-attempt - a retry here "
            "risks executing the already-approved document-creating tool twice"
        )
        assert result.response_text == APPROVAL_FAILED_TRY_AGAIN

    def test_rate_limit_error_leaves_pending_approval_in_place(
        self, ai_handler, mock_ai_client, pending_approval, approval_request
    ):
        """A clean single-attempt 429 failure means nothing executed - the
        pending approval must stay open so the user's next "כן" is a fresh
        attempt, not a duplicate risk."""
        scoped_create = mock_ai_client.with_options.return_value.responses.create
        scoped_create.side_effect = RateLimitError(
            "Rate limit exceeded", response=Mock(), body={}
        )
        chat_id = "972500000000@c.us"
        ai_handler.pending_approval_manager.set(chat_id, pending_approval)

        ai_handler._resolve_pending_approval(
            pending_approval, approval_request, effective_chat_id=chat_id,
            user_obj=None, user_role="godfather", sender=chat_id, recipient=None,
        )

        assert ai_handler.pending_approval_manager.get(chat_id) == pending_approval
