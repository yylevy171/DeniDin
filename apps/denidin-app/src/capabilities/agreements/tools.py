"""Function-tool schemas for the Agreements capabilities (Feature 089, backbone-only).

Reads: `find_agreements`, `get_agreement`. Writes: `update_agreement`, `update_component`,
`add_component`, `set_component_status`, `set_agreement_status`. There is deliberately no
delete-component and no create-agreement tool for the bot: deletion is UI-only, and a new
agreement is created by the existing post-turn capture path (the user reporting a signed
agreement), not by a tool.

The schemas are non-strict so a write names only the fields it changes; every
component field is optional on an update.
"""
from typing import Any, Dict

_COMPONENT_FIELDS: Dict[str, Any] = {
    "label": {"type": "string", "description": "The component's short name, unique within the agreement."},
    "description": {"type": ["string", "null"], "description": "The component's wording."},
    "amount": {"type": ["number", "string", "null"], "description": "Fixed amount in NIS."},
    "percent": {"type": ["number", "string", "null"], "description": "Percentage fee."},
    "percent_base": {"type": ["string", "null"], "description": "What the percent applies to."},
    "trigger_condition": {"type": ["string", "null"], "description": "Condition that makes it payable."},
    "vat_status": {"type": ["string", "null"], "description": "כולל / לא כולל / לא צוין."},
    "txn_date": {"type": ["string", "null"], "description": "Transaction date, DD/MM/YYYY."},
}

FIND_AGREEMENTS_TOOL: Dict[str, Any] = {
    "type": "function",
    "name": "find_agreements",
    "description": (
        "Read-only. Returns every fee agreement of one client (exact stored client name), each with "
        "its payer, partner, partner percent, status and all its components (label, amount/percent, "
        "trigger, status, component_key). Use it to answer 'what is our agreement with X' and to "
        "identify WHICH agreement/component a request means. If it returns more than one agreement "
        "and the user did not say which, ASK - never pick one yourself."
    ),
    "parameters": {
        "type": "object",
        "properties": {"client_name": {"type": "string", "description": "The client's exact name."}},
        "required": ["client_name"],
    },
}

GET_AGREEMENT_TOOL: Dict[str, Any] = {
    "type": "function",
    "name": "get_agreement",
    "description": "Read-only. Returns one agreement (with its components) by its agreement_id.",
    "parameters": {
        "type": "object",
        "properties": {"agreement_id": {"type": "string"}},
        "required": ["agreement_id"],
    },
}

UPDATE_AGREEMENT_TOOL: Dict[str, Any] = {
    "type": "function",
    "name": "update_agreement",
    "description": (
        "Changes the agreement-level fields: payer_name, partner_name, partner_percent. Only call "
        "after the user approved, with a real agreement_id from find_agreements. Name only the "
        "fields that change."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "agreement_id": {"type": "string"},
            "payer_name": {"type": ["string", "null"]},
            "partner_name": {"type": ["string", "null"]},
            "partner_percent": {"type": ["number", "string", "null"]},
        },
        "required": ["agreement_id"],
    },
}

UPDATE_COMPONENT_TOOL: Dict[str, Any] = {
    "type": "function",
    "name": "update_component",
    "description": (
        "Changes fields of ONE component of an agreement. Only call after the user approved, with a "
        "real agreement_id and component_key from find_agreements. Name only the fields that "
        "change. A completed or cancelled component, or a component of a closed agreement, is "
        "locked and the call fails."
    ),
    "parameters": {
        "type": "object",
        "properties": {"agreement_id": {"type": "string"}, "component_key": {"type": "string"}, **_COMPONENT_FIELDS},
        "required": ["agreement_id", "component_key"],
    },
}

ADD_COMPONENT_TOOL: Dict[str, Any] = {
    "type": "function",
    "name": "add_component",
    "description": (
        "Adds a new component to an existing Active agreement. Only call after the user approved. "
        "Needs a label and an amount or a percent. A component with a trigger_condition starts "
        "Pending, one without starts Active."
    ),
    "parameters": {
        "type": "object",
        "properties": {"agreement_id": {"type": "string"}, **_COMPONENT_FIELDS},
        "required": ["agreement_id", "label"],
    },
}

SET_COMPONENT_STATUS_TOOL: Dict[str, Any] = {
    "type": "function",
    "name": "set_component_status",
    "description": (
        "Moves one component through its lifecycle. action: activate (Pending to Active - the "
        "condition was met), complete (Active to Completed - it was paid), cancel (Pending or Active "
        "to Cancelled), reopen (Completed or Cancelled back to Active). Only call after the user "
        "approved."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "agreement_id": {"type": "string"},
            "component_key": {"type": "string"},
            "action": {"type": "string", "enum": ["activate", "complete", "cancel", "reopen"]},
        },
        "required": ["agreement_id", "component_key", "action"],
    },
}

SET_AGREEMENT_STATUS_TOOL: Dict[str, Any] = {
    "type": "function",
    "name": "set_agreement_status",
    "description": (
        "Closes or reopens a whole agreement. complete: Active components become Completed, Pending "
        "components become Cancelled, already closed components stay. cancel: every component that "
        "is not Completed becomes Cancelled. reopen: only the agreement becomes Active again; its "
        "components stay as the close left them. Only call after the user approved."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "agreement_id": {"type": "string"},
            "action": {"type": "string", "enum": ["complete", "cancel", "reopen"]},
        },
        "required": ["agreement_id", "action"],
    },
}

AGREEMENTS_READ_TOOLS = (FIND_AGREEMENTS_TOOL, GET_AGREEMENT_TOOL)
AGREEMENTS_WRITE_TOOLS = (
    UPDATE_AGREEMENT_TOOL, UPDATE_COMPONENT_TOOL, ADD_COMPONENT_TOOL,
    SET_COMPONENT_STATUS_TOOL, SET_AGREEMENT_STATUS_TOOL,
)
AGREEMENTS_WRITE_TOOL_NAMES = tuple(tool["name"] for tool in AGREEMENTS_WRITE_TOOLS)
