# Releases

One longer-form section per release, newest first. Written only by `scripts/cut_release.sh` —
never hand-edited (see `specs/in-progress/034-versioning-release-mgmt/spec.md` REQ-REL-004/
REQ-REL-006).

## morning-mcp-app v0.0.1 — 2026-08-02

Initial versioned release: introduces semantic versioning, cut/deploy tooling, and per-app version observability (Feature 034).

## morning-mcp-app v0.1.0 — 2026-08-03

first alpha version

## morning-mcp-app v0.2.0 — 2026-08-05

Version bump to match denidin-app v0.2.0 - no functional changes in this app

## morning-mcp-app v0.2.1 — 2026-08-05

Fix list_invoices silent truncation beyond 10 items (real pagination + token-budget-aware display truncation); pin mcp<2.0.0 after a breaking upstream API rename (FastMCP -> MCPServer).

## morning-mcp-app v0.2.2 — 2026-08-07

signed docs

## morning-mcp-app v0.2.3 — 2026-08-07

bump version, no change

## morning-mcp-app v0.3.0 — 2026-08-07

Mandatory real client reference for document creation (feature 027): resolve/attach documents by real Morning client_id instead of a bare name; fix Hebrew geresh/apostrophe mismatch breaking client lookup; fix list_invoices number search.

## morning-mcp-app v0.4.0 — 2026-08-12

resolve_client_name-first architecture, MCP audit logging, and receipt/credit-note payment-date fixes

## morning-mcp-app v0.4.1 — 2026-08-13

close_transaction_account renamed to create_combo_document_as_reference with real required payment_date/payment_method/bank-detail params (was silently hardcoding today's date) and a shared type-320 payload builder with create_combo_document; invoice_id/original_invoice_id renamed to internal_morning_id/original_internal_morning_id and list_invoices' number filter to document_display_number, fixing a live incident where the model passed a document's display number where the internal id was required.

## morning-mcp-app v0.4.2 — 2026-08-14

Migrated MorningAuth to Morning's real OAuth2 client_credentials token endpoint (feature 053), replacing the deprecated /account/token flow ahead of Morning's stated cutoff.
