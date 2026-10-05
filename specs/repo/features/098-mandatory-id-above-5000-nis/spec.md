# Feature 098: Mandatory Client ID for Tax Documents Above the Allocation Threshold

**Feature Branch**: `feature/098-mandatory-id-above-5000-nis`
**Created**: 2026-10-05 (stub, commit 94fbc4f), rewritten via speckit.specify the same day
**Status**: In Progress
**Priority**: P1 (regulatory - documents above the threshold are non-compliant without it)

User stories and acceptance scenarios: **`user-stories.md`** (authoritative).

---

## 1. Background & Goal

Since 1 June 2026, Israel's "חשבוניות ישראל" model requires an allocation number
(מספר הקצאה) on every tax invoice (חשבונית מס) and tax invoice/receipt (חשבונית
מס/קבלה) whose amount **exceeds 5,000 ₪ before VAT**. Without it, the customer cannot
deduct the input VAT. Morning requests the allocation number from the Tax Authority
automatically when it issues the document, as long as the client's record in Morning
holds an identification number (ת.ז / ח.פ / ע.מ).

DeniDin currently issues these documents without ever looking at whether the client
has an ID on file. This feature makes sure a qualifying document is never issued for a
client with no ID: DeniDin asks the user for the ID first, saves it to the client, and
then issues the document.

## 2. Terminology Glossary

| Term | Meaning |
|------|---------|
| **In-scope document** | Morning type **305** (חשבונית מס) or **320** (חשבונית מס/קבלה), however it is created - a fresh document, or a 320 that closes a transaction account (חשבון עסקה). |
| **Allocation threshold** | The amount, **before VAT**, above which an in-scope document needs an allocation number. Currently 5,000 ₪. Configurable, never hard-coded. |
| **Pre-VAT amount** | The document's amount excluding VAT. When the user's amount includes VAT, it is the amount divided by (1 + VAT rate). |
| **Client ID** | The client's identification number in Morning (ת.ז / ח.פ / ע.מ), stored on the client record (`tax_id`). |
| **Valid client ID (format)** | Exactly 9 digits. Morning itself additionally rejects an ID whose check digit is wrong. |
| **Allocation-qualifying document** | An in-scope document whose pre-VAT amount is strictly greater than the allocation threshold. |
| **Backbone** | The flows/capabilities prompt architecture introduced by Feature 063 (`config/prompts/`), replacing `runtime_constitution.md`. |

## 3. Research Findings (verified 2026-10-05)

- **Document types**: only tax invoices and tax invoice/receipts need an allocation
  number; receipts, transaction accounts and credit notes do not. Morning's own guide:
  "חשבונית מס או חשבונית מס-קבלה"; credit notes (חשבונית זיכוי) explicitly not required.
  Source: greeninvoice.co.il/magazine/israel-invoice/.
- **Threshold**: "עסקאות שסכומן **עולה על** 5,000 ₪ לפני מע"מ" from 1 June 2026,
  i.e. strictly greater than 5,000, before VAT. It went 20,000 (2025) → 10,000 (Jan 2026)
  → 5,000 (Jun 2026), so it must be configurable. Sources: agreenstein.co.il, Morning's
  guide above.
- **Morning automation**: Morning requests the allocation number on its own once the
  Tax Authority connection is authorized; the only thing DeniDin must ensure is the
  client's ID is on the client record (PM decision, consistent with Morning's guide).
- **Existing tax-ID support (code, read in full)**: already implemented end to end in
  `apps/morning-mcp-app`:
  - `models.py` `Client.tax_id`, mapped from Morning's `taxId` (fixed and confirmed
    live 2026-07-29).
  - `tools.py` `add_client`/`update_client` accept `tax_id` and send it as `taxId`
    (`_build_add_client_payload`, `_build_update_client_payload`).
  - `formatters.py` `_client_dict` returns `tax_id` from `get_client_details`/`list_clients`.
  - `server.py` exposes `tax_id` on the `add_client`/`update_client` MCP tools.
  - Live sandbox tests cover add, update and read-back
    (`tests/integration/test_morning_sandbox_{add,update,get}_client*`), and record that
    Morning rejects an ID with a bad check digit (errorCode 1111).
  - Document payloads send only `client.id`; Morning fills the rest from the client
    record server-side (confirmed live, Feature 027).

