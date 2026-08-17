"""
Unit tests for PendingLocalToolApprovalManager (Feature 054).

Covers tasks.md T006a: get/set/clear/attach_sent_message_id, matching the shape
already established by Feature 022's PendingApprovalManager, but for local
function-tool calls (create_reminder/modify_reminder/delete_reminder) rather
than remote MCP tool calls. See
specs/in-progress/054-reminders-functionality-mgmt/contracts/local-tool-approval-gate.md.
"""

import pytest

from src.managers.pending_local_tool_approval_manager import (
    PendingLocalToolApproval,
    PendingLocalToolApprovalManager,
)


@pytest.fixture
def manager():
    return PendingLocalToolApprovalManager()


def _approval(**overrides):
    base = {
        "tool_name": "create_reminder",
        "response_id": "resp_abc123",
        "call_id": "call_xyz789",
        "arguments": {"message_text": "call the accountant", "schedule_type": "one_time"},
        "created_at": "2026-08-16T10:00:00+03:00",
    }
    base.update(overrides)
    return PendingLocalToolApproval(**base)


class TestGetSetClear:
    def test_get_returns_none_when_nothing_pending(self, manager):
        assert manager.get("972501234567@c.us") is None

    def test_set_then_get_returns_the_same_object(self, manager):
        approval = _approval()
        manager.set("972501234567@c.us", approval)
        assert manager.get("972501234567@c.us") is approval

    def test_arguments_is_a_dict_not_a_json_string(self, manager):
        # Unlike PendingApproval.arguments (a JSON string, for MCP audit-replay),
        # this is already-parsed - no second round-trip needed to resolve it.
        approval = _approval(arguments={"reminder_id": "abc", "scope": "whole_series"})
        manager.set("chat1", approval)
        result = manager.get("chat1")
        assert isinstance(result.arguments, dict)
        assert result.arguments["scope"] == "whole_series"

    def test_set_overwrites_existing_pending_for_same_chat(self, manager):
        first = _approval(tool_name="create_reminder")
        second = _approval(tool_name="delete_reminder")
        manager.set("chat1", first)
        manager.set("chat1", second)
        assert manager.get("chat1") is second

    def test_different_chats_are_independent(self, manager):
        a = _approval(tool_name="create_reminder")
        b = _approval(tool_name="modify_reminder")
        manager.set("chat1", a)
        manager.set("chat2", b)
        assert manager.get("chat1") is a
        assert manager.get("chat2") is b

    def test_clear_removes_pending_approval(self, manager):
        manager.set("chat1", _approval())
        manager.clear("chat1")
        assert manager.get("chat1") is None

    def test_clear_on_empty_chat_is_a_safe_no_op(self, manager):
        manager.clear("never-had-anything")  # must not raise
        assert manager.get("never-had-anything") is None

    def test_clearing_one_chat_does_not_affect_another(self, manager):
        manager.set("chat1", _approval())
        manager.set("chat2", _approval())
        manager.clear("chat1")
        assert manager.get("chat1") is None
        assert manager.get("chat2") is not None


class TestAttachSentMessageId:
    def test_attaches_to_existing_pending_approval(self, manager):
        manager.set("chat1", _approval())
        manager.attach_sent_message_id("chat1", "wamid.123")
        assert manager.get("chat1").sent_message_id == "wamid.123"

    def test_defaults_to_none_before_attach(self, manager):
        manager.set("chat1", _approval())
        assert manager.get("chat1").sent_message_id is None

    def test_no_op_when_nothing_pending(self, manager):
        manager.attach_sent_message_id("never-had-anything", "wamid.123")  # must not raise
        assert manager.get("never-had-anything") is None

    def test_no_op_after_already_cleared(self, manager):
        manager.set("chat1", _approval())
        manager.clear("chat1")
        manager.attach_sent_message_id("chat1", "wamid.123")  # must not raise, no resurrection
        assert manager.get("chat1") is None


class TestPendingLocalToolApprovalDataclass:
    def test_defaults(self):
        approval = PendingLocalToolApproval(tool_name="create_reminder")
        assert approval.response_id == ""
        assert approval.call_id == ""
        assert approval.arguments == {}
        assert approval.created_at == ""
        assert approval.sent_message_id is None

    def test_two_instances_have_independent_argument_dicts(self):
        # dataclass default_factory=dict must not share a mutable default across instances.
        a = PendingLocalToolApproval(tool_name="create_reminder")
        b = PendingLocalToolApproval(tool_name="delete_reminder")
        a.arguments["x"] = 1
        assert "x" not in b.arguments
