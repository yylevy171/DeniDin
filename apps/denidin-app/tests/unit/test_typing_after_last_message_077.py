"""bugfix-077: no typing indicator on the model call that follows a lone send_to_user.

The dots used to appear right after the last message because the app switched typing on for the call in which
the model merely decides to stop. A call that follows a round containing nothing but send_to_user (and no waiting
user messages) gets no typing; every other call keeps it.
"""
from types import SimpleNamespace

from src.backbone.typing_policy import typing_wanted_for_next_call


def _response(*tool_names):
    return SimpleNamespace(output=[SimpleNamespace(type="function_call", name=n) for n in tool_names])


def _outputs(n):
    return [{"type": "function_call_output", "call_id": f"c{i}", "output": "ok"} for i in range(n)]


def test_no_typing_after_a_round_with_only_send_to_user():
    outputs = _outputs(1)
    assert typing_wanted_for_next_call(_response("send_to_user"), outputs, outputs) is False


def test_no_typing_after_several_send_to_user_calls_in_one_round():
    outputs = _outputs(2)
    assert typing_wanted_for_next_call(_response("send_to_user", "send_to_user"), outputs, outputs) is False


def test_typing_when_the_round_also_called_another_tool():
    outputs = _outputs(2)
    assert typing_wanted_for_next_call(_response("send_to_user", "load_capabilities"), outputs, outputs) is True


def test_typing_after_a_round_without_send_to_user():
    outputs = _outputs(1)
    assert typing_wanted_for_next_call(_response("load_flows"), outputs, outputs) is True


def test_typing_when_a_user_message_arrived_meanwhile():
    outputs = _outputs(1)
    follow_up = outputs + [{"role": "user", "content": "עוד משהו"}]
    assert typing_wanted_for_next_call(_response("send_to_user"), outputs, follow_up) is True


def test_typing_when_the_response_had_no_tool_call():
    assert typing_wanted_for_next_call(_response(), [], [{"role": "developer", "content": "x"}]) is True
