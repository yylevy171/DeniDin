# Feature Specification: Morning API Authentication Migration (OAuth2 Token Endpoint)

**Feature Branch**: `feature/053-morning-api-auth-migration`
**Feature ID**: 053-morning-api-auth-migration
**Priority**: P1 — real, dated cutoff already passed; current auth flow is at risk of being
blocked without further warning.
**Created**: August 13, 2026
**Status**: Done — implemented, tested (22 new unit tests, 3 new + several updated real sandbox
integration tests, all green), and verified live via a real dev-environment smoke test (real
OpenAI call → real MCP tool call → real Morning sandbox document creation, through the actual
rebuilt `morning-mcp-app-dev` container). Merged to master (PR #218).
**Input**: User report — a deprecation warning shown in Morning's own login UI, corroborated by
real primary-source research this session (see Origin below)

---

**MANDATORY REQUIREMENT MET**: See `user-stories.md` (this directory) for Given-When-Then user
stories, per METHODOLOGY.md §I/§II.

**This spec complies with**:
- **CONSTITUTION.md** §I (config/dependency handling — no env vars, all config explicit),
  §III (feature branch workflow), "NO UNVERIFIED THIRD-PARTY ASSUMPTIONS" (every claim below is
  backed by a real, directly-fetched primary source, not documentation paraphrase or inference —
  see citations throughout).
- **METHODOLOGY.md** §I (user stories mandatory), §II (template structure).

---

## Origin

The user saw a deprecation warning in Morning's own web UI during login. Investigating (this
session, 2026-08-13) turned up the real, primary-source explanation:

**Source 1** — Morning's official help-center article,
<https://www.greeninvoice.co.il/help-center/api-updates-26/> (fetched and read directly, raw
HTML stripped to text; the user independently pasted the same page's rendered text mid-session,
word-for-word matching what was fetched — corroborated twice):

> עדכונים חשובים בתשתית ממשק ה-API של מורנינג. במהלך חודש יוני 2026 יתבצעו מספר עדכונים בתשתית
> ה-API של מורנינג... העדכונים כוללים שינוי במבנה קבלת ה-Token ועדכון כתובת ה-Base URL של
> השירות... הכתובת והמבנה הישנים ימשיכו להיתמך עד יוני 2026. לאחר מכן, קריאות בנתיבים הישנים
> ייחסמו.

(Translation: important updates to Morning's API infrastructure. During June 2026, several
updates to Morning's API infrastructure will take effect... including a change to the Token
acquisition structure and an update to the service's Base URL... The old address and structure
will continue to be supported until June 2026. After that, requests to the old paths will be
blocked.)

**Source 2** — Morning's real, current OpenAPI spec, fetched directly from
`https://developers.morning.co/docs/openapi.bundled.json` (the actual spec file backing their
public Redoc documentation site — reverse-engineered via the site's JS bundle, not guessed;
`info.version: "2.0.0"` is the *documentation portal's* version number, not a REST API URL
version — the documented base URLs for `/documents`, `/clients`, etc. are still
`https://api.greeninvoice.co.il/api/v1` prod / `https://sandbox.d.greeninvoice.co.il/api/v1`
sandbox, unchanged).

**Source 3** — this app's own current implementation,
`apps/morning-mcp-app/src/denidin_mcp_morning/auth.py`.

### What's actually changing vs. what isn't (confirmed by diffing sources 2 and 3 against 1)

**NOT changing** (already correct — no action needed): the base URL used for `/documents`,
`/clients`, and every other endpoint. `MorningClient`'s default `base_url`
(`https://api.greeninvoice.co.il/api/v1`) already matches the help-center notice's stated *new*
address (`api.greeninvoice.co.il/api`) — the "old" address it warns about
(`www.greeninvoice.co.il/api`) does not appear anywhere in this codebase.

**IS changing** — token acquisition only, confirmed via the real OpenAPI spec's
`/idp/v1/oauth/token` path definition (`obtainAccessToken`, tag `Authentication`):

| | Current (`auth.py`) | Required (per the real spec) |
|---|---|---|
| Host | `{base_url}` (same host as `/documents`/`/clients`) | **A different host entirely**: `https://api.morning.co` (prod) / `https://api.sandbox.morning.dev` (sandbox) — this path has its own `servers` override in the spec, distinct from every other endpoint's default. |
| Path | `/account/token` | `/idp/v1/oauth/token` |
| Request body | `{"id": ..., "secret": ...}` | `{"grant_type": "client_credentials", "client_id": ..., "client_secret": ...}` (all three required; `TokenRequest` schema) |
| Response shape | Token read from `X-Authorization-Bearer` header, or JSON `token`/`access_token` | JSON `{"accessToken": ..., "tokenType": "Bearer", "expiresAt": <unix ts>}` (`TokenResponse` schema) — `accessToken` (camelCase) is not one of the keys the current code checks for at all |
| Token TTL | Assumed fixed `token_ttl_seconds` (default 3600) | Real spec confirms "valid for 1 hour" but also returns an authoritative `expiresAt` timestamp per response — using it directly is more correct than assuming a fixed TTL |
| Auth header on subsequent calls | `Authorization: Bearer <token>` | Unchanged — same scheme, per `TokenResponse.accessToken`'s own description ("use as `Authorization: Bearer <token>` header") |

