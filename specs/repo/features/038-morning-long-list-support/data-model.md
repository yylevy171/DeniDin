# Data Model: Morning Long List Support — Feature 038

**No new entities.** This feature changes only fetch/format behavior in
`list_invoices`, not data shape.

- **Invoice** (`apps/morning-mcp-app/src/denidin_mcp_morning/models.py`):
  unchanged Pydantic model, unchanged fields, unchanged validation. This
  feature changes how many raw Morning documents are validated into
  `Invoice` instances before formatting (all matching documents within the
  fetch cap, instead of only the first page's first 10), not the model
  itself.
- **Morning `/documents/search` response shape** (external, not an app
  entity, confirmed live — research.md Decision 1): `{pageSize, page,
  total, from, to, pages, items, aggregations}`. This feature starts
  reading `total`/`page`/`pages` (previously ignored by `_extract_items`,
  which only reads `items`/`data`) — no schema change on Morning's side,
  just this app choosing to read fields that were always present.
- **Token-budget truncation** (research.md Decision 5, added 2026-08-04):
  not a data entity either — a runtime computation (accumulated `tiktoken`
  token count over already-built `Invoice` formatted blocks) that decides
  how many of an already-fetched, already-validated `Invoice` list to
  include in the reply. No new persisted state, no new model field.
