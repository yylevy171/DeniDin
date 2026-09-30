"""
The tools that drive the Backbone's resolution loop (Feature
063 — see
specs/repo/features/063-refactor-oversized-handlers/contracts/capability-resolution-loop.md).

Every turn's single merged backbone call has these attached alongside
BACKBONE_TOOLS (send_progress_update/react_to_message, unchanged) - together
with record_planning_status/send_to_user they are the tools of the
always-present capabilities (ALWAYS_PRESENT_CAPABILITIES); the approval tool
belongs to the on-demand cap_approval_with_buttons instead - real,
native OpenAI function-calling tools, not a hand-authored JSON envelope.

`load_flows([...])` loads flow blueprints (config/prompts/flows/) and
`load_capabilities([...])` loads capabilities - both always plural. The moment a
capability is loaded, both its prompt text AND its own real domain tools
(create_reminder, the Morning MCP tools, etc.) are attached to every following
call in this chat, starting the very next round - the model then calls the real
tool directly, guided by that capability's own prompt. Flows and capabilities
stay attached across turns until `unload_flows`/`unload_capabilities` remove
them, `reset_to_backbone` clears everything, or the capabilities_reset_minutes
idle sweep clears them automatically - see Session.active_flows /
Session.active_capabilities (src/managers/session_manager.py) for where this
state actually lives.
"""
from typing import Any, Dict, List, Tuple

from src.backbone.capability_tags import CapabilityTag
from src.backbone.flow_tags import FlowTag

def _names_tool(name: str, description: str, param: str, enum_values: List[str], param_doc: str) -> Dict[str, Any]:
    """One plural load/unload tool: a single array parameter of closed-set values."""
    return {
        "type": "function",
        "name": name,
        "description": description,
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                param: {
                    "type": "array",
                    "items": {"type": "string", "enum": enum_values},
                    "description": param_doc,
                },
            },
            "required": [param],
            "additionalProperties": False,
        },
    }


_CAPABILITY_VALUES = [t.value for t in CapabilityTag]
_FLOW_VALUES = [t.value for t in FlowTag]

LOAD_CAPABILITIES_TOOL: Dict[str, Any] = _names_tool(
    "load_capabilities",
    "Loads one or several capabilities at once (always an array; one item is "
    "fine). Each capability's prompt AND its own real tools are attached "
    "starting the very next round - call a capability's own tool directly once "
    "it is loaded, there is no separate 'use' step. Stays loaded across this "
    "and future turns in this chat until you unload it or reset_to_backbone, "
    "or it auto-clears after a period of inactivity. Already-loaded "
    "capabilities are a harmless no-op.",
    "capabilities", _CAPABILITY_VALUES,
    "The CapabilityTag values to load, e.g. ['cap_client_read', 'cap_invoicing_write'].",
)

UNLOAD_CAPABILITIES_TOOL: Dict[str, Any] = _names_tool(
    "unload_capabilities",
    "Removes one or several previously-loaded capabilities (always an array) - "
    "their prompts and tools stop being attached starting the next round. Use "
    "it once you no longer anticipate needing them for the user's current "
    "request(s). Capabilities that are not loaded are a harmless no-op.",
    "capabilities", _CAPABILITY_VALUES, "The CapabilityTag values to unload.",
)

LOAD_FLOWS_TOOL: Dict[str, Any] = _names_tool(
    "load_flows",
    "Loads one or several flows at once (always an array; one item is fine; "
    "combining flows is allowed when a request spans more than one). A flow is "
    "a blueprint: it tells you which capabilities to load, in what order and "
    "how their results connect - starting the very next round. Loading a flow "
    "does NOT load its capabilities; you load those yourself, as the flow "
    "directs. Stays loaded across this and future turns in this chat until "
    "you unload it or reset_to_backbone, or it auto-clears after a period of "
    "inactivity. Already-loaded flows are a harmless no-op.",
    "flows", _FLOW_VALUES, "The FlowTag values to load, e.g. ['flow_add_client'].",
)

UNLOAD_FLOWS_TOOL: Dict[str, Any] = _names_tool(
    "unload_flows",
    "Removes one or several previously-loaded flows (always an array) once "
    "their blueprint is no longer needed. Flows that are not loaded are a "
    "harmless no-op.",
    "flows", _FLOW_VALUES, "The FlowTag values to unload.",
)

