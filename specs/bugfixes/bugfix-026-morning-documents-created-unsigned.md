# Bugfix Spec: Every Morning document created via the API is hardcoded as unsigned, blocking email sharing

## Bug ID
bugfix-026-morning-documents-created-unsigned

## Title
All six document-payload builders in `apps/morning-mcp-app`'s `tools.py` hardcode
`"signed": False` when creating a document via Morning's `/documents` (Add Document) API.
Documents created this way cannot be shared by email — Morning refuses with "cannot share a
document that is not digitally signed" — even though the identical document created through
Morning's own UI is signed by default and shares fine.

## Priority
P0 - breaks a core user-facing capability (sharing an invoice/receipt with a client by email)
for every single document this app creates via the API, with no workaround once a document
already exists unsigned (see "Manual sign of existing docs" below). This has presumably been
silently broken since the very first document-creation tool shipped.

## Status
Open - root cause investigated and confirmed (2026-08-06, via Morning's own public API
Postman collection + doc-creation code); human approval of root cause and fix approach given
2026-08-06 ("create a bugfix... lets start on it. this is P0!"). Test-gap analysis next.

## Date Opened
2026-08-06

## Reported By
yaronlev171 (noticed while trying to share a doc created via the API by email in the real
Morning UI - got an error saying the doc isn't digitally signed; docs created manually in the
UI don't have this problem)

## Affected Area
- `apps/morning-mcp-app/src/denidin_mcp_morning/tools.py` - all six document-payload
  builders that send a `signed` field to Morning's Add Document endpoint:
  - `_build_create_invoice_payload` (tax invoice, type 305)
  - `_build_transaction_account_payload` (חשבון עסקה, type 300)
  - `_build_combo_document_payload` (invoice-receipt combo, type 320)
  - `_build_cancellation_payload` (credit note, type 330)
  - `_build_payment_receipt_payload` (receipt, type 400)
  - `_build_combo_closing_payload` (closing invoice-receipt, type 320 closing a type 300)
- Downstream: every MCP tool that calls these builders (`create_invoice`,
  `create_transaction_account`, `create_combo_document`, `create_credit_note`,
  `create_receipt`, `close_transaction_account`, and `update_invoice_status`'s
  paid/cancelled branches) inherits the bug.

## Description
Every document this app creates via Morning's API - invoices, receipts, credit notes,
transaction accounts, combo documents - is created with the Morning API's own `signed` field
explicitly set to `false`. Morning's product (and Israeli tax law's requirement for a
digitally signed invoice to be a legally valid original) treats a "green signature" as
something that must be applied at issuance; an unsigned document is effectively a draft.
Morning's UI blocks emailing/sharing an unsigned document for exactly that reason, and the
same restriction applies over the API - it's not a UI-only quirk.

Documents created directly through Morning's own web UI are signed by default as part of the
normal issuance flow, so they share by email with no problem. Only API-created documents from
this app hit the block, because this app is the one telling Morning not to sign them.

## Root Cause
`tools.py` hardcodes `"signed": False` in all six payload builders (confirmed at
[tools.py:102](../../apps/morning-mcp-app/src/denidin_mcp_morning/tools.py#L102),
[:156](../../apps/morning-mcp-app/src/denidin_mcp_morning/tools.py#L156),
[:257](../../apps/morning-mcp-app/src/denidin_mcp_morning/tools.py#L257),
[:581](../../apps/morning-mcp-app/src/denidin_mcp_morning/tools.py#L581),
[:677](../../apps/morning-mcp-app/src/denidin_mcp_morning/tools.py#L677),
[:746](../../apps/morning-mcp-app/src/denidin_mcp_morning/tools.py#L746)). Traced via `git
log -S` back to the very first CRUD implementation (commit `fc09fff`, Feature 005/US1) and
copied forward unchanged into every later document type added by Features 020/021. No spec,
comment, or commit message documents this as a deliberate choice - it reads like it was
carried over from an early sandbox test fixture and never revisited as new document types
were added.

Confirmed against Morning's own public API documentation
(`specs/done/005-mcp-morning-green-receipt/Green Invoice Public API.postman_collection.json`):
the Add Document endpoint's own example payloads use `"signed": true` in every example but
one (a request explicitly titled "Foreign Currency & Not Digitally Signed", demonstrating
`signed: false` as a deliberate, opt-in alternative - not the default).

### Impact of switching to `signed: true` (assessed before starting the fix)
No functional downside found:
- Morning's `Documents` API group has **no edit/update endpoint at all**, signed or unsigned
  - documents are immutable by design once created either way. Switching to `signed: true`
  removes no capability this app currently has via the API.
- `Close`/`Open Document` (payment-status toggle) and the cancellation/credit-note flow this
  app already implements (issuing a new reversal document that references the original,
  never mutating the original in place) work identically regardless of the `signed` flag.

### Manual sign of existing already-created unsigned documents
No mechanism exists to retroactively sign a document already created unsigned - confirmed via
Morning's API surface (no `sign`/update/patch endpoint anywhere in the `Documents` group) and
consistent with the general rule that a green/digital signature is only legally meaningful if
applied at issuance (it certifies the content hasn't changed since signing; retroactively
adding one would defeat that guarantee). This second point is inferred from documentation and
general guidance, not confirmed via a live Morning API call or a check of the actual Morning
UI - flagging per CONSTITUTION.md's "no unverified third-party assumptions" rule. The
practical remedy for any already-created unsigned documents is to cancel/credit-note them (if
already reported to the tax authority) and reissue as new documents once this bug is fixed.

## Steps to Reproduce
1. As a godfather/admin user, ask DeniDin to create any invoice/receipt/transaction-account
   document via the Morning MCP tools (e.g. `create_invoice`).
2. Open the created document in Morning's web UI.
3. Attempt to share it by email.
4. Observe: "cannot share a document that is not digitally signed" (or equivalent), where the
   same action on a UI-created document works with no error.

## Proposed Fix (approved 2026-08-06)
Change `"signed": False` to `"signed": True` in all six payload builders listed above.
