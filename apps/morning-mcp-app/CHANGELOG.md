# Changelog

One entry per release, newest first. Written only by `scripts/cut_release.sh` — never hand-edited
(see `specs/in-progress/034-versioning-release-mgmt/spec.md` REQ-REL-003/REQ-REL-006).

## [0.0.1] - 2026-08-02

Initial versioned release: introduces semantic versioning, cut/deploy tooling, and per-app version observability (Feature 034).

## [0.1.0] - 2026-08-03

first alpha version

## [0.2.0] - 2026-08-05

Version bump to match denidin-app v0.2.0 - no functional changes in this app

## [0.2.1] - 2026-08-05

Fix list_invoices silent truncation beyond 10 items (real pagination + token-budget-aware display truncation); pin mcp<2.0.0 after a breaking upstream API rename (FastMCP -> MCPServer).

## [0.2.2] - 2026-08-07

signed docs

## [0.2.3] - 2026-08-07

bump version, no change

## [0.3.0] - 2026-08-07

Mandatory real client reference for document creation (feature 027): resolve/attach documents by real Morning client_id instead of a bare name; fix Hebrew geresh/apostrophe mismatch breaking client lookup; fix list_invoices number search.

## [0.4.0] - 2026-08-12

resolve_client_name-first architecture, MCP audit logging, and receipt/credit-note payment-date fixes