**Error shape** (per the spec's documented error responses, RFC 6749 OAuth2 format):
`400 invalid_request` (missing `grant_type`), `400 unsupported_grant_type`, `400 invalid_grant`
(API key expired/revoked/pending), `400 unauthorized_client` (no active subscription/API access),
`401 invalid_client` (missing/incorrect `client_id`/`client_secret`, or account blocked) — all
with body `{"error": "<code>", "error_description": "..."}`.

### Config changes (confirmed with the user, 2026-08-13)

Since the token endpoint's host now genuinely differs from the main API's host (previously one
`base_url` served both), `MorningAuth` needs a new, explicit place to get that second host from —
it cannot be derived/inferred from the existing `api_url` config value (CONSTITUTION §I: no
inference, config must be explicit).

- **New field: `auth_url`**, in `apps/morning-mcp-app/config/config.{dev,prod,test,example}.json`,
  set independently per environment (`https://api.sandbox.morning.dev` for dev/test,
  `https://api.morning.co` for prod) — same pattern as `api_url` today.
- **Removed field: `token_ttl_seconds`**. Today this drives an *assumed* expiry
  (`now + token_ttl_seconds`, default 3600). The new response includes a real, authoritative
  `expiresAt` unix timestamp — once that's used directly, `token_ttl_seconds` has nothing left
  to drive and becomes dead config. Removed outright (not kept as a fallback) per explicit user
  decision — cleaner than carrying unused config forward "just in case."
- **Unchanged**: `api_url`, `api_key_id`, `api_key_secret`, `refresh_before_seconds` (the
  proactive-refresh safety margin stays meaningful and independent of where the raw expiry comes
  from).

## Problem Statement

`MorningAuth._request_token()` calls an authentication endpoint and request/response shape that
Morning's own real, current API documentation no longer describes at all — it has been fully
replaced by a standard OAuth2 client-credentials flow on a separate host. The old endpoint is
still working as of this investigation (real sandbox/prod calls succeeded throughout the session
this was found in), but Morning's own notice states the cutoff ("until June 2026") has already
passed calendar-wise, meaning the old flow could stop working at any time with no further
warning, breaking every Morning-dependent capability in `denidin-app` (invoicing, client
management, financial reporting) for both `dev` and `prod`.

## Scope

### In scope
- Migrate `MorningAuth._request_token()` to call `POST {auth_url}/idp/v1/oauth/token` with the
  new request body shape (`grant_type`/`client_id`/`client_secret`) and parse the new response
  shape (`accessToken`/`tokenType`/`expiresAt`), using the real `expiresAt` for cache-expiry
  tracking instead of the current fixed-TTL assumption.
- Add the new `auth_url` config field to `apps/morning-mcp-app`'s config example/dev/prod/test
  files, pointing at the correct host per environment (`api.morning.co` prod /
  `api.sandbox.morning.dev` dev+test). Remove `token_ttl_seconds` (superseded by the real
  `expiresAt` timestamp — see "Config changes" above).
- Full regression coverage: unit tests against the new request/response shape and every
  documented error case; a real integration test against the actual sandbox token endpoint; a
  real dev-environment smoke run (start the container, confirm a real tool call succeeds
  end-to-end) before this is considered done.

### Out of scope
- Any change to `base_url`/`api_url` used for `/documents`, `/clients`, or any other endpoint —
  already correct, confirmed unaffected by this migration.
- Feature 041 (`mcp` package 2.0 migration / dependency pinning) — a separate, unrelated
  concern, parked back in `specs/backlog/` per explicit user decision this session.
- Any change to how the access token is *used* on subsequent calls (`Authorization: Bearer
  <token>` header) — unchanged per the real spec.
- The invoice-allocation-number (`מספר הקצאה`) Israel Tax Authority mandate investigated
  alongside this — confirmed (via the real OpenAPI spec's `Document`/`Expense` schemas) to be
  handled server-side by Morning once a business account is Tax-Authority-connected, with no
  API-level integration action required on our part (response-only fields:
  `allocationNumber`, `taxAuthorityConfirmationInitiated`, `taxAuthorityConfirmationNumber`,
  etc.). Not this feature's concern; noted here only so it isn't re-investigated from scratch
  later under a mistaken belief it's related.

## Success Criteria

- `MorningAuth` successfully obtains and refreshes tokens via the new OAuth2 endpoint in both
  `dev` (sandbox) and, once deployed, `prod`.
- Every documented error case (`invalid_request`, `unsupported_grant_type`, `invalid_grant`,
  `unauthorized_client`, `invalid_client`) is handled with a friendly, non-crashing outcome
  (CONSTITUTION §X), never a raw stack trace or silent auth failure.
- `apps/morning-mcp-app`'s full test suite is green, plus a real dev-environment smoke test
  (tunnel status `"running"`, `/health`, and at least one real end-to-end tool call) confirmed
  working before this is considered done.
- No change in behavior for any endpoint other than token acquisition.
