# Changelog

One entry per release, newest first. Written only by `scripts/cut_release.sh` — never hand-edited
(see `specs/in-progress/034-versioning-release-mgmt/spec.md` REQ-REL-003/REQ-REL-006).

## [0.0.1] - 2026-08-02

Initial versioned release: introduces semantic versioning, cut/deploy tooling, and per-app version observability (Feature 034).

## [0.1.0] - 2026-08-03

first alpha version

## [0.2.0] - 2026-08-05

Group conversation support (no-mention-required replies, no-reply etiquette, group RBAC) and a 1:1 RBAC resolution fix for Morning MCP tool attachment

## [0.2.1] - 2026-08-05

Fix bugfix-024 (recognize native WhatsApp @-mentions of DeniDin's own number by phone, not display name); reorganize billed Morning-MCP E2E test suite by topic and fix import bugs the split introduced.

## [0.2.2] - 2026-08-07

just version bump, no change

## [0.2.3] - 2026-08-07

added mark-as-read, approval מאשר

## [0.3.0] - 2026-08-07

Guide the bot to require a real client record (not just a name) before creating invoices/documents, and to offer adding the client when one doesn't exist yet.

## [0.4.0] - 2026-08-12

Client-name-resolution architecture overhaul, add_client safety fixes, and a full billed/expensive test sweep

## [0.4.1] - 2026-08-13

Group B document approvals (receipt/credit note/combo-document-as-reference) now show the referenced document's real data - client, date, amount, status - before approval, instead of a blank placeholder; internal Morning ids and human-facing document numbers are now structurally distinct throughout the Morning tool contract, fixing a live incident where the model confused the two.

## [0.4.2] - 2026-08-14

WhatsApp typing indicator shown while processing a message (feature 048).

## [0.4.3] - 2026-08-14

WhatsApp interactive buttons (כן/לא) for the document-creation approval gate - a real button tap now resolves a pending approval alongside the existing typed-text path, with a stanza_id-based guard against a stale tap resolving the wrong (superseded) approval.

## [0.5.0] - 2026-08-19

Reminders (Feature 054): create/list/modify/delete reminders via natural Hebrew conversation, godfather/admin only, one-time and recurring, with an approval gate before creation/modification and a scheduled delivery service with a per-reminder delivery target and fallback. Ledger event schema revision (Feature 043 Phase 11): bank/payment-detail fields, a unified reference mechanism, and code-side enforcement of payer_name/VAT rules for bank deposits; plus a new WhatsApp export replay tool ('player') for testing the ledger pipeline against real historical conversations, and real Message identity fields (WhatsApp JID + RBAC role, not a resolved display name). Two real bugs fixed: eliminated a double OpenAI retry layer that could turn a single rate-limited call into a 100+ second wait, and de-duplicated incoming Green API webhook notifications by idMessage (was producing duplicate approval prompts on webhook redelivery).
