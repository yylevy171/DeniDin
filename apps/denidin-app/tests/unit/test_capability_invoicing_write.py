"""Unit tests for the Invoicing/Morning — Write capability handler (Feature 063
write-approval-flow parity): propose -> pending MCP approval -> approve/decline,
using OpenAI's own native `mcp_approval_request`/`mcp_approval_response`
mechanism (Feature 022's PendingApprovalManager, shared unmodified)."""
from unittest.mock import MagicMock

from src.capabilities.invoicing.handler import propose_write, resolve_button_tap, resolve_typed_reply
from src.capabilities.invoicing.tools import build_fallback_text
from src.managers.pending_approval_manager import PendingApproval


def _fake_approval_request_response(tool_name, arguments_json):
    item = MagicMock()
    item.type = "mcp_approval_request"
    item.id = "ar_1"
    item.name = tool_name
    item.arguments = arguments_json
    item.server_label = "morning-invoices"
    response = MagicMock()
    response.output = [item]
    response.output_text = ""
    response.id = "resp_1"
    return response


def _fake_executed_response(tool_name, output_text="✅ בוצע."):
    call_item = MagicMock()
    call_item.type = "mcp_call"
    call_item.name = tool_name
    response = MagicMock()
    response.output = [call_item]
    response.output_text = output_text
    response.id = "resp_2"
    return response


def test_propose_write_creates_pending_mcp_approval():
    orchestrator = MagicMock()
    orchestrator.morning_mcp_locator.current_server_url.return_value = "https://mcp.example.com"
    orchestrator.config.mcp = {"morning_auth_token": "tok"}
    fake_response = _fake_approval_request_response(
        "create_transaction_account", '{"client_name": "עמיר כץ"}',
    )
    # 2026-09-16: propose_write now goes through orchestrator.call_capability_step
    # (return_response=True) instead of reimplementing the API call inline - stub
    # that shared method directly, same as any other capability step's test would.
    orchestrator.call_capability_step.return_value = fake_response
    request = MagicMock(model="gpt-5.6-luna", max_tokens=1000, chat_id="chat1", timestamp=None)
    request.user_prompt = "תפיק חשבון עסקה לעמיר כץ"

    result = propose_write(orchestrator, request, "", "", {"chat_id": "chat1"})

    assert "לאשר" in result
    orchestrator.pending_approval_manager.set.assert_called_once()
    chat_id_arg, pending_arg = orchestrator.pending_approval_manager.set.call_args[0]
    assert chat_id_arg == "chat1"
    assert pending_arg.tool_name == "create_transaction_account"
    assert pending_arg.approval_request_id == "ar_1"


def test_propose_write_no_approval_request_returns_model_text():
    orchestrator = MagicMock()
    orchestrator.morning_mcp_locator.current_server_url.return_value = "https://mcp.example.com"
    orchestrator.config.mcp = {"morning_auth_token": "tok"}
    response = MagicMock()
    response.output = []
    response.output_text = "לא זוהתה בקשה ליצירת מסמך."
    orchestrator.call_capability_step.return_value = response
    request = MagicMock(model="gpt-5.6-luna", max_tokens=1000, chat_id="chat1", timestamp=None)
    request.user_prompt = "מה שלומך?"

    result = propose_write(orchestrator, request, "", "", {"chat_id": "chat1"})
    assert result == "לא זוהתה בקשה ליצירת מסמך."
    orchestrator.pending_approval_manager.set.assert_not_called()


def test_resolve_button_tap_stale_returns_none():
    orchestrator = MagicMock()
    orchestrator.pending_approval_manager.get.return_value = None
    result = resolve_button_tap(orchestrator, "chat1", "denidin_approve", "stanza1", None)
    assert result is None


def test_resolve_button_tap_approve_executes_tool_once():
    orchestrator = MagicMock()
    pending = PendingApproval(
        response_id="resp_1", approval_request_id="ar_1", tool_name="create_transaction_account",
        arguments='{"client_name": "עמיר כץ"}', server_label="morning-invoices",
        created_at="2026-09-14T00:00:00", sent_message_id="stanza1",
    )
    orchestrator.pending_approval_manager.get.return_value = pending
    orchestrator.morning_mcp_locator.current_server_url.return_value = "https://mcp.example.com"
    orchestrator.config.mcp = {"morning_auth_token": "tok"}
    orchestrator.client.with_options.return_value.responses.create.return_value = _fake_executed_response(
        "create_transaction_account",
    )
    request = MagicMock(model="gpt-5.6-luna", max_tokens=1000, timestamp=1)

    response = resolve_button_tap(orchestrator, "chat1", "denidin_approve", "stanza1", request)

    orchestrator.client.with_options.assert_called_once_with(max_retries=0)
    orchestrator.pending_approval_manager.clear.assert_called_once_with("chat1")
    assert "בוצע" in response.response_text


