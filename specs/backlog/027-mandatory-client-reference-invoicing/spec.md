# Feature Spec: Mandatory Reference to an Existing Client for Invoice Creation

**Feature ID**: 027-mandatory-client-reference-invoicing
**Priority**: P3 (unset by user — adjust when picked up)
**Status**: Draft - Needs Clarification (not yet started; captured from a scoping decision made
while specifying Feature 026, not yet given its own `/speckit.specify` pass)
**Created**: July 29, 2026

---

**NOTE ON PROCESS**: This is a placeholder spec, not yet through the full `speckit.specify` flow.
It has **no `user-stories.md` yet** — per METHODOLOGY §I/§II this means it is **not approved and
not ready for `/speckit.plan`**. When this feature is picked up, run `/speckit.specify` properly
against the Problem Statement below (or a refined version of it) to produce a compliant `spec.md`
+ mandatory `user-stories.md`, then proceed through `/speckit.clarify` as normal.

---

## Problem Statement

Today, `apps/morning-mcp-app`'s invoice-creation tools (`create_invoice`, `create_credit_note`,
`create_receipt`, `create_combo_document`, `create_transaction_account`) accept a **free-text
client name** and pass it straight through to the Green Invoice API — there is no requirement
that the name correspond to an actual client record created via `add_client` (Feature 026, once
built) or otherwise already known to Morning. This risks: typos silently creating invoices
against a misspelled/wrong "client" that Green Invoice may auto-create or reject inconsistently,
no reuse of the client lookup/disambiguation behavior Feature 026 introduces for
`list_clients`/`get_client_details`, and no single source of truth for "who is this invoice
actually for."

This feature would make referencing an **existing** client record **mandatory** when creating any
invoice/document — i.e., invoice creation should resolve the named client via the same lookup
Feature 026 uses (list/get, with disambiguation on multiple matches), and refuse or prompt to
create the client first if no match is found, rather than silently passing a bare string to the
Green Invoice API as it does today.

## Explicit Decision from Feature 026's Scoping (2026-07-29)

- Feature 026 (Client Management: list/view/add/update) deliberately does **NOT** touch
  invoice-creation tools' client-referencing behavior — that stays exactly as-is in 026.
- The user explicitly asked for this to be split into its **own** feature, to be scoped and
  clarified separately, rather than bundled into 026.
- This feature depends on Feature 026 existing first (needs `list_clients`/`get_client_details`
  lookup + disambiguation logic to reuse), so it should not be picked up before 026 ships.

## Open Questions for `/speckit.clarify` (not yet resolved)

- If the named client doesn't exist yet, should invoice creation: (a) fail with a friendly
  "client not found, add them first" message, (b) prompt the user to create the client inline
  (reusing Feature 026's now-approval-gated `add_client` flow) before proceeding with the
  invoice, or (c) something else?
- Does this apply to **all** document-creation tools (`create_invoice`, `create_credit_note`,
  `create_receipt`, `create_combo_document`, `create_transaction_account`) uniformly, or only
  `create_invoice`?
- Interaction with Feature 022's approval gate: if client-creation now happens inline mid
  invoice-flow (option b above), does the user confirm the client creation and the invoice
  creation separately (two approval turns) or as one combined confirmation?
- Does ambiguous client-name matching during invoice creation block the invoice entirely until
  resolved, or should Morning's own name-matching (if any) be trusted as a fallback?

## Out of Scope (for this placeholder note)

- Nothing implemented yet — this file exists solely to preserve the decision and problem
  statement so it isn't lost. Full scoping happens at pickup time via `/speckit.specify`.
