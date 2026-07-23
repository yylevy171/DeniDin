# Feature 017 — MCP Morning Receipt Parsing (DEFERRED / future)

**Priority**: P2 (Medium)
**Status**: Deferred — not scheduled. Placeholder only.
**Origin**: Split out of Feature 005 (`specs/done/005-mcp-morning-green-receipt/`)
on 2026-07-08 to keep 005 scoped to the 8-tool **invoice-management** MCP server.
**Moved**: `specs/in-definition/` → `specs/backlog/` on 2026-07-24 — still no `spec.md`/
`plan.md`/`tasks.md`, so it isn't clarified/ready-for-planning yet, but `in-definition/` is
reserved for specs with open clarifications, and this one has no spec to clarify at all.

## What this is

A separate, future MCP product for Morning's **file-upload + receipt-parsing** flow —
distinct from 005's invoice CRUD. It centers on uploading a receipt/expense file to
Morning, receiving parsed expense-draft data back, and verifying asynchronous webhook
callbacks (HMAC signature + canonicalization + replay window).

During the 005 validation pass this product's contracts had leaked into the 005 folder
and its `tasks.md`, creating two contradictory tool sets in one feature. Those contracts
were relocated here to preserve them without polluting 005.

## Contents

`contracts/` — draft tool/endpoint schemas carried over from the original 005 drafts:

- `authorize.json` — partner/API-key authorization
- `upload_file.json` — request a presigned file-upload URL
- `receipt_parse.json` — submit an uploaded receipt for parsing
- `get_status.json` — poll parse/expense-draft status
- `list_receipts.json` — list parsed receipts / expense drafts
- `webhook.json` — inbound `expense-draft/parsed` webhook (HMAC-verified)
- `health.json`, `metrics.json` — service health/observability endpoints

## Not started

No `spec.md` / `plan.md` / `tasks.md` / `user-stories.md` yet. When this feature is picked
up, author those artifacts via the SpecKit pipeline (`speckit.specify` → …) per
`.github/METHODOLOGY.md`, and reconcile the drafts above against the current Morning
file-upload and webhook APIs (see the canonicalization notes that were kept with 005's
history under `specs/archive/005-mcp-morning-green-receipt/`).
