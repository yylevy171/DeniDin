# User Stories: Reference-Linked Combo Document Creation

**Feature ID**: 023-reference-linked-document-creation
**Created**: July 29, 2026

Per METHODOLOGY.md §I, these stories trace complete end-to-end flows from
external entry point (a WhatsApp message from a godfather/admin) through
system processing to the Morning API and back to the user's response.

---

## US1 (P1): Close a transaction account with a full-amount combo document, by direct request

**Given** a godfather/admin user, in a WhatsApp conversation with DeniDin, references an existing type-300 ("חשבון עסקה") Morning document by its number or a name/date the model can resolve to one
**When** the user asks to close/settle it — whether phrased directly ("תפיק חשבונית מס/קבלה שסוגרת את המסמך הזה") or as a status change ("תסגור לי את חשבון העסקה מספר 4021 בתשלום מלא", "סמן את זה כשולם") — there is no separate `update_invoice_status` tool; the model itself resolves the target's real type (via `get_invoice_details`) and always calls `close_transaction_account` directly once it determines the original is type 300
**Then** DeniDin's model selects the new combo-linking tool, passing the resolved original document's id
**And** the tool fetches the original document from Morning, builds a type-320 combo payload with `linkedDocumentIds` referencing it, for the original's full amount
**And** Morning creates the new linked document and returns its number
**And** DeniDin replies in Hebrew confirming the new combo document's number and that it closes the referenced transaction account

**Router/Dispatcher Requirement**: The new tool must be registered with the FastMCP server (`server.py`) alongside the existing `create_combo_document`/`create_credit_note`/`create_receipt` tools so OpenAI's Responses API can discover and invoke it over the existing MCP tunnel — no new routing layer in `denidin-app` itself (the existing godfather/admin RBAC gate on MCP tool attachment, per `ai_handler.py`, already covers this).

**Acceptance Criteria**:
- Tool call includes the resolved original document's Morning id
- Resulting payload has `type=320` and `linkedDocumentIds=[original_id]`
- Full-amount case: line items/amount mirror the original (no amount override passed)
- Confirmation message names both the new document's number and the original's number

---

## US2 (P2): Close a transaction account with a partial-amount combo document

**Given** a godfather/admin user references an existing type-300 document that is only partially being paid now
**When** the user asks to close/settle it for a specific partial amount (e.g. "תסגור חלק מחשבון העסקה מספר 4021, 500 שקל")
**Then** the tool accepts an optional `amount` override, defaulting to the original's full amount when omitted (matching `create_receipt`'s existing partial-payment pattern)
**And** the resulting type-320 payload reflects the partial amount, not the original's full total
**And** the confirmation message states the partial amount actually recorded, distinct from the original document's full amount

**Acceptance Criteria**:
- `amount` parameter is optional; omitting it reproduces US1's full-amount behavior exactly
- Providing `amount` produces a payload with that amount, not the original's total
- No regression to `create_combo_document`'s existing standalone (no-reference) behavior — that tool is unchanged and still creates a brand-new, unlinked type-320 document when no original is referenced

---

## US3 (P2): Referencing a non-type-300 document is rejected, not silently miscreated

**Given** a godfather/admin user asks to close/link a combo document to an existing document that is NOT type 300 (e.g. a type-305 tax invoice, which is instead closed by `create_receipt`)
**When** `close_transaction_account` is invoked with that document's id
**Then** the tool raises a clear error (not a silently-wrong document type) naming the unsupported original type
**And** DeniDin surfaces this as a friendly, non-crashing message to the user (CONSTITUTION.md §X error format), not a stack trace

**Acceptance Criteria**:
- Original document type != 300 → `ValueError` (or equivalent) naming the unsupported type, no Morning document created
- This case should be rare in practice: the model is expected to resolve the original's real type itself (via `get_invoice_details`) *before* choosing which tool to call — this is the deterministic backstop for when it gets that wrong or the type changed between resolution and the call

---

## US4 (P1): "Mark as paid" phrasing resolves to the correct direct tool, not a status-update tool

