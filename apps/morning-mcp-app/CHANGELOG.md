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
