# Research: Transaction Account Cancellation Mechanism

**Feature**: 056-receipts-without-invoice
**Date**: 2026-08-18
**Purpose**: Resolve spec.md's "Open Questions for `speckit.plan`" — the exact Morning API
mechanism for cancelling a type-300 transaction account with no document created — per
CONSTITUTION's "NO UNVERIFIED THIRD-PARTY ASSUMPTIONS" rule. Confirmed against the real Morning
sandbox (no mocking), plus the authoritative Green Invoice Postman collection
(`specs/done/v0.0.1/005-mcp-morning-green-receipt/Green Invoice Public API.postman_collection.json`).

## Method

1. Read the authoritative Postman collection's full endpoint list and the real (documented)
   response bodies for `GET /documents/statuses` and `POST /documents/{id}/close`.
2. Live sandbox script (`create_transaction_account` → `close_invoice` → `get_invoice` →
   `open_invoice`, repeated across several runs) against `config/config.test.json`'s real
   sandbox credentials, using this app's own existing tools/client code — no new API surface
   invented, no mocking.

## Finding 1: No `/cancel` endpoint exists — only `/close` and `/open`

The full Green Invoice public API (66 endpoints, enumerated from the Postman collection) has
exactly two document-state-mutating endpoints besides document creation: `POST
/documents/{id}/close` and `POST /documents/{id}/open`. There is no `/cancel` endpoint, and no
way to directly set a status via any other call.

`GET /documents/statuses`' real, authoritative Hebrew names (from the collection's cached
example response) are more precise than `models.py`'s existing terse comment suggested:

| Code | Hebrew (authoritative) | Meaning |
|---|---|---|
| 0 | מסמך פתוח | Open document |
| 1 | מסמך סגור | Closed document (paid) |
| 2 | מסמך סומן ידנית כסגור | Document manually marked as closed |
| 3 | מסמך שביטל מסמך אחר | **A document that cancelled another document** (applies to the credit note itself) |
| 4 | מסמך שבוטל | **A document that was cancelled** (applies to the original, once a linked credit note exists) |

Statuses 3 and 4 are **both outcomes of the credit-note flow** (`create_credit_note` /
`_build_cancellation_payload`) — one on each side of that linked pair. Since no endpoint sets
them directly, they are **not reachable without creating a document** — which is exactly what
this feature must avoid for transaction accounts. This rules out 3/4 entirely as a candidate for
"cancel with no document."

**Conclusion**: status **2** ("manually marked as closed", via the existing `close_invoice`) is
the only document-less state-mutation available in the real API. There is no distinct
"abandoned/cancelled without payment" status separate from "closed" — Morning's status
vocabulary does not distinguish *why* a document was manually closed.

## Finding 2: `close_invoice`/`open_invoice` (already-existing `MorningClient` methods) work correctly on a type-300, confirmed live

Live sandbox trace (transaction account created via `create_transaction_account`, doc id
`69f4dc75-ed95-4daf-8f6b-575fd2137e4b`):

