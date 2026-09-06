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

## morning-mcp-app v0.4.3 — 2026-08-14

Version sync with denidin-app v0.4.3 - no functional changes to morning-mcp-app in this release.

## morning-mcp-app v0.5.0 — 2026-08-19

Tool-call audit log now includes full read-tool response bodies, not just their length, matching denidin-app's own two-way audit logging added for the reminders feature.

## morning-mcp-app v0.5.1 — 2026-08-21

Feature 056: create_receipt now supports a standalone call with no linked invoice (no VAT line, free-text description); new cancel_transaction_account tool cancels an open transaction account (type 300 only) with no document created as a side effect, and an idempotent no-op if already closed.

## morning-mcp-app v0.5.2 — 2026-08-26

get_invoice_details/list_invoices expose Morning's raw creation_timestamp and gain an opt-in format="json" response shape (Feature 025 Phase 9a), enabling deterministic parsing for denidin-app's accounting document reconciliation sweep

## morning-mcp-app v0.5.3 — 2026-08-27

Version sync with denidin-app v0.5.3 - no functional changes to morning-mcp-app in this release.

## morning-mcp-app v0.5.4 — 2026-09-04

Parse negative-amount documents: Invoice / Payment / LinkedDocument .amount drop their Field(ge=0) lower bound, so real production type-400 receipt-cancellation documents ("ביטול חשבונית מס / קבלה ...", genuinely negative by Morning's own reversal convention) parse instead of raising a validation error - found and confirmed against 15 real prod documents during Feature 062's ledger backfill. Plus: get_invoice_details / format_invoice_details now shows each payment line's method and bank name / branch / account when Morning returns them.

## morning-mcp-app v0.5.4-70 — 2026-09-06

Lockstep version bump for the both-apps 0.5.4-70 deploy — no code change from v0.5.4.
