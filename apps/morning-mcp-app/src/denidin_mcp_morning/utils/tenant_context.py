"""Per-request tenant id (Feature 055: Multi-Tenancy, contracts/invoicing-capability.md).

Mirrors `utils/correlation.py`'s existing pattern exactly (same file's docstring
explains the rationale for using a `ContextVar` here rather than threading an
extra parameter through every tool/client call): `BearerTokenMiddleware` resolves
which tenant a request's bearer token belongs to and binds it here for the
duration of that request; `server.py`'s tool closures (and, in turn, `audit.py`)
read it back to select that tenant's own `MorningClient` and attribute audit
lines correctly - without changing the public signature of any `tools.*`
function or `MorningClient` method.

Empirically verified (not assumed - CONSTITUTION's "no unverified third-party
assumptions" rule): a `ContextVar` set inside `BaseHTTPMiddleware.dispatch()`
before `call_next()` DOES survive into the downstream FastMCP tool-call handler
in this app's actual installed Starlette/FastMCP/uvicorn versions, including
through the real streamable-HTTP session-handling path (probed live against a
throwaway FastMCP server, 2026-08-17) - this was not a safe assumption to make
without checking, given `BaseHTTPMiddleware`'s well-documented history of
breaking contextvar propagation in some frameworks/versions.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator, Optional

_UNSET: Optional[str] = None

_tenant_id: ContextVar[Optional[str]] = ContextVar("morning_mcp_tenant_id", default=_UNSET)


def current_tenant_id() -> Optional[str]:
    """The tenant id of the request currently in flight, or None outside one
    (single-tenant/legacy shared-secret mode, or a direct `tools.*`/`MorningClient`
    call made outside the MCP boundary - tests, ad hoc scripts)."""
    return _tenant_id.get()


@contextmanager
def tenant_scope(tenant_id: Optional[str]) -> Iterator[Optional[str]]:
    """Bind `tenant_id` for the duration of the block, then restore."""
    token = _tenant_id.set(tenant_id)
    try:
        yield tenant_id
    finally:
        _tenant_id.reset(token)
