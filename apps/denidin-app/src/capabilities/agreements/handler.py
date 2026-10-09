"""Agreements capabilities (Feature 089) - dispatches the `cap_agreements_read` and
`cap_agreements_write` tools onto the unmodified-contract `AgreementsManager`.

Every write is made as actor "whatsapp" and carries the turn's session/message/timestamp so the
ledger events the DB write produces link back to this conversation. Business-rule failures
(locked, not found, illegal transition, validation, ledger busy) come back as `error: <code>:
<reason>` strings the model relays to the user in Hebrew; nothing is retried automatically.
"""
import json
import logging
from typing import Any, Callable, Dict, Optional

from src.constants.error_messages import BACKBONE_CAPABILITY_NOT_CONFIGURED
from src.managers.agreements_manager import AgreementsError
from src.managers.session_manager import SessionManager

logger = logging.getLogger(__name__)

ACTOR = "whatsapp"
_COMPONENT_FIELD_NAMES = (
    "label", "description", "amount", "percent", "percent_base", "trigger_condition", "vat_status", "txn_date",
)


def _ledger_kwargs(backbone, turn_context: Dict[str, Any]) -> Dict[str, Any]:
    session_id: Optional[str] = None
    chat_id = turn_context.get("chat_id")
    session_manager: Optional[SessionManager] = getattr(backbone, "session_manager", None)
    if session_manager is not None and chat_id:
        try:
            session_id = session_manager.get_session(chat_id).session_id
        except Exception:  # noqa: BLE001 - a missing session only loses the back-link, never the write
            logger.warning("agreements: could not resolve the session for chat %r", chat_id, exc_info=True)
    return {
        "session_id": session_id,
        "message_id": turn_context.get("message_id"),
        "message_timestamp": turn_context.get("timestamp"),
    }


def _written(result) -> str:
    agreement, event_ids = result
    return json.dumps({"agreement": agreement, "ledger_event_ids": event_ids}, ensure_ascii=False)


def _fields(args: Dict[str, Any], names) -> Dict[str, Any]:
    return {name: args[name] for name in names if name in args}


def dispatch_direct_tool_call(backbone, tool_name: str, args: Dict[str, Any],
                               turn_context: Dict[str, Any]) -> str:
    """Executes one agreements tool call directly on the ongoing chain."""
    manager = backbone.agreements_manager
    if manager is None:
        return BACKBONE_CAPABILITY_NOT_CONFIGURED
    ledger = _ledger_kwargs(backbone, turn_context)
    handlers: Dict[str, Callable[[], str]] = {
        "find_agreements": lambda: json.dumps(
            {"agreements": manager.find_agreements(args["client_name"])}, ensure_ascii=False),
        "get_agreement": lambda: json.dumps(
            {"agreement": manager.get_agreement(args["agreement_id"])}, ensure_ascii=False),
        "update_agreement": lambda: _written(manager.edit_agreement(
            args["agreement_id"], _fields(args, ("payer_name", "partner_name", "partner_percent")),
            ACTOR, **ledger)),
        "update_component": lambda: _written(manager.edit_component(
            args["agreement_id"], args["component_key"], _fields(args, _COMPONENT_FIELD_NAMES),
            ACTOR, **ledger)),
        "add_component": lambda: _written(manager.add_component(
            args["agreement_id"], _fields(args, _COMPONENT_FIELD_NAMES), ACTOR, **ledger)),
        "set_component_status": lambda: _written(manager.set_component_status(
            args["agreement_id"], args["component_key"], args["action"], ACTOR, **ledger)),
        "set_agreement_status": lambda: _written(manager.set_agreement_status(
            args["agreement_id"], args["action"], ACTOR, **ledger)),
    }
    handler = handlers.get(tool_name)
    if handler is None:
        return f"error: unknown agreements tool {tool_name!r}"
    try:
        return handler()
    except KeyError as exc:
        return f"error: validation: missing required argument {exc}"
    except AgreementsError as exc:
        detail = f" {json.dumps(exc.fields, ensure_ascii=False)}" if exc.fields else ""
        return f"error: {exc.code}: {exc.message}{detail}"
