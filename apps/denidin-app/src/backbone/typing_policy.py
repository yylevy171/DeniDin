"""When WhatsApp's typing indicator is shown for a model call (bugfix-077).

The indicator is on while a model call is in flight. The call that follows a round whose only tool call was
`send_to_user` (with no user message waiting) is usually the one where the model just decides to stop, so
showing typing there leaves dots hanging after the last message. Every other call shows it.
"""
from typing import Any, Dict, List


def typing_wanted_for_next_call(response: Any, outputs: List[Dict[str, Any]],
                                follow_up_input: List[Dict[str, Any]]) -> bool:
    """False only when `response` called nothing but `send_to_user` and the next call's input is just
    those tool results (no waiting user message was added)."""
    names = [getattr(item, "name", None) for item in (getattr(response, "output", None) or [])
             if getattr(item, "type", None) == "function_call"]
    only_send_to_user = bool(names) and all(name == "send_to_user" for name in names)
    return not (only_send_to_user and len(follow_up_input) == len(outputs))