def test_resolve_button_tap_decline_does_not_call_openai_again():
    orchestrator = MagicMock()
    pending = PendingApproval(
        response_id="resp_1", approval_request_id="ar_1", tool_name="create_transaction_account",
        arguments="{}", server_label="morning-invoices", created_at="2026-09-14T00:00:00",
        sent_message_id="stanza1",
    )
    orchestrator.pending_approval_manager.get.return_value = pending
    request = MagicMock(model="gpt-5.6-luna", max_tokens=1000, timestamp=1)

    response = resolve_button_tap(orchestrator, "chat1", "denidin_decline", "stanza1", request)

    orchestrator.client.with_options.assert_not_called()
    assert response.response_text == "בוטל."


def test_resolve_button_tap_duplicate_execution_is_flagged_not_silently_reported_success():
    orchestrator = MagicMock()
    pending = PendingApproval(
        response_id="resp_1", approval_request_id="ar_1", tool_name="create_transaction_account",
        arguments="{}", server_label="morning-invoices", created_at="2026-09-14T00:00:00",
        sent_message_id="stanza1",
    )
    orchestrator.pending_approval_manager.get.return_value = pending
    orchestrator.morning_mcp_locator.current_server_url.return_value = "https://mcp.example.com"
    orchestrator.config.mcp = {"morning_auth_token": "tok"}
    call_item_1 = MagicMock(type="mcp_call")
    call_item_1.name = "create_transaction_account"
    call_item_2 = MagicMock(type="mcp_call")
    call_item_2.name = "create_transaction_account"
    dup_response = MagicMock()
    dup_response.output = [call_item_1, call_item_2]
    dup_response.output_text = "✅ בוצע."
    orchestrator.client.with_options.return_value.responses.create.return_value = dup_response
    request = MagicMock(model="gpt-5.6-luna", max_tokens=1000, timestamp=1)

    response = resolve_button_tap(orchestrator, "chat1", "denidin_approve", "stanza1", request)

    assert "יותר מפעם אחת" in response.response_text


def test_resolve_typed_reply_no_pending_returns_none():
    orchestrator = MagicMock()
    orchestrator.pending_approval_manager.get.return_value = None
    request = MagicMock(user_prompt="כן", request_id="r1", model="gpt-5.6-luna", timestamp=1)

    result = resolve_typed_reply(orchestrator, request, "chat1")
    assert result is None


def test_resolve_typed_reply_decline_clears_and_returns_none():
    orchestrator = MagicMock()
    pending = PendingApproval(
        response_id="resp_1", approval_request_id="ar_1", tool_name="create_transaction_account",
        arguments="{}", server_label="morning-invoices", created_at="2026-09-14T00:00:00",
    )
    orchestrator.pending_approval_manager.get.return_value = pending
    request = MagicMock(user_prompt="לא", request_id="r1", model="gpt-5.6-luna", timestamp=1)

    result = resolve_typed_reply(orchestrator, request, "chat1")

    assert result is None
    orchestrator.pending_approval_manager.clear.assert_called_once_with("chat1")
    orchestrator.client.with_options.assert_not_called()


# --- build_fallback_text (tools.py) ------------------------------------------

def test_build_fallback_text_create_transaction_account():
    text = build_fallback_text("create_transaction_account", '{"client_name": "עמיר כץ", "amount": "500"}')
    assert "עמיר כץ" in text
    assert "500" in text


def test_build_fallback_text_never_exposes_internal_id_for_group_b_tools():
    text = build_fallback_text("cancel_transaction_account", '{"original_internal_morning_id": "uuid-secret"}')
    assert "uuid-secret" not in text


def test_build_fallback_text_unknown_tool_returns_generic():
    text = build_fallback_text("some_unrecognized_tool", "{}")
    assert "אישור" in text
