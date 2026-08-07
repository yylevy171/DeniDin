# data-model.md — Feature 027 (Mandatory Client Reference for Invoicing)

No new persisted entities and no changes to the existing `Client`/`Invoice` Pydantic models
(`apps/morning-mcp-app/src/denidin_mcp_morning/models.py`) — Morning remains the sole source of
truth, unchanged from Feature 026. This feature changes the **shape of a value already in
transit** (a document's `client` sub-object) and how 6 tools build/consume it.

## Document `client` sub-object — now two shapes in the wild

A Green Invoice document's `client` field, as returned by `POST /documents` or `GET
/documents/{id}`, has always been able to carry either shape server-side; this feature is the
first time this codebase's own tools deliberately produce and rely on both:

| Shape | When it occurs | Produced by |
|---|---|---|
| `{"id": "<uuid>", "name": ..., "phone": ..., "emails": [...]}` (full record, `id` present) | Any document created **on or after** this feature ships, via a Group A tool that resolved a real client, or a Group B tool that preserved an `id` from its original | Group A tools (REQ-INV-002); Group B tools when their original has this shape (REQ-INV-012) |
| `{"name": "..."}` only (no `id`) | Any document created **before** this feature shipped (the old, universal bare-name behavior) | Historical documents only — no tool this feature ships ever produces this shape again |

**Group B tools (`create_credit_note`, `create_receipt`, `close_transaction_account`) must branch
on which shape their linked original has** (`original.get("client", {}).get("id")`):
- Present → build the new document's `client` as `{"self": False, "id": <that id>}` (REQ-INV-012).
- Absent → refuse; create nothing (REQ-INV-013).

No other field of `Client`/`Invoice`/`Document` changes. `client.id` was already a real,
Morning-assigned field these models never needed to declare explicitly for this purpose — Group A
tools pass it straight into a raw payload `dict` (not through a typed model), exactly as
`client_name` was passed through before.

## Client (read model — fully unchanged from Feature 026)

Referenced only via the existing `_resolve_client_by_name` helper (Group A) — no new fields, no
new validation. See `specs/done/026-client-management/data-model.md` for the full existing
definition (`id`, `name`, `email`, `phone`, `tax_id`, `created_at`).

## No new validation rules

Group A introduces no new input validation (still just `client_name: str`, unchanged signature).
Group B introduces no new input validation either (still just `original_invoice_id: str`,
unchanged signature) — the branch on `client.id` presence is a **read-side** check on data already
fetched from Morning, not a new input constraint on what the model may pass in.
