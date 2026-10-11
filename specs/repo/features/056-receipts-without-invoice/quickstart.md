# Quickstart: Receipts Without Invoice + Transaction Account Cancellation (Feature 056)

Manual verification scenarios once implementation lands, covering both user stories (US1, US2).
Requires: `apps/morning-mcp-app` running (dev, real sandbox) via its own `run_morning_mcp.sh dev`;
`apps/denidin-app` running dev with a godfather WhatsApp number configured. **Starting either
environment always needs explicit approval — nothing below authorizes that on its own.**

## Prerequisites

- `apps/morning-mcp-app/config/config.dev.json` has real Morning sandbox credentials
  (including `auth_url`, per Feature 053 — confirm this before starting, a missing field there
  fails config load loudly, not silently).
- `apps/denidin-app/config/config.dev.json`'s `mcp` block points at the running Morning server's
  status file, and the sender's WhatsApp number resolves to `godfather` or `admin`.
- A sandbox client named "Danny Cohen" exists (seed via `add_client` first, or reuse one from an
  earlier feature's manual verification).

## US1 — Standalone receipt for a deposit/loan/advance payment (P1)

**Happy path**: send `"קיבלתי פיקדון של 500 שקל מדני כהן, תוציא לי קבלה"` (no invoice request at
all). Expect: a confirmation question (approval gate, unchanged mechanism) → reply "כן" → a
Hebrew receipt confirmation naming the client and amount, with no invoice mentioned or created.
Verify: `MorningClient.get_invoice(<returned id>).type == 400`, `linkedDocumentIds == []`, and
no `income` line in the raw document.

**Advance-payment variant**: send `"דני כהן שילם לי מקדמה של 1000 שקל על עבודה שעוד לא סיימתי,
תוציא קבלה"`. Expect the same standalone-receipt flow.

**Independence from a later invoice**: once the advance-payment receipt above exists, send
`"עכשיו תוציא לדני כהן חשבונית על 1000 שקל בעבור העבודה שסיימתי"`. Expect a normal `create_invoice`
flow, completing without ever referencing the earlier receipt. Verify: the new invoice's
`linkedDocumentIds` does NOT include the earlier receipt's id (REQ-INV-019).

**Unresolved client**: send the same deposit request for a client name that doesn't exist or is
ambiguous. Expect the same refusal/disambiguation behavior every other `create_*` tool already
has — no receipt created.

**Existing behavior unchanged**: repeat any pre-existing `create_receipt`-against-a-real-invoice
scenario from Feature 021/023's own manual verification (e.g. "תסמן את חשבונית מספר X כשולמה") —
must behave identically to before this feature shipped (REQ-INV-016).

## US2 — Cancelling a transaction account creates no document (P2)

Seed an open transaction account first: send `"תוציא לדני כהן חשבון עסקה על 800 שקל"`, approve,
note the returned `internal_morning_id`.

**Cancellation, happy path**: send `"בטל את חשבון העסקה הזה, העסקה לא יצאה לפועל"`. Expect: a
confirmation question → reply "כן" → a confirmation that does **not** say the account was paid
(שולם) — REQ-INV-026. Verify via `MorningClient.get_invoice`: `status == 2`, `linkedDocuments`
unchanged (still `[]`), and zero new documents exist for that client that weren't there before
(no new `create_invoice`/`create_receipt`/`create_credit_note`/`create_combo_document` call
appears in `apps/morning-mcp-app`'s audit log for this turn).

**Idempotency — already cancelled**: repeat the exact same cancellation request. Expect: the
same kind of confirmation, no error, and (checking the audit log) no second `close_invoice` call
was actually made — the app-side no-op guard fired (REQ-INV-021/025).

**Idempotency — already fulfilled**: seed a second open transaction account, fulfill it via
`"סגור את חשבון העסקה הזה, הלקוח שילם"` (routes to `create_combo_document_as_reference`,
creating a real type-320 document), then send the cancellation request against the same
account. Expect: a no-op confirmation, and — critically — the type-320 document created by the
fulfillment must still exist unchanged; cancellation must never contradict a real payment record.

**Wrong document type**: send a cancellation request referencing a real tax invoice's id instead
of a transaction account's. Expect: a clear rejection, and confirm (Hebrew phrasing check) that
it points toward `create_credit_note` as the correct path for a tax invoice — REQ-INV-022.

**RBAC**: from a non-godfather/admin (`client`-role) WhatsApp number, ask to cancel a
transaction account. Expect: no MCP tool available at all, a normal reply, no Morning API call
in logs for that turn — same as every other Morning tool's existing RBAC behavior.

## Cleanup

Documents/clients created during manual verification are sandbox data — no cleanup mechanism is
required (consistent with every other feature's quickstart in this repo).