- `status` before: `0` (open)
- `client.close_invoice(doc_id)` → re-fetched document: `status: 2`, `linkedDocuments: []`
- The close response's own `id` equals the original document's id — no separate document was
  created (unlike `create_receipt`/`create_combo_document_as_reference`, which return a *new*
  document's id).
- `client.open_invoice(doc_id)` → `status: 0` again. Repeated close→open→close cycles all
  behaved identically and cleanly.
- `get_invoice_details(client, internal_morning_id=doc_id)` (this app's own formatter) on the
  closed (status 2) transaction account produced:
  ```
  ...
  סטטוס: שולם
  ...
  ```
  **"שולם" means "paid."** This is a real, confirmed semantic bug for this feature's purposes —
  `models._MORNING_STATUS_CODES` maps `2 -> "paid"` (reasonable for its original use: a manually
  reconciled tax-invoice payment), but a *cancelled* transaction account was never paid at all.
  Surfacing "paid" to a godfather who just cancelled/abandoned a deal is actively misleading.

**Conclusion**: no new `MorningClient` method is needed — `close_invoice`/`open_invoice` are the
confirmed-correct, already-existing mechanism. **But** the cancellation capability must not
reuse `get_invoice_details`'s existing formatter as-is for this case; it needs its own
confirmation message (or a formatter branch keyed off document type + how it was closed) that
never says "paid" for a cancellation.

## Finding 3: the raw API is NOT idempotent on double-close — the app must self-guard

Live sandbox trace (`close_invoice` called a second time on an already-closed, status-2
document):

```
400 Client Error: Bad Request for url: .../documents/{id}/close
body: {"errorCode":2400,"errorMessage":"לא ניתן לסגור מסמך שאינו פתוח"}
```
("Cannot close a document that is not open.")

This matches the existing pattern already established elsewhere in this app (`create_receipt`,
`create_combo_document_as_reference` both implement their own idempotent no-op checks in
application code, precisely because Morning itself is not assumed to be idempotent) — the new
cancellation capability needs the identical treatment: check the document's current status
first, and short-circuit as a no-op if it's already `2` (or otherwise not `0`/open), never call
`close_invoice` blindly and propagate a raw 400 to the user (REQ-INV-021).

## Finding 4 (operational note, not a spec requirement): the sandbox is flaky around `close_invoice`

Across several live runs, `close_invoice` calls made very shortly (within a few seconds) after
the transaction account's own creation intermittently returned a 400 error (`errorCode: 3000`,
empty message, or the "not open" 2400 above) **even though the mutation had actually already
succeeded** — confirmed by immediately re-fetching the document and finding `status: 2` despite
the client-visible exception. This is consistent with `morning_client.py`'s underlying
`_build_session(retries=3, ...)` transparently retrying the POST at the network layer: the first
attempt lands and closes the document, a retried attempt then correctly gets rejected as
"already closed," and that's what surfaces to the caller. Whoever implements this feature's
tests/tasks should be aware: **a `close_invoice` exception is not proof the close failed** —
always re-fetch and check real status before treating it as an error, and expect this same
sandbox-timing quirk to affect test flakiness (mirrors the already-known
`_fresh_nonexistent_client_name` retry pattern documented in bugfix-028's handoff for a
different, unrelated reason — search-index/propagation lag right after a mutation is a
recurring sandbox characteristic, not unique to this feature).

## Answers to spec.md's Open Questions

1. **Exact Morning mechanism for "cancel with no document"**: `close_invoice` (POST
   `/documents/{id}/close`) — already exists on `MorningClient`, confirmed live to set status
   `0 → 2` on a type-300 with zero documents created and clean reversibility via `open_invoice`.
2. **New MCP tool vs. extending an existing one**: leaning toward a new dedicated tool (working
   name `cancel_transaction_account`), matching Feature 021's precedent of type-specific tools —
   `close_invoice`'s contract (an id, no line items, no payment details) is structurally
   unrelated to every existing `create_*`/`create_combo_document_as_reference` tool's contract,
   so folding it into one of those would be an awkward, differently-shaped branch. Final call
   still belongs to `plan.md`, but this research removes the main uncertainty.
3. **Does `MorningClient` need a new method?**: No — `close_invoice`/`open_invoice` already
   exist and are confirmed correct.

## New implementation-relevant findings (beyond the original Open Questions)

- The cancellation capability must implement its own idempotency guard in application code
  (Finding 3) — Morning's API rejects a redundant close with a 400, it does not no-op silently.
- The cancellation capability must not present Morning's "paid" status language for a
  cancellation (Finding 2) — needs its own confirmation/formatting path, not a reuse of
  `get_invoice_details`'s existing "שולם" output.
- Tests exercising this feature should build in the same short retry-on-lag tolerance already
  used elsewhere in this app's sandbox tests (Finding 4), rather than treating a single
  `close_invoice` exception as a definitive failure.
