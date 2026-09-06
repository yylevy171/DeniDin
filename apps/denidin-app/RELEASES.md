# Releases

One longer-form section per release, newest first. Written only by `scripts/cut_release.sh` —
never hand-edited (see `specs/in-progress/034-versioning-release-mgmt/spec.md` REQ-REL-004/
REQ-REL-006).

## denidin-app v0.0.1 — 2026-08-02

Initial versioned release: introduces semantic versioning, cut/deploy tooling, and per-app version observability (Feature 034).

## denidin-app v0.1.0 — 2026-08-03

first alpha version

## denidin-app v0.2.0 — 2026-08-05

Group conversation support (no-mention-required replies, no-reply etiquette, group RBAC) and a 1:1 RBAC resolution fix for Morning MCP tool attachment

## denidin-app v0.2.1 — 2026-08-05

Fix bugfix-024 (recognize native WhatsApp @-mentions of DeniDin's own number by phone, not display name); reorganize billed Morning-MCP E2E test suite by topic and fix import bugs the split introduced.

## denidin-app v0.2.2 — 2026-08-07

just version bump, no change

## denidin-app v0.2.3 — 2026-08-07

added mark-as-read, approval מאשר

## denidin-app v0.3.0 — 2026-08-07

Guide the bot to require a real client record (not just a name) before creating invoices/documents, and to offer adding the client when one doesn't exist yet.

## denidin-app v0.4.0 — 2026-08-12

Client-name-resolution architecture overhaul, add_client safety fixes, and a full billed/expensive test sweep

## denidin-app v0.4.1 — 2026-08-13

Group B document approvals (receipt/credit note/combo-document-as-reference) now show the referenced document's real data - client, date, amount, status - before approval, instead of a blank placeholder; internal Morning ids and human-facing document numbers are now structurally distinct throughout the Morning tool contract, fixing a live incident where the model confused the two.

## denidin-app v0.4.2 — 2026-08-14

WhatsApp typing indicator shown while processing a message (feature 048).

## denidin-app v0.4.3 — 2026-08-14

WhatsApp interactive buttons (כן/לא) for the document-creation approval gate - a real button tap now resolves a pending approval alongside the existing typed-text path, with a stanza_id-based guard against a stale tap resolving the wrong (superseded) approval.

## denidin-app v0.5.0 — 2026-08-19

Reminders (Feature 054): create/list/modify/delete reminders via natural Hebrew conversation, godfather/admin only, one-time and recurring, with an approval gate before creation/modification and a scheduled delivery service with a per-reminder delivery target and fallback. Ledger event schema revision (Feature 043 Phase 11): bank/payment-detail fields, a unified reference mechanism, and code-side enforcement of payer_name/VAT rules for bank deposits; plus a new WhatsApp export replay tool ('player') for testing the ledger pipeline against real historical conversations, and real Message identity fields (WhatsApp JID + RBAC role, not a resolved display name). Two real bugs fixed: eliminated a double OpenAI retry layer that could turn a single rate-limited call into a 100+ second wait, and de-duplicated incoming Green API webhook notifications by idMessage (was producing duplicate approval prompts on webhook redelivery).

## denidin-app v0.5.1 — 2026-08-21

Feature 056: standalone receipts (no linked invoice, no VAT line) and transaction-account cancellation via natural conversation, with zero documents created as a side effect and an idempotent no-op if already closed; approval prompt for cancellation now shows the real account/client data instead of a generic message. Bugfix-040: reminder approval text now translates RRULE weekday codes to Hebrew instead of showing raw English BYDAY codes.

## denidin-app v0.5.2 — 2026-08-26

Accounting document reconciliation completes with machine-readable capture (Feature 025 Phase 9) and natural-language ledger event querying ships (Feature 044) - AI can now look up and reason over past fee agreements/payments/reconciled documents via a new RBAC-gated query tool, with a ledger-as-cache-over-Morning fallback rule

## denidin-app v0.5.3 — 2026-08-27

Feature 061: new standalone prod-ledger-backfill operator tool (apps/prod-ledger-backfill/) for populating prod's ledger with pre-existing Morning documents before the reconciliation scheduler is ever enabled there - a real, full dev-environment backfill (~4,067 documents, Jul-Aug 2026) completed and verified; the actual prod run itself deferred to Feature 062. Also adds SCHEMA_VERSION_HISTORY plus import-time verification to ledger_event_manager.py, closing the ungoverned schema-version-bump gap. Bugfix-045: add_client no longer re-blocks after the user explicitly confirms a new client, with a corrected scope limit so a bare 'add new client' request never silently skips the near-duplicate disclosure/ask step, plus two related tool-family misclassification fixes (ledger event capture, reminder creation) for the same confirmation reply.

## denidin-app v0.5.4 — 2026-09-04

Accounting-reconciliation sweep reliability: bugfix-047 gives the sweep its own 300s OpenAI timeout (was inheriting the 30s conversational-turn ceiling and timing out once the sandbox held ~13+ in-window documents), bugfix-048 switches its dedup key to (date, display_number) so already-captured Morning documents are no longer re-flagged as anomalies after every app restart. Also: prod Morning ledger backfill completed from 2025-09-01 (Feature 062), August 2026 ledger audit findings applied to prod (Feature 065), parallel sanity test sweep (Feature 075), and cross-app sanity-suite stabilization (Feature 059).

## denidin-app v0.5.4-70 — 2026-09-06

Rolling 14-day short-term memory window with nightly daily-summary roll; retires 24h session expiry and the hourly cleanup thread.
