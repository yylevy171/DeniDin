# Contract: denidin-app Agreements API

Served by `apps/denidin-app/src/services/agreements_api.py` (Starlette). Consumed only by
`apps/webapp/backend`. JSON in, JSON out, UTF-8.

## Common

- **Auth**: `Authorization: Bearer <config.agreements_api.auth_token>` on every route except
  `GET /is_alive`. Missing or wrong token: `401 {"error":{"code":"unauthorized"}}`.
- **Actor**: every write carries `"actor": "webapp"` in the body (the bot never uses HTTP); `DELETE` carries it as the query parameter `?actor=webapp`. Any
  other value: `422 invalid_actor`.
- **Error shape**: `{"error": {"code": "<snake_case>", "message": "<human text>", "fields": {...}}}` (`fields` only for `validation`).
- **Codes**: `404 not_found`, `409 locked` (write to a Completed/Cancelled component or to a
  component of a non-Active agreement), `409 illegal_transition`, `422 validation` (with
  `fields: {name: reason}`), `401 unauthorized`, `503 ledger_busy` (human decision 2026-10-09: event ids allow
  at most 10 `הסכם` events per minute; a write needing more free slots than remain is refused whole,
  nothing is written, and the caller retries in a minute). A ledger failure AFTER a committed DB write
  is out of scope, logged only.
- **Writes return** `{"agreement": <full agreement with components>, "ledger_event_ids": [...]}`. A save that changes nothing returns `200` with the
  unchanged state, `ledger_event_ids: []`, and creates no revision.
- **Last write wins**: no `If-Match`, no versions. Writes are serialized.

## Agreement JSON

```json
{
  "agreement_id": "1026-ישראל_ישראלי-ערעור",
  "title": "ערעור",
  "client_name": "ישראל ישראלי",
  "payer_name": null,
  "partner_name": "עו״ד כהן",
  "partner_percent": 25,
  "status": "Active",
  "components": [
    {
      "component_key": "<uuid hex, immutable, used in URL paths>", "component_id": "<ledger-style slug>",
      "origin_event_id": "<ledger event id or null>", "label": "ריטיינר", "description": "...",
      "amount": 5000, "percent": null, "percent_base": null,
      "trigger_condition": null, "vat_status": "לא כולל מע״מ", "txn_date": "2026-10-01",
      "status": "Active", "locked": false
    }
  ]
}
```

`locked` is computed server-side and is the single source of truth for the UI's disabled state.

## Routes

| Method + path | Purpose | UAT |
|---|---|---|
| `GET /is_alive` | liveness, no auth | quickstart |
| `GET /agreements?client_name=<official name>` | all agreements of a client, with components | 1.1, 1.2, 1.4 |
| `GET /agreements/{agreement_id}` | one agreement | 1.2 |
| `GET /agreements/totals` | `{client_name: sum of non-Cancelled component amounts}` for all clients | 6.1 |
| `GET /agreements/{agreement_id}/revisions` | chronological revisions, each `{revision_id, created_at, actor, action, component_key, snapshot, changed}` | 4.1 |
| `POST /agreements` | create agreement + >=1 component | 2.4 |
| `PATCH /agreements/{agreement_id}` | edit `payer_name`, `partner_name`, `partner_percent` only | 2.1 |
| `POST /agreements/{agreement_id}/status` | body `{"action": "complete"\|"cancel"\|"reopen"}`, cascades per data-model.md | 3.5, 3.6 |
| `POST /agreements/{agreement_id}/components` | add a component (default status per UAT 3.1) | 2.3 |
| `PATCH /agreements/{agreement_id}/components/{component_key}` | edit component fields (`label`, `description`, `amount`, `percent`, `percent_base`, `trigger_condition`, `vat_status`, `txn_date`) | 2.2, 2.2b |
| `POST /agreements/{agreement_id}/components/{component_key}/status` | body `{"action": "activate"\|"complete"\|"cancel"\|"reopen"}` | 3.2-3.4, 3.6 |
| `DELETE /agreements/{agreement_id}/components/{component_key}` | soft delete (`is_active = 0`) + `ביטול` ledger event | 2.5 |
| `DELETE /agreements/{agreement_id}?actor=webapp` | **API-only** soft delete of a whole agreement (`is_active = 0` on the agreement, its components and its revisions); writes **no** ledger events; `200 {"deleted": true, "agreement_id": ...}`, `404` if absent or already deleted. Neither the UI nor WhatsApp exposes it - it exists for test cleanup and admin use. | tests |

Request validation: `POST /agreements` requires `client_name`, `title` (the agreement id is derived as `MMYY-client-title`, an id already held by an ACTIVE agreement is `422`; the id of a deleted agreement can be reused) and a non-empty `components` array; component labels must be unique within an agreement (`422`);
each component needs `label` and an `amount` or `percent`; a `PATCH` accepts only the whitelisted
fields (unknown field -> `422 validation`; status is never settable through a field `PATCH`).

## Webapp backend facade (browser-facing, behind the session gate)

Same shapes, proxied one-to-one, under `/api/agreements/...` and `/api/clients/{client_id}/agreements`.
The webapp backend adds `actor: "webapp"`, maps a connection failure to
`502 {"error":{"code":"agreements_unavailable"}}`, and never forwards the denidin-app token to the
browser.
