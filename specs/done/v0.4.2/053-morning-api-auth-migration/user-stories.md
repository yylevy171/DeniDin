# User Stories: Morning API Authentication Migration (OAuth2 Token Endpoint)

Feature ID: 053-morning-api-auth-migration

---

## US1: Obtain a Morning access token via the new OAuth2 endpoint

**As** `morning-mcp-app`,
**I want** to request an access token from Morning's real, current authentication endpoint
(`POST {auth_url}/idp/v1/oauth/token`, `grant_type: client_credentials`),
**so that** invoicing/client/reporting tool calls keep working once Morning blocks the old
`/account/token` endpoint (already past its stated "until June 2026" support window).

**Given** valid `client_id`/`client_secret` credentials and a configured `auth_url` for the
current environment (dev→sandbox, prod→prod),
**When** `MorningAuth.get_token()` needs a fresh token,
**Then** it POSTs `{"grant_type": "client_credentials", "client_id": "<id>", "client_secret":
"<secret>"}` to `{auth_url}/idp/v1/oauth/token`, reads `accessToken` from the JSON response body,
and returns it — Router/Dispatcher Requirement: this must be the ONLY token-acquisition path;
the old `/account/token` call must not remain as a fallback.

**Given** a successful token response `{"accessToken": "...", "tokenType": "Bearer",
"expiresAt": 1771317327}`,
**When** the token is cached,
**Then** the cache expiry is derived from the real `expiresAt` unix timestamp, not from an
assumed fixed TTL — so a token issued with an unusual lifetime (shorter or longer than the
typical 1 hour) is still tracked correctly.

## US2: Every documented OAuth2 error case fails safely, never crashes or misleads

**As** a godfather/admin using DeniDin's invoicing features,
**I want** a Morning authentication failure (expired API key, no active subscription, wrong
credentials, etc.) to produce a clear, friendly error,
**so that** I understand something needs fixing on the Morning-account side, instead of DeniDin
silently failing or throwing a raw exception.

**Given** Morning's real documented error responses (`400 invalid_request`, `400
unsupported_grant_type`, `400 invalid_grant`, `400 unauthorized_client`, `401 invalid_client` —
each with `{"error": "<code>", "error_description": "..."}`),
**When** any of these is returned from the token endpoint,
**Then** `MorningAuth`/`MorningClient` surfaces a friendly, non-crashing error up through the
existing MCP error boundary (`_call_with_error_boundary` in `server.py`) — never a raw stack
trace, never a silent no-op, per CONSTITUTION §X.

**Given** the token endpoint is temporarily unreachable (network error, 5xx),
**When** a tool call needs a token,
**Then** the existing retry policy applies (CONSTITUTION §XI: retry once on 5xx/timeout after
1s, never retry 4xx) — a 4xx OAuth2 error (bad credentials, expired key) must NOT be retried, only
a genuine transient failure.

## US3: Environment-correct `auth_url` configuration, no inference

**As** a developer running `dev` (sandbox) or `prod` (real Morning account),
**I want** the token endpoint's host to be explicitly configured per environment, not guessed
from the existing `api_url`,
**so that** dev never accidentally hits the prod token host or vice versa (CONSTITUTION §I: no
env vars, all config explicit).

**Given** `config.dev.json`/`config.test.json` point at the sandbox token host
(`https://api.sandbox.morning.dev`) and `config.prod.json` points at the real prod token host
(`https://api.morning.co`),
**When** `create_server`/`MorningClient` initializes `MorningAuth`,
**Then** it uses the configured `auth_url` directly — never derives it from `api_url`'s host,
never falls back to a hardcoded default silently shared across environments.

**Given** `auth_url` is missing from a config file,
**When** the app starts,
**Then** config validation fails loudly at startup (CONSTITUTION §I: "Validate all configuration
at startup with clear error messages") — never a lazy failure the first time a token happens to
be requested.

## US4: Regression-proof before this is considered done

**As** a maintainer of `apps/morning-mcp-app`,
**I want** real test coverage (not mocked) proving the new flow actually works against Morning's
real sandbox, plus a real dev-environment smoke run,
**so that** "the code compiles and unit tests pass" is never mistaken for "this actually works
against the real Morning API" (CONSTITUTION's zero-mocking-of-internal-components policy, §I/§V).

**Given** the migration is implemented,
**When** `apps/morning-mcp-app`'s integration suite runs against the real sandbox,
**Then** a real token is obtained, cached, used for a real tool call (e.g. `list_invoices`), and
refreshed correctly once expired — no mocking of the token endpoint itself.

**Given** the integration suite is green,
**When** a real dev-environment smoke test is performed (start the container, confirm the ngrok
tunnel status file shows `"status": "running"`, hit `/health`, make one real tool call
end-to-end through the full `denidin-app` → tunnel → `morning-mcp-app` → Morning sandbox path),
**Then** it succeeds before this feature is considered ready to haleluya.
