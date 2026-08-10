"""Per-tool-call correlation id, shared between the MCP boundary and the tools.

bugfix-036: the audit trail is written from two layers - `server.py`'s
`_call_with_error_boundary` (which knows the tool name and its caller-facing
arguments) and `tools.py` (which knows the payload actually sent to Morning
and the response it returned). Both must stamp the *same* id so the lines can
be joined when reading the log.

A `ContextVar` carries it between them without threading an extra parameter
through every `tools.*` signature and every `MorningClient` method. This is a
read of an explicitly-set context value, not runtime attribute injection - no
monkey-patching, no globals mutated across calls (CONSTITUTION §XVII). Each
call scopes its own value and resets it on the way out, so a value can never
leak into an unrelated call, and `contextvars` keeps that true per-task under
the async streamable-HTTP server.
"""
from __future__ import annotations

import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

# "-" rather than an empty string so a log line always has a value in the slot,
# even for a direct `tools.*` call made outside the MCP boundary (tests, ad hoc
# scripts) - an unset id is visible as unset rather than as a blank field.
_UNSET = "-"

_correlation_id: ContextVar[str] = ContextVar("morning_mcp_correlation_id", default=_UNSET)


def new_correlation_id() -> str:
    """Mint an id for one tool call."""
    return str(uuid.uuid4())


def current_correlation_id() -> str:
    """The id of the tool call currently in flight, or "-" outside one."""
    return _correlation_id.get()


@contextmanager
def correlation_scope(correlation_id: str) -> Iterator[str]:
    """Bind `correlation_id` for the duration of the block, then restore."""
    token = _correlation_id.set(correlation_id)
    try:
        yield correlation_id
    finally:
        _correlation_id.reset(token)
