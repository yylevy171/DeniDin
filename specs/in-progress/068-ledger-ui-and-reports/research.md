# Research & Open Decisions: Feature 068

## 1. Password hash function

**Decision**: `sha256(salt + password)` with `salt = "denidin-pw"` — a **hardcoded module
constant** (`webapp_backend.auth.PASSWORD_SALT`), never a config key (2026-09-05: removed from
`AppConfig` / all config files; a stray `password_salt` key is now ignored). Fixed literal, per user
instruction). Not PBKDF2/bcrypt/argon2.

**Rationale**: this gate protects against casual/accidental access (no login system, single
shared password, internal tool), not against a determined offline attacker with the hash file
in hand — and the user explicitly specified the salt literal, which only makes sense for a
plain fast hash (a real KDF's whole point is a *configurable, slow* cost factor, which a fixed
literal salt doesn't need). If threat model changes later (e.g. once this gate is the only
thing standing between the internet and real client financials, post Cloudflare Tunnel), this
should be revisited — noted as a flagged risk, not silently resolved as "good enough forever."

## 2. Filtering split: server-side vs client-side

**Decision** (see `plan.md`'s "Data Flow" section): the *load window* (`days_back`) is the only
server-side filter parameter; every on-screen filter (date-range-within-loaded-set, event
type/subtype, client name, global fuzzy search) is applied client-side over the already-loaded
batch.

**Rationale**: matches the spec's explicit UX ("all filters visible/editable, nothing
re-filters until Apply is pressed" — an instant, no-network, no-loading-spinner interaction is
implied) and avoids round-tripping the whole event set on every filter tweak. The trailing
"days_back" window is different in kind — it changes *what data exists client-side at all*, so
it must be a real reload.

**Consequence to surface in the UI (flagged in spec.md already)**: the on-screen date-range
filter's *from* bound can silently be inside the loaded window while its stated range implies
otherwise if a user sets it wider than `days_back` — `tasks.md`/frontend copy must make clear
these are two different concepts (a disabled/greyed date picker bound at the loaded window's
edge, or an inline note, to be decided in `tasks.md`).

## 3. Media/context byte-serving

**Decision**: `GET /media/{token}` — a dedicated, session-token-gated endpoint that streams the
resolved media file's bytes (never inlines base64 into the `/events/{id}/context` JSON
response), where `{token}` is an opaque reference the backend hands back inside
the context response (not the raw filesystem path), e.g. `{"media_url": "/media/abc123..."}}`.

**What "media token" means, in plain terms (2026-09-05, user asked)**: when a chat message has
an attached image/PDF, the backend must give the browser some URL to fetch that file from. It
must NOT put the real file path (`.../dev_data/media/DD-972...-uuid.jpg`) in that URL — that
would leak the server's directory layout. So instead the backend generates a meaningless
short string ("token"), remembers internally which real file it maps to, and the browser's URL
is just `/media/<that string>`. **Validity (2026-09-05 decision): tied to the session — the
same `Authorization: Bearer <session-token>` every other endpoint needs; the media URL simply
stops working when the session expires or the user logs out.** No separate per-file expiry
clock, no extra moving parts.