**Given** a godfather/admin user asks to mark an existing invoice as paid, using status-change phrasing ("סמן את החשבונית כשולמה", "היא שילמה") rather than naming a document type
**When** DeniDin processes the request
**Then** there is no `update_invoice_status` tool to call — the model must first resolve which real document is meant (via `list_invoices`/session memory, per existing invoice-resolution rules) and fetch its type (via `get_invoice_details`)
**And** based on the resolved type, the model calls `create_receipt` (type 305 original) or `close_transaction_account` (type 300 original) directly — never guessing the type from conversation phrasing alone
**And** DeniDin replies confirming the new linked document, in the same style as a direct "תפיק לי קבלה" request

**Acceptance Criteria**:
- No `update_invoice_status` tool exists in the MCP server's tool list
- The reply is indistinguishable in content/quality from the equivalent direct-request phrasing (US1 of this doc, or 021's `create_receipt` stories) — only the user's own wording differs
- If the model cannot determine the original's type with confidence, it asks the user rather than guessing (see US7)

---

## US5 (P1): "Cancel" phrasing resolves directly to create_credit_note

**Given** a godfather/admin user asks to cancel an existing invoice ("בטל את החשבונית", "תבטל את זה")
**When** DeniDin processes the request
**Then** the model resolves the target document (as above) and calls `create_credit_note` directly, for the full amount (no override) — functionally identical to the old `_cancel_invoice` internal helper, just reached without an `update_invoice_status` indirection
**And** DeniDin replies confirming the new credit note and what it cancels

**Acceptance Criteria**:
- Cancellation remains a fully supported, ordinary action (per existing constitution guidance) — removing `update_invoice_status` must not make this request type harder or less reliable
- No new tool needed for this story — `create_credit_note` (021) already covers it

---

## US6 (P2): "Mark as unpaid" / payment reversal is explicitly refused, not attempted

**Given** a godfather/admin user asks to reverse a payment or "mark as unpaid" an already-paid document
**When** DeniDin processes the request
**Then** the model does not attempt any tool call for this — there is no document-creation action that reverses a payment (Morning has no reversal mechanism for a receipt-based payment)
**And** DeniDin explains this plainly and suggests the actual supported alternative if relevant (e.g. issuing a credit note if the intent is really "this shouldn't have been charged")

**Acceptance Criteria**:
- No tool call is made for a pure reversal request
- The refusal is a friendly, clear explanation (CONSTITUTION §X), not a generic error

---

## US7 (P2): The model asks the user when VAT-inclusion or the target document is genuinely ambiguous

**Given** a godfather/admin user asks to close a transaction account, or create/close any document where VAT-inclusion isn't stated
**When** DeniDin cannot determine VAT-inclusion (or which document is meant) with confidence from the conversation or a tool result
**Then** the model asks the user directly (e.g. "האם כולל מע\"מ?") rather than silently defaulting or guessing
**And** proceeds using the user's answer once given

**Acceptance Criteria**:
- `close_transaction_account` exposes a `vat_included: bool = True` parameter (the code still needs *some* value to call the Morning API with) — the determinism requirement is on the model's decision of what value to pass and when to ask first, not a change to this default itself
- Constitution wording explicitly instructs asking over guessing for this and analogous ambiguous cases

---

## US8 (P1): Duplicate document creation is prevented by a deterministic pre-check, not assumed

**Given** a godfather/admin user asks to mark something paid (or otherwise create a linked document) that may already have a linked receipt/combo/credit note
**When** DeniDin processes the request
**Then** the model calls `get_invoice_details` on the target first and checks whether the relevant linked document already exists
**And** if it does, DeniDin reports the existing state instead of creating a duplicate document
**And** if it does not, the model proceeds to call the appropriate create/close tool

**Acceptance Criteria**:
- This is a constitution-level (model-behavior) requirement, not a code-level guard — verified live that Morning itself does not reject a duplicate receipt against an already-paid invoice, so nothing in the tools themselves prevents this; the check must happen before the tool call
- Applies to `create_receipt`, `close_transaction_account`, and `create_credit_note` alike

---

## Out of Scope (explicitly, per spec.md's re-scoping)

- Non-payment reference/linking use cases (quotes, general "based on the old one" documents)
- Any change to `create_invoice`, `create_transaction_account`, `create_credit_note`, or `create_receipt`'s own payload-building logic (only their dispatch changes)
- A general N-to-N "link any two documents" mechanism
