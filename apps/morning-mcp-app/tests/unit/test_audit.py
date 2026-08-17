"""Unit tests for denidin_mcp_morning.audit (bugfix-036; extended Feature 055
Phase 6, tasks.md T024a: every audit line records the resolved tenant_id).

Real `logging` capture via pytest's `caplog` - no mocking of internal code
(CONSTITUTION §I/§V); the only thing "faked" is the log record's data, which is
the actual observable output this module exists to produce.
"""
import logging

from denidin_mcp_morning.audit import log_mutation, log_refusal
from denidin_mcp_morning.utils.tenant_context import tenant_scope


def test_log_mutation_includes_tenant_when_bound(caplog):
    with caplog.at_level(logging.INFO):
        with tenant_scope("tenant-a"):
            log_mutation(
                tool="create_invoice", payload={"amount": 100}, response={"id": "doc-1"},
                client_id="c-1", client_name="Some Client",
            )

    assert "[tenant=tenant-a]" in caplog.text


def test_log_mutation_records_none_when_no_tenant_bound(caplog):
    """Legacy single-shared-secret mode (or a direct call outside the MCP
    boundary): tenant_id is None - still recorded explicitly, not silently
    omitted, so a reader of the log can tell "no tenant context" apart from
    "tenant context field is missing" (a config regression)."""
    with caplog.at_level(logging.INFO):
        log_mutation(
            tool="create_invoice", payload={"amount": 100}, response={"id": "doc-1"},
        )

    assert "[tenant=None]" in caplog.text


def test_log_refusal_includes_tenant_when_bound(caplog):
    with caplog.at_level(logging.WARNING):
        with tenant_scope("tenant-b"):
            log_refusal("create_invoice", "client not found", client_name="Unknown Client")

    assert "[tenant=tenant-b]" in caplog.text


def test_two_tenants_calls_are_distinguishable_in_the_same_log_stream(caplog):
    """The actual point of this requirement: one shared log file/stream, two
    tenants' lines both present and each correctly attributed - not merged,
    not silently defaulting to whichever tenant called first."""
    with caplog.at_level(logging.INFO):
        with tenant_scope("tenant-a"):
            log_mutation(tool="create_invoice", payload={}, response={"id": "doc-a"})
        with tenant_scope("tenant-b"):
            log_mutation(tool="create_invoice", payload={}, response={"id": "doc-b"})

    lines = caplog.text.splitlines()
    tenant_a_line = next(line for line in lines if "doc-a" in line)
    tenant_b_line = next(line for line in lines if "doc-b" in line)
    assert "[tenant=tenant-a]" in tenant_a_line
    assert "[tenant=tenant-b]" in tenant_b_line
