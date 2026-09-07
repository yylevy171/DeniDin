# data-model.md — Feature 026 (Client Management)

Extends the existing `Client` entity (`apps/morning-mcp-app/src/denidin_mcp_morning/models.py:58`,
built for Feature 005) — a **Pydantic model** that validates/parses Morning API responses. No
persistence; Morning is the sole source of truth (plan.md Technology Choice). All timestamps UTC.

## Client (read model — unchanged shape, scope note added)

- `id`: string (Morning-assigned UUID)
- `name`: string (required)
- `email`: string (optional, `EmailStr` — pydantic/`email-validator`, already in place)
- `phone`: string (optional — no format constraint on the *read* model; real Morning records may
  contain phone in any format since this field predates Feature 026's normalization)
- `tax_id`: string (optional)
- `address`: string (optional — **still parsed if Morning returns it** on an existing client, but
  never *written* by any tool this feature adds/changes — REQ-CLIENT-013)
- `created_at`: datetime (UTC)

No changes to this model's field definitions. It remains the parsing target for
`search_clients` responses regardless of which fields this feature's tools choose to set.

**`id` is internal-only** (REQ-CLIENT-018): parsed and used internally to target
`update_client`'s `PUT /clients/{id}` call, but MUST NEVER appear in any formatted Hebrew string
returned to the WhatsApp user by `list_clients`, `get_client_details`, `add_client`, or
`update_client`. This corrects existing Feature-005 code: `add_client`'s current return string
(`f"נוצר לקוח חדש: {name} (מזהה: {client_id})"`) leaks it today and must be fixed.

## Client-mutation input validation (new — not a persisted model, applied in `tools.py`)

These rules apply to the **input** side of `add_client`/`update_client`, distinct from the read
model above (a record can exist with data that predates these rules — the rules only gate new
writes):

| Field | `add_client` | `update_client` | Validation |
|---|---|---|---|
| `name` | **required** | optional | non-empty string |
| `email` | **required** | optional | `EmailStr` format (mirrors Morning `errorCode 1102`/`1120`) |
| `phone` | **required** | optional | normalized to Israeli local dashed format (`0XX-XXXXXXX`); reject if it doesn't resolve to a plausible Israeli number |
| `tax_id` | optional | optional | no client-side format check (Morning validates server-side via checksum, `errorCode 1111` — unchanged, not duplicated client-side) |
| `address` | **not accepted** | **not accepted** | out of scope (REQ-CLIENT-013) — not a tool parameter at all |

- `update_client` additionally requires **at least one** of `name`/`email`/`phone`/`tax_id` to be
  present (a call with none is rejected — "nothing to update").
- `update_client`'s *target* is always resolved by name-lookup (see Client Resolution below),
  never a caller-supplied `client_id` (keeps the tool's natural-language surface consistent with
  how `add_client`/`get_client_details` already work).
- **`add_client` does NOT resolve/check for an existing match before creating**
  (analysis 2026-07-29, F2: "try and fail" chosen over a proactive duplicate-check) — it calls
  `client.add_client` directly; whatever Morning's real API does (create a second record, or
  reject as a duplicate) is what happens, and any rejection propagates through the normal
  friendly-error mapping rather than being caught/interpreted specially.

## Client Resolution (new — `_resolve_client_by_name`, shared by `get_client_details`/`update_client`)

Not a data entity, but a shared resolution contract both tools depend on:

- **Input**: a `name` string (from the user's natural-language request).
- **Behavior**: calls `MorningClient.search_clients({"name": name})` — the response's `items` are
  already full records (confirmed via the Postman collection's example), so no follow-up
  GET-by-id call is ever needed.
  - 0 matches → returns a "not found" sentinel (tools map this to a friendly Hebrew message).
  - 1 match → returns that `Client` (parsed via the read model above), including its `id` for
    `update_client` to target.
  - >1 matches → returns an "ambiguous" sentinel carrying the list of candidates (tools map this
    to a Hebrew message listing each candidate's `name` + `tax_id`/`phone`, asking the user to
    be more specific — no mutation is attempted).
- **Never** falls back to "just pick the first match" — REQ-CLIENT-003/007.

## Search payload (new — maps to `POST /clients/search`)

- `list_clients` (no filter, or an optional `name` substring): `{"page": 1}` + `{"name": ...}` if
  given.
- `get_client_details`/`update_client`'s internal lookup: `{"name": name}` (exact resolution
  target, not a listing UX).

Response shape (confirmed via the Postman collection's "Search Clients" example, see
research.md Decision 1): `{"page": int, "total": int, "items": [<client records>], ...}` — only
`items` and `total` are consumed; pagination fields beyond `page 1` are not needed at this
feature's scale (mirrors `list_invoices`' existing single-page assumption).
