# Feature Specification: MCP Auth Mechanism Hardening & Auto-Rotation

**Feature Branch**: `feature/057-mcp-auth-hardening`
**Created**: 2026-08-18
**Status**: Placeholder — not yet clarified/specced. Captured from a 2026-08-18 request;
run `speckit.specify` + `speckit.clarify` before starting implementation.

## Input

User description: "create a new feature 57 - hardening security of auth mechanism, which will
include changing the mechanism and also auto-rotation" — raised directly after a walkthrough of
how Feature 055 (multi-tenancy) wired per-tenant bearer-token auth between `apps/denidin-app`
and `apps/morning-mcp-app`'s shared MCP server.

## Context that prompted this

Feature 055 gave `apps/morning-mcp-app`'s `BearerTokenMiddleware` a per-tenant token map
(`{token: tenant_id}`, `server.py`), sourced from each tenant's own `mcp_auth_token`
(`config.py`'s `TenantMorningCredentials`, joined against `apps/denidin-app`'s own
`Tenant.mcp_auth_token`). Walking through how that token is managed surfaced that it is:

- **A long-lived, static, opaque secret** — a plain string, checked by literal comparison, no
  built-in expiry or lifetime semantics (not a JWT, not OAuth, nothing self-describing).
- **Manually duplicated in two places** — `apps/denidin-app`'s per-tenant credential config AND
  `apps/morning-mcp-app`'s `config.<env>.json`, kept in sync only by hand. No shared source of
  truth, no validation that the two sides agree — a drift is silent until a call 401s.
- **Has no rotation mechanism at all.** Rotating one today means: generate a new string by hand,
  edit it in both configs, restart both containers. No grace/overlap window (the old token stops
  working the instant the new config is loaded — a non-atomic two-file edit means a real
  window where calls fail), no scheduled/automatic rotation, no immediate-revocation path for a
  suspected compromise beyond the same manual edit-and-restart.
- Explicitly NOT to be confused with the separate, already-adequate `MorningClient` OAuth2
  token (Morning's own `client_id`/`client_secret` → access-token exchange, Feature 053,
  auto-refreshed via `refresh_before_seconds`) — that mechanism is out of scope here; this
  feature is about the `denidin-app` ↔ `morning-mcp-app` bearer token only, unless clarification
  broadens it.

## Notes captured so far

- Scope not yet defined. Open questions for `speckit.specify`/`speckit.clarify`:
  - **What replaces the static shared secret?** Candidates to evaluate: short-lived signed
    tokens (JWT/HMAC with an expiry claim, minted by one side and verified by the other without
    a shared static value being what's actually compared); mTLS between the two apps; an
    OAuth2-style client-credentials exchange (mirroring what `MorningClient` already does
    against Morning itself, Feature 053) where `denidin-app` fetches a short-lived access token
    from `morning-mcp-app` using a longer-lived-but-still-rotatable client secret.
  - **What does "auto-rotation" actually mean here?** A scheduled job that mints a new
    secret/key on an interval? Automatic short-lived-token minting per call/session (making
    "rotation" a non-event because nothing long-lived exists to rotate)? Needs an explicit
    decision on rotation *of what* (the root secret vs. per-call tokens derived from it) before
    a mechanism can be chosen.
  - **Cross-app sync problem**: today's two-config, manually-kept-in-sync shape is itself part
    of the security gap (a drift silently breaks a tenant's invoicing tools, and there's no way
    for either side to detect the OTHER side already rotated). Does the new mechanism need a
    single source of truth one app derives from, or a real distribution/handshake step?
  - **Zero-downtime rotation**: does the new mechanism need an overlap window (old and new
    credential both valid briefly), given `apps/morning-mcp-app`'s config isn't hot-reloaded
    (restart required) and both apps' "never restart without explicit approval" rule (CLAUDE.md)
    makes any rotation that requires a restart an operator-gated event, not a background one?
  - **Audit/observability**: should a rotation event itself be logged/audited (who/what
    triggered it, old-vs-new key identifiers without logging the secret values themselves)?
  - **Scope boundary**: does "hardening the auth mechanism" stay limited to the MCP bearer
    token, or does it also cover other long-lived static secrets in this repo with the same
    shape (Green API tokens, OpenAI keys, `constitution_supplement_file` paths aren't secrets
    but credentials generally) — needs an explicit in/out-of-scope line, not an implicit
    expansion once specced.
  - **Backward compatibility during rollout**: Feature 055's `BearerTokenMiddleware` already
    supports two modes (`token=` legacy single-secret, `tokens=` per-tenant map) for
    REQ-PARITY-001 reasons — does the new mechanism need a similar migration path, or is a
    clean cutover acceptable given the low tenant count today?