## 4. Requirements

### Functional Requirements

- **REQ-098-01 (Scope)**: The rule applies only to in-scope documents (types 305 and
  320), including a 320 that closes a transaction account. Transaction accounts (300),
  receipts (400) and credit notes (330) are never affected.
- **REQ-098-02 (Threshold)**: A document qualifies when its pre-VAT amount is strictly
  greater than the allocation threshold. When the amount is given VAT-inclusive, the
  pre-VAT amount is derived using the configured VAT rate.
- **REQ-098-03 (Configurable threshold)**: The threshold is configuration in
  `morning-mcp-app` (source of truth), and is also available to `denidin-app` so its
  prompts can state the number. Changing it requires no code change.
- **REQ-098-04 (Ask before approval)**: For a qualifying document whose client has no
  valid client ID, DeniDin asks the user for the client's ID, explaining it is needed for
  the allocation number, **before** presenting any document-approval prompt. No document
  is created.
- **REQ-098-05 (Save and continue)**: When the user supplies a 9-digit ID, DeniDin saves
  it to the client's Morning record and then continues the same document request without
  the user restating it.
- **REQ-098-06 (Invalid ID)**: A reply that is not exactly 9 digits, or that Morning
  rejects, is not saved; DeniDin says what is wrong and asks again. No document is
  created.
- **REQ-098-07 (Hard backstop)**: Independently of the conversation, the Morning
  document-creation tools themselves refuse to create a qualifying document for a client
  with no valid ID, and return a clear refusal the model can act on (ask for the ID).
  Nothing is sent to Morning in that case.
- **REQ-098-08 (Unaffected paths)**: A client that already has a valid ID, or a document
  at or below the threshold, or an out-of-scope document type, behaves exactly as today:
  no question, no extra step.
- **REQ-098-09 (Prompt boundaries)**: The rule is defined in `runtime_constitution.md`
  (scope, when it applies, when it does not), and - once Feature 063 lands - in the
  relevant backbone flows/capabilities as well (see §6).
- **REQ-098-10 (Cancel)**: If the user declines to give an ID, nothing is created and
  the request is dropped; DeniDin does not issue the document anyway.

### Key Entities

- **Client (Morning)**: name, email, phone, `tax_id`. Only `tax_id` matters here.
- **In-scope document request**: client, type (305/320), amount, VAT-inclusive or not,
  currency.
- **Allocation threshold**: one number, in ₪, pre-VAT.

## 5. Success Criteria

- **SC-001**: 100% of 305/320 documents above the threshold issued through DeniDin are
  for clients with an ID on file.
- **SC-002**: Zero extra questions for documents at or below the threshold, for
  out-of-scope document types, or for clients that already have an ID.
- **SC-003**: After the user supplies an ID, the document is issued in the same
  conversation without the user repeating the original request.
- **SC-004**: Changing the threshold value takes effect after a restart with no code
  change.

## 6. Dependencies & Assumptions

- **Feature 063 (backbone)**: not yet merged (`origin/feature/063-refactor-oversized-handlers`).
  Whichever lands second carries the rule into the other: if 098 merges first, 063 must
  port the rule into its flows/capabilities (at least `flow_issue_invoice_for_payment_due`,
  `flow_issue_invoice_receipt_combo`, `flow_issue_payment_received_with_reference_doc`,
  `cap_invoicing_write`, `cap_client_write`); if 063 merges first, 098 adds it there.
- **Assumption - all clients**: the rule applies to every client, business or private
  (PM decision: ID is mandatory, a 9-digit ת.ז is acceptable).
- **Assumption - ID format**: 9 digits is the only local check (PM decision). Check-digit
  validation is left to Morning, which already rejects bad ones.
- **Assumption - VAT rate**: the pre-VAT derivation uses one configured VAT rate.
  ⚠️ `morning-mcp-app`'s existing `default_vat_rate` config is **0.17** in example/dev/prod
  and unused in code; Israel's VAT is 18% since 1 Jan 2025. Fixing that value is a
  config change requiring explicit human approval (to be raised at plan time).
- **Out of scope**: the allocation-number request itself (Morning does it), validating
  that the allocation number was actually received, credit notes, receipts.

## 7. Open Questions

See `user-stories.md` → "Open Questions for PM" (max 3).
