"""Unit tests for bugfix-028 B4(b): the approved tool must never silently run
ZERO times.

`_resolve_pending_approval` (ai_handler.py) already guarded against the
approved tool running MORE than once (bugfix-022, 2026-08-03 incident). Nothing
guarded the opposite: a response that comes back with the approval accepted but
carrying no `mcp_call` for the approved tool at all - e.g. the tool call itself
failed to resolve (a client lookup that returned "not found") without the
failure being typed as an error anywhere the caller could see. In production
this let the same ₪40,000 document be approved eight times, created zero
times, with the user re-asked an identical question every time and no hint
the previous attempt had failed.

This is unit-testable and deterministic: force the fake OpenAI response to
carry zero `mcp_call` items for the approved tool's name, and assert (a) the
user is told plainly and specifically that nothing was created, (b) the
pending approval is CLEARED rather than left in place (retrying an identical
request would fail identically - leaving it pending is what produced the
production loop), and (c) this is distinct from the existing ">1" duplicate
guard, which must still fire correctly and must not be triggered by this case.

Same harness as test_ai_handler_approval_no_retry.py (bugfix-022's own unit
tests for this same method) - only the OpenAI client is a stand-in (external
service, per CONSTITUTION SS I); AIHandler and PendingApprovalManager are real.
"""
from unittest.mock import MagicMock, Mock

import pytest

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
        tool_name="create_transaction_account",
        arguments='{"client_name": "הסתדרות כללית חדשה", "amount": 40000}',
        server_label="morning",
        created_at="2026-08-10T00:00:00+00:00",
    )


@pytest.fixture
def approval_request():
    return AIRequest(
        user_prompt="כן", constitution="", max_tokens=500,
        model="gpt-4o-mini", chat_id="972500000000@c.us", message_id="msg-approve-1",
        timestamp=1770000000,
    )


def _mcp_call(name, output=None, error=None):
    """A fake `response.output` item shaped like an executed mcp_call - only the
    attributes `_resolve_pending_approval` actually reads via getattr()."""
    call = Mock()
    call.type = "mcp_call"
    call.name = name
    call.output = output
    call.error = error
    return call


def _fake_response(output_items, response_id="resp_followup_1"):
    response = Mock()
    response.id = response_id
    response.output = output_items
    return response


class TestZeroExecutionIsDetected:
    def test_zero_mcp_calls_for_the_approved_tool_is_never_treated_as_success(
        self, ai_handler, mock_ai_client, pending_approval, approval_request
    ):
        """The exact production shape: the model accepted the approval and the
        response carries NO mcp_call for the approved tool at all (e.g. the
        underlying resolution failed silently) - this must not fall through to
        `_finalize_response` as if the document was created."""
        scoped_create = mock_ai_client.with_options.return_value.responses.create
        scoped_create.return_value = _fake_response([])  # nothing executed at all

        result = ai_handler._resolve_pending_approval(
            pending_approval, approval_request, effective_chat_id="972500000000@c.us",
            user_obj=None, user_role="godfather", sender="972500000000@c.us",
            recipient=None,
        )

        assert result is not None
        assert "לא נוצר שום מסמך" in result.response_text, (
            f"the user must be told plainly that nothing was created, got: "
            f"{result.response_text!r}"
        )

    def test_zero_execution_clears_the_pending_approval(
        self, ai_handler, mock_ai_client, pending_approval, approval_request
    ):
        """Must NOT stay pending: the production incident was the SAME pending
        approval being re-approved eight times with an identical, doomed-to-fail
        retry each time. Clearing it means the user's next message starts a
        genuinely fresh turn rather than repeating the same failure."""
        scoped_create = mock_ai_client.with_options.return_value.responses.create
        scoped_create.return_value = _fake_response([])
        chat_id = "972500000000@c.us"
        ai_handler.pending_approval_manager.set(chat_id, pending_approval)

        ai_handler._resolve_pending_approval(
            pending_approval, approval_request, effective_chat_id=chat_id,
            user_obj=None, user_role="godfather", sender=chat_id, recipient=None,
        )

        assert ai_handler.pending_approval_manager.get(chat_id) is None, (
            "a zero-execution result must clear the pending approval, not leave "
            "it in place for an identical, doomed-to-repeat retry"
        )

    def test_other_tools_executing_does_not_mask_the_approved_one_never_running(
        self, ai_handler, mock_ai_client, pending_approval, approval_request
    ):
        """The zero-execution check must count only the APPROVED tool's own
        executions - a response carrying mcp_calls for OTHER tools (e.g. an
        unrelated list_invoices the model made while failing to resolve the
        approved one) must not be mistaken for the approved tool having run."""
        scoped_create = mock_ai_client.with_options.return_value.responses.create
        scoped_create.return_value = _fake_response([
            _mcp_call("list_invoices", output="[]"),
            _mcp_call("get_client_details", output="לא נמצא לקוח בשם הזה."),
        ])

        result = ai_handler._resolve_pending_approval(
            pending_approval, approval_request, effective_chat_id="972500000000@c.us",
            user_obj=None, user_role="godfather", sender="972500000000@c.us",
            recipient=None,
        )

        assert "לא נוצר שום מסמך" in result.response_text

    def test_failure_detail_from_the_actual_tool_output_is_surfaced_when_present(
        self, ai_handler, mock_ai_client, pending_approval, approval_request
    ):
        """When some OTHER call in the same response carries a real failure
        message (e.g. a client lookup that came back not-found -
        bugfix-028 B4(c)), that detail should reach the user rather than a
        fully generic 'nothing happened' - this is what would have told the
        user, on attempt ONE, that the client name needed fixing, instead of
        eight identical silent retries."""
        scoped_create = mock_ai_client.with_options.return_value.responses.create
        scoped_create.return_value = _fake_response([
            _mcp_call("get_client_details", output="לא נמצא לקוח בשם הזה."),
        ])

        result = ai_handler._resolve_pending_approval(
            pending_approval, approval_request, effective_chat_id="972500000000@c.us",
            user_obj=None, user_role="godfather", sender="972500000000@c.us",
            recipient=None,
        )

        assert "לא נמצא לקוח" in result.response_text, (
            f"the real failure detail should be surfaced, got: {result.response_text!r}"
        )

    def test_failure_detail_from_a_real_mcp_error_field_is_surfaced(
        self, ai_handler, mock_ai_client, pending_approval, approval_request
    ):
        """Root-cause fix follow-up (2026-08-12): a failed call's reason now
        lives in `.error` (output=None), not `.output` - confirmed live
        against the real OpenAI SDK: `error` is
        `{"type": "mcp_tool_execution_error", "content": [{"type": "text",
        "text": "..."}]}`. Without _extract_mcp_error_text, this would
        silently fall through to the fully generic message, the exact same
        silent-failure shape bugfix-028 exists to kill - just one layer up
        from where it was originally found."""
        scoped_create = mock_ai_client.with_options.return_value.responses.create
        scoped_create.return_value = _fake_response([
            _mcp_call(
                "get_client_details",
                output=None,
                error={
                    "type": "mcp_tool_execution_error",
                    "content": [{"type": "text", "text": "לא נמצא לקוח בשם הזה. (מרדכי קיואן)"}],
                },
            ),
        ])

        result = ai_handler._resolve_pending_approval(
            pending_approval, approval_request, effective_chat_id="972500000000@c.us",
            user_obj=None, user_role="godfather", sender="972500000000@c.us",
            recipient=None,
        )

        assert "לא נמצא לקוח" in result.response_text, (
            f"the real failure detail from .error should be surfaced, got: {result.response_text!r}"
        )


