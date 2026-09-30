"""Pure helpers for the load_flows/unload_flows/load_capabilities/
unload_capabilities tools: parsing the model's requested names against a closed
enum, applying load/unload to a current list, and describing the result back to
the model. No state and no I/O - the orchestrator owns persistence."""
from enum import Enum
from typing import List, Sequence, Tuple, Type


def parse_requested(enum_cls: Type[Enum], requested: Sequence[str]) -> Tuple[List, List[str]]:
    """Splits `requested` into (valid enum members, de-duplicated, in order;
    unknown names, reported back to the model rather than silently dropped)."""
    valid: List = []
    unknown: List[str] = []
    for name in requested:
        try:
            item = enum_cls(name)
        except ValueError:
            unknown.append(str(name))
            continue
        if item not in valid:
            valid.append(item)
    return valid, unknown


def apply_loading(current: List, valid: List, *, loading: bool) -> List:
    """The new loaded list: `valid` appended (no duplicates) or removed."""
    if loading:
        return current + [item for item in valid if item not in current]
    return [item for item in current if item not in valid]


def describe_loading(kind: str, *, loading: bool, valid: List, unknown: List[str],
                     flows_now: List[str], capabilities_now: List[str]) -> str:
    """The function_call_output text fed back to the model."""
    message = (
        f"{'loaded' if loading else 'unloaded'} {kind}s: {', '.join(i.value for i in valid) or '(none)'}. "
        f"Loaded flows now: {', '.join(flows_now) or '(none)'}. "
        f"Loaded capabilities now: {', '.join(capabilities_now) or '(none)'}."
    )
    if loading and valid:
        message += (" Their blueprint text is attached starting now." if kind == "flow"
                    else " Their instructions and tools are attached starting now.")
    if unknown:
        message += f" error: unknown {kind}(s) ignored: {', '.join(unknown)}."
    return message
