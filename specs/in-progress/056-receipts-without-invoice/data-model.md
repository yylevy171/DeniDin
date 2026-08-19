# data-model.md — Feature 056 (Receipts Without Invoice + Transaction Account Cancellation)

No new persisted entities, no new Pydantic models, and no changes to `Client`/`Invoice`
(`apps/morning-mcp-app/src/denidin_mcp_morning/models.py`) — Morning remains the sole system of
record. This feature adds one new *shape* of document payload (a standalone receipt) and one new
*state transition* (transaction-account cancellation) that this codebase's tools didn't
previously produce.

## New payload shape: standalone receipt (type 400, no linked original)

Today's only type-400 receipt shape (`_build_payment_receipt_payload`) always carries
`linkedDocumentIds: [<original id>]` and mirrors the original's amount/currency/lang. The new
standalone shape has no original to mirror:

| Field | Standalone shape | vs. existing payment-receipt shape |
|---|---|---|
| `type` | `400` | unchanged |
| `linkedDocumentIds` | `[]` (always empty) | was `[<original id>]` |
| `income`/VAT line | **absent entirely** | was absent too (receipts never carried one) — no change here, confirmed by re-reading `_build_payment_receipt_payload`; noted explicitly in spec.md REQ-INV-017 since a transaction-account payload's absence of a VAT line was the closer mental model used during clarification |
| `client` | `{"self": False, "id": <resolved_client.id>}` — from `resolve_client_name`/`_require_resolved_client`, the same architecture every other `create_*` tool uses | was derived from the *original's* linked client (`_extract_linked_client_id(original)`) |
| `description` | caller-supplied free text (REQ-INV-018 — model composes it, e.g. "פיקדון", "החזר הלוואה", "מקדמה על חשבון...") | was a generated string referencing the original's number |
| `payment` | `[{"type": 1, "price": amount, "date": <validated payment_date>}]` | same shape, same `_validate_payment_date` reuse |

**Which shape a `create_receipt` call produces is decided entirely by whether
`original_internal_morning_id` is `None`** — there is no separate tool, no separate MCP contract
name (Clarification Q1). See `contracts/create_receipt.json` for the full updated schema.

## New state transition: transaction account cancellation (type 300 only)

| From status | Action | To status | Document created? |
|---|---|---|---|
| `0` (open) | `cancel_transaction_account` → `MorningClient.close_invoice` | `2` (manually closed) | **None** — confirmed live, `research.md` |
| `2` (already closed/cancelled) | `cancel_transaction_account` again | `2` (unchanged) | None — app-side idempotent no-op (REQ-INV-021/025), never calls `close_invoice` again |
| `1` (closed via a linked payment document — i.e. already fulfilled via `create_combo_document_as_reference`) | `cancel_transaction_account` | `1` (unchanged) | None — same idempotent no-op path; cancellation must never contradict a real payment document that already exists |
| anything other than type `300` | `cancel_transaction_account` | rejected, `ValueError` | None — REQ-INV-022, same pattern as `create_receipt`'s type-305-only guard |

Morning's own status vocabulary does not distinguish "closed because cancelled/abandoned" from
"closed because someone paid it by hand" — both are status `2`. This app's confirmation text for
a cancellation (REQ-INV-026) is therefore the only place that distinction is recorded; nothing
about it is persisted in Morning itself, by design (this is exactly the document-less outcome
the feature asks for).

## No new validation rules beyond what's reused

- Standalone-receipt path: `client_name`/`name_resolved` validation is 100% reused from
  `_require_resolved_client` (already shared by `create_invoice`/`create_transaction_account`/
  `create_combo_document`) — no new validation function.
- `payment_date` validation: 100% reused from `_validate_payment_date` (already shared by
  `create_receipt`'s existing path, `create_combo_document`, `create_transaction_account`).
- Cancellation's only new check is the type-300-only guard (mirrors `create_receipt`'s existing
  type-305-only guard almost verbatim) and the idempotency short-circuit (mirrors
  `create_receipt`'s/`create_combo_document_as_reference`'s existing already-closed no-op
  pattern) — no genuinely new validation logic, both are direct copies of an existing pattern
  applied to a new tool.