class TestZeroExecutionGuardDoesNotInterfereWithTheExistingDuplicateGuard:
    """Guard against a regression in the OTHER direction: adding the ==0 check
    must not affect the >1 (duplicate execution) path bugfix-022 already relies
    on, and exactly one clean execution must still reach _finalize_response."""

    def test_more_than_one_execution_is_still_flagged_as_a_duplicate(
        self, ai_handler, mock_ai_client, mock_config, pending_approval, approval_request
    ):
        from src.constants.error_messages import APPROVAL_POSSIBLY_DUPLICATED

        scoped_create = mock_ai_client.with_options.return_value.responses.create
        scoped_create.return_value = _fake_response([
            _mcp_call("create_transaction_account", output="נוצר מסמך מספר 100"),
            _mcp_call("create_transaction_account", output="נוצר מסמך מספר 101"),
        ])

        result = ai_handler._resolve_pending_approval(
            pending_approval, approval_request, effective_chat_id="972500000000@c.us",
            user_obj=None, user_role="godfather", sender="972500000000@c.us",
            recipient=None,
        )

        assert result.response_text == APPROVAL_POSSIBLY_DUPLICATED
        assert "לא נוצר שום מסמך" not in result.response_text, (
            "a duplicate (>1) execution must never be reported using the "
            "zero-execution (0) message - they are different failures"
        )

    def test_exactly_one_execution_is_not_treated_as_zero(
        self, ai_handler, mock_ai_client, pending_approval, approval_request, monkeypatch
    ):
        """The ordinary success path: exactly one execution of the approved tool
        must reach _finalize_response, not the zero-execution branch."""
        scoped_create = mock_ai_client.with_options.return_value.responses.create
        scoped_create.return_value = _fake_response([
            _mcp_call("create_transaction_account", output="נוצר מסמך מספר 100"),
        ])

        finalize_calls = []
        monkeypatch.setattr(
            ai_handler, "_finalize_response",
            lambda *a, **kw: finalize_calls.append((a, kw)) or "FINALIZED"
        )

        result = ai_handler._resolve_pending_approval(
            pending_approval, approval_request, effective_chat_id="972500000000@c.us",
            user_obj=None, user_role="godfather", sender="972500000000@c.us",
            recipient=None,
        )

        assert len(finalize_calls) == 1, "exactly one clean execution must reach _finalize_response"
        assert result == "FINALIZED"
