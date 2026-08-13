"""Audit trail for Morning document/client mutations (bugfix-036).

Before this module, `morning-mcp-app` - the component that actually creates tax
documents - logged nothing on the success path: only raised exceptions reached
the log, via `errors.friendly_error_message`. Documents 100012-100015 and 90195
were all created through this server during the 7-9 Aug 2026 production window
and none of them appears in its log; reconstructing what was sent to Morning was
only possible from `denidin-app`'s logs, as a side effect of its logging of
OpenAI responses. That is an accident, not an audit trail.

What is recorded here, per the bugfix's Expected section: correlation id, tool
name, resolved client id and name, the payload sent, the response received
(including the document number and Morning's own computed total), and the
outcome - enough to answer "what did we send Morning, and what did it return?"
from this app's log alone.

Scope: mutating tools only (document creation, client create/update). Read tools
are covered by the boundary lines in `server.py`, deliberately without their
response bodies - a `list_invoices` result can carry 100 documents and would
bury the mutations this trail exists to preserve.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from .utils.correlation import current_correlation_id
from .utils.logger import get_logger

logger = get_logger(__name__)

# Keys Morning returns on a created document that a reader of this log will
# actually want - notably `total`, Morning's OWN computed total, which is the
# number the customer sees and is not necessarily the amount that was requested
# (bugfix-028 A4). The full response is logged too; this is the at-a-glance
# summary in front of it.
_DOCUMENT_SUMMARY_KEYS = ("id", "number", "total", "status", "type")


def _summarize(response: Any) -> Dict[str, Any]:
    """Pull the interesting document fields out of a Morning response."""
    if not isinstance(response, dict):
        return {}
    return {key: response[key] for key in _DOCUMENT_SUMMARY_KEYS if key in response}


def log_mutation(
    tool: str,
    payload: Any,
    response: Any,
    client_id: Optional[str] = None,
    client_name: Optional[str] = None,
) -> None:
    """Record one completed mutation against Morning.

    Args:
        tool: the MCP tool name this call came in as.
        payload: the request body actually sent to Morning.
        response: the parsed response body Morning returned.
        client_id: resolved Morning client id, when the tool resolved one.
        client_name: the client name as resolved/normalized, when known.
    """
    logger.info(
        "[corr_id=%s] AUDIT %s OK client_id=%s client_name=%r document=%r payload=%r response=%r",
        current_correlation_id(),
        tool,
        client_id,
        client_name,
        _summarize(response),
        payload,
        response,
    )


def log_refusal(tool: str, reason: str, **context: Any) -> None:
    """Record a mutation that was deliberately NOT performed.

    The three failed `create_transaction_account` attempts for
    הסתדרות כללית חדשה left no trace at all precisely because a refusal is not
    an exception: the resolution helper of the day (`_resolve_client_for_
    document_creation`, since superseded by `_require_resolved_client` -
    client-name-resolution architecture fix, 2026-08-12) returned a friendly
    message and the tool returned it. A refusal is a decision the server made
    about a document, so it belongs in the same trail as the documents it did
    create.
    """
    logger.warning(
        "[corr_id=%s] AUDIT %s REFUSED reason=%s context=%r",
        current_correlation_id(),
        tool,
        reason,
        context,
    )