**Rationale**: avoids bloating JSON payloads with base64 images; keeps the raw `data_root` path
never exposed to the client even indirectly. **Path-traversal safety**: the backend must
resolve the underlying real path and assert it is a descendant of the configured `data_root`
before serving — never trust a client-supplied filename/path directly, even indirectly via a
media token, without this containment check as defense-in-depth (belt-and-suspenders even
though the token itself isn't attacker-choosable).

## 4. JS/TS test tooling (repo's first UI feature — no existing precedent)

**Revised decision (2026-09-04, per explicit user direction)**: **Playwright is the required,
"real" test tier for this feature — the direct UI equivalent of `billed`/`expensive` in the
existing TDD redefinition** (real, end-to-end, from-the-user's-perspective, run against a real
built app with real data, no mocking). This is what the user actually cares about as
acceptance evidence; everything below it is optional scaffolding, not the bar.

- **Playwright** (`apps/webapp/frontend/e2e/`, run via `npx playwright test`, **not** part of
  `npm test`): real Chromium, real CSS layout engine, driven against the actual running
  frontend + backend (real data, matching the zero-mocking philosophy). This is the layer that
  proves the things `jsdom`-based component tests structurally cannot:
  - Interaction: press "+", assert both panels actually appear with the correct rendered data.
  - Real layout: `getBoundingClientRect()` assertions — right panel positioned right-of/above
    left panel per viewport, expanding a row visibly pushes subsequent rows down.
  - Viewport-driven behavior: same suite run at a desktop width and a mobile width, asserting
    side-by-side at desktop vs. stacked-vertical at mobile (spec.md's explicit requirement).
  - Visual regression: screenshots of key states (collapsed list, expanded row, expand-all)
    diffed against a checked-in baseline per viewport, to catch layout drift, not just "it
    rendered something."
  - This suite is the feature's actual acceptance test, run at the end of `speckit.implement`
    (same "written and run together, once, as a final pass" shape `billed`/`expensive` follow)
    — see `plan.md`'s Verification section, revised accordingly.
- **Jest + React Native Testing Library** (`npm test`) is kept only as fast, optional
  developer-loop scaffolding during implementation (structural/behavioral sanity while writing
  components) — **not required, not gating, not part of acceptance**, per the user's explicit
  "all the rest I don't care about" instruction. `tasks.md` should not spend real task-planning
  weight on it; a task list built around Playwright as the actual deliverable is correct here.

**Rationale for keeping Playwright separate from `npm test`/Jest rather than merged**: they
have different runtimes (real browser vs `jsdom`) and different purposes (acceptance/visual
truth vs quick dev-loop feedback) — collapsing them would blur which one is actually gating.

## 5. `LedgerEventManager` "list all" access

**Decision** (recommended, pending `speckit.tasks`/human sign-off since it touches
`denidin-app`'s own manager): add a small additive public method, e.g.
`list_events(self) -> List[Dict]` returning a shallow copy of `self._index`, rather than the
BFF reaching into the underscore-prefixed `_index` attribute directly from another app's
codebase.

**Rationale**: `_index` is conventionally private; even though Python won't stop cross-module
access, reading another app's private attribute directly is a maintainability smell and would
silently break if `_index`'s internal shape ever changes for reasons unrelated to this feature.
A one-line additive public method is low-risk, clearly scoped, and testable on its own. This
touches `apps/denidin-app/src/`, so it needs to be called out explicitly as an in-scope change
to denidin-app itself when this feature's PR is reviewed — not something to slip in unannounced.

## 5a. Client-name typeahead data source (2026-09-05)

`GET /clients/search?prefix=` (contracts/api.md) needs a full-history distinct-client-name
list. No new `denidin-app` method is needed for this beyond `list_events()` (research.md §5,
if added) — the BFF already holds the full in-memory event list for this purpose; the distinct
`client_name` set is derived in the BFF itself (a simple set-comprehension over already-fetched
events), not a separate `LedgerEventManager` capability.

## 6a. Auth model gaps: concurrent sessions & audit trail (2026-09-05)

The user asked directly: what does a second successful login actually mean, given the password
is shared and reusable? Answer surfaced a real gap — as originally scoped, the password is not
consumed, has no expiry, and any number of devices/people can be logged in simultaneously with
no way to distinguish them. Resolved:

- **Session expiry**: each issued token now carries an issue/last-activity time and expires
  after **168 hours (1 week) of inactivity** (server-configurable; independent of
  `SessionManager`'s own unrelated `session_timeout_hours`). Concurrent sessions across devices
  remain **allowed** (a new login does not invalidate others) — chosen over "new login kicks
  out everyone else" because there's no concept of "whose" session should win with a shared,
  identity-less password.
- **Testing note (2026-09-05)**: expiry is real behavior but not automated in any test tier —
  the user explicitly chose manual verification only over a backend test with an artificially
  short test-only expiry window. `tasks.md`'s Story 1 Acceptance-adjacent notes should record
  this as a deliberate, one-time manual check at real acceptance time, not an oversight.
- **Login audit logging**: every login attempt, success or failure, is written to the backend's
  log file with a timestamp and outcome (no new UI/storage needed — reuses the app's normal
  logging). This is the only accountability mechanism available given there are no per-user
  accounts; it doesn't prevent misuse, but makes it after-the-fact visible.
- **Explicitly still not addressed** (not raised as blocking, but worth naming so it isn't
  mistaken for solved): a leaked/shared password remains fully usable by anyone until the
  password file is manually rotated; there is no rate-limiting on login attempts (brute-force
  is unaddressed); there is no way to selectively revoke one device's session without expiring
  everyone's or rotating the password entirely.

## 6. Hosting/ingress (Cloudflare Tunnel) — deployment-time details deferred

Confirmed with the user: one Cloudflare Tunnel per environment, routed only to that
environment's webapp ports; `denidin-app`/`morning-mcp-app` are never tunneled. Still open,
to be settled at actual deploy time (not blocking `speckit.tasks`):
- Which domain (must be added to the user's Cloudflare account).
- Exact subdomain scheme (`ledger-dev.<domain>` / `ledger.<domain>` suggested, not decided).
- Whether `cloudflared` runs as a third container per environment (matching the
  containers-only rule the rest of the project follows) or as a host-level process — should
  default to **containerized**, per "Both apps run exclusively as Docker containers" precedent,
  unless a concrete reason emerges to deviate.

## 7. Concurrent read of denidin-app data while it is mid-write (2026-09-05)

The webapp-backend reads `LedgerEventManager`'s index (and session/message JSON files) while
`denidin-app` may be actively writing a new ledger event or message. **Explicitly out of scope
for v1** (user decision, 2026-09-05): ledger events and messages are written as atomic
single-file JSON writes, so a reader either sees the old set or the new file, never a torn one.
No dedicated test for a partially-written file is required. If a malformed JSON file is ever
encountered during a list load, the sensible-but-untested behavior is to skip that one file and
continue rather than fail the whole load — noted here so a future hardening pass has a starting
point, not built now.