RESET_TO_BACKBONE_TOOL: Dict[str, Any] = {
    "type": "function",
    "name": "reset_to_backbone",
    "description": (
        "Unloads EVERY currently-loaded flow AND capability at once - "
        "equivalent to unload_flows and unload_capabilities for everything "
        "loaded. Use this once you judge you're genuinely done with the "
        "user's request(s) for now, not mid-task. Harmless no-op if nothing "
        "is loaded."
    ),
    "strict": True,
    "parameters": {"type": "object", "properties": {}, "required": [], "additionalProperties": False},
}

RECORD_PLANNING_STATUS_TOOL: Dict[str, Any] = {
    "type": "function",
    "name": "record_planning_status",
    "description": (
        "Records your own running account of where this turn (and, across "
        "turns, this whole task) stands - use this every turn, per the "
        "Backbone prompt's guidance on when. Three free-text sections, your "
        "own words, no fixed format required beyond the three headings."
    ),
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "where_i_was": {"type": "string", "description": "What has happened so far."},
            "this_turns_purpose": {"type": "string", "description": "What this turn is for."},
            "expectation": {"type": "string", "description": "What you expect to happen/need next."},
        },
        "required": ["where_i_was", "this_turns_purpose", "expectation"],
        "additionalProperties": False,
    },
}

SEND_TO_USER_TOOL: Dict[str, Any] = {
    "type": "function",
    "name": "send_to_user",
    "description": (
        "Sends your actual reply to the user - a real capability like any "
        "other, called whenever you're ready to speak (not just at the very "
        "end). Pass the literal text '[[NO_REPLY]]' to deliberately say "
        "nothing this turn (e.g. a group message clearly addressed to someone "
        "else). For a yes/no confirmation question, use "
        "approval_with_yes_no_buttons instead - it gives the user tappable "
        "buttons."
    ),
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "The reply text, or '[[NO_REPLY]]'."},
        },
        "required": ["text"],
        "additionalProperties": False,
    },
}

APPROVAL_WITH_YES_NO_BUTTONS_TOOL: Dict[str, Any] = {
    "type": "function",
    "name": "approval_with_yes_no_buttons",
    "description": (
        "Sends a yes/no confirmation question to the user, with real tappable "
        "WhatsApp buttons - use this instead of send_to_user whenever you need "
        "the user's explicit yes/no sign-off before doing something (creating/"
        "modifying a document, a reminder, anything else that needs "
        "confirmation first). Completely stateless and domain-agnostic - it "
        "just asks and ends your turn; there is no separate 'resolve' step. "
        "On the user's next message, read your own conversation history/"
        "record_planning_status note to see what you asked and what they "
        "answered, then act (or ask again) accordingly."
    ),
    "strict": True,
    "parameters": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "The yes/no question to ask, ending on a clear closed question.",
            },
        },
        "required": ["text"],
        "additionalProperties": False,
    },
}

RESOLUTION_TOOLS: List[Dict[str, Any]] = [
    LOAD_FLOWS_TOOL,
    UNLOAD_FLOWS_TOOL,
    LOAD_CAPABILITIES_TOOL,
    UNLOAD_CAPABILITIES_TOOL,
    RESET_TO_BACKBONE_TOOL,
    RECORD_PLANNING_STATUS_TOOL,
    SEND_TO_USER_TOOL,
]

# Attached only while cap_approval_with_buttons is loaded (toolsets.py); still
# executed by the backbone itself, since it ends the turn.

_RESOLUTION_TOOL_NAMES = {
    "load_flows", "unload_flows", "load_capabilities", "unload_capabilities", "reset_to_backbone",
    "record_planning_status", "send_to_user", "approval_with_yes_no_buttons",
}


def extract_resolution_tool_calls(response: Any) -> List[Tuple[str, str, Dict[str, Any]]]:
    """Scans `response.output` for function_call items among the resolution
    tools above. Returns a list of (call_id, tool_name, args) in
    output order. Never raises - a malformed call's arguments are skipped
    (logged), not fatal to the round."""
    import json
    import logging

    logger = logging.getLogger(__name__)
    calls: List[Tuple[str, str, Dict[str, Any]]] = []
    for item in (getattr(response, "output", None) or []):
        if getattr(item, "type", None) != "function_call":
            continue
        name = getattr(item, "name", None)
        if name not in _RESOLUTION_TOOL_NAMES:
            continue
        try:
            args = json.loads(item.arguments)
        except (json.JSONDecodeError, TypeError) as exc:
            logger.warning("Malformed %r function_call arguments discarded: %s", name, exc)
            continue
        calls.append((getattr(item, "call_id", ""), name, args))
    return calls
