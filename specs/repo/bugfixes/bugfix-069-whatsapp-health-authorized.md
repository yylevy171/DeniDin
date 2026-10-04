# Bugfix 069: /health reports WhatsApp "success" while the Green API instance is logged out

**Status**: Done (2026-10-04) — PR #681
**Priority**: P0 (production incident)
**Branch**: `bugfix/069-whatsapp-health-authorized`
**Created**: 2026-10-04

## Incident

Prod WhatsApp stopped receiving messages after **2026-10-01 21:10** (the last `[AUDIT-IN]` line in
prod's `denidin.log*`). Oct 2, Oct 3 and Oct 4 until discovery have zero inbound messages. It was
noticed only on 2026-10-04 ~10:15, when the user's messages to the bot showed a single gray tick.
Green API (read-only call, 2026-10-04):
`getStateInstance -> {"stateInstance":"notAuthorized"}`,
`getStatusInstance -> {"statusInstance":"offline"}`.
Throughout the outage, denidin-app's `/health` reported `"whatsapp_connectivity": "success"`, so the
prober logged every service as healthy every minute and the 0.7.9 prod deploy verified "healthy".

## Root cause (approved by the PM, 2026-10-04)

`apps/denidin-app/src/services/health_server.py` `check_whatsapp_connectivity` calls
`green_api.account.getStateInstance()` and returns `response.code == 200`. Green API answers
HTTP 200 for every instance state, including `notAuthorized`, so the check proves only that Green
API's servers are reachable, never that our WhatsApp number is linked and receiving.

## Decision (PM, 2026-10-04)

- **Report only, never fail.** Add a separate `whatsapp_authorized` field to denidin-app's `/health`
  body: `"success"` only when `getStateInstance` returns 200 **and** `stateInstance == "authorized"`,
  otherwise `"fail"`. It **never** affects the overall `status` or the HTTP code.
  - **Why:** the prober (`scripts/health_monitoring/prober.py`) restarts prod whenever `status` is
    not `ok`, and a restart cannot re-link a phone. Counting this check would put prod in an
    endless soft/hard restart loop that also takes Morning and the webapp down.
  - The prober, deploy and verify scripts judge health by `status` alone
    (`scripts/health_monitoring/verify.py` `is_healthy_body`), so a report-only field cannot
    trigger restarts.
- The existing `whatsapp_connectivity` check (Green API reachable) is unchanged.
- **Alerting a human** is not part of this bugfix. It was added to Feature 028 (FR8).
- No feature flag: a monitoring bugfix that only adds a field to the `/health` body; no message
  handling path changes.

## Test-gap analysis

`tests/unit/test_health_server.py`:
- **The fake only ever returns `authorized`.** `_FakeGreenApiResponse` returns
  `{"stateInstance": "authorized"}` for every 200, so no test ever exercised "HTTP 200 but not
  authorized", which is the exact production failure.
- **No report-only concept exists in the server.** Every registered check feeds `status`, so there
  was no way to surface a state that must not cause restarts.

## New tests (RED first)

1. `check_whatsapp_authorized`:
   - True only for 200 + `authorized`;
   - False for 200 + `notAuthorized` (the incident);
   - False for 200 + `yellowCard` / `blocked` / `starting`;
   - False for non-200;
   - False when the call raises.
2. `build_health_info_fns`: empty without `green_api`; `{"whatsapp_authorized"}` with it.
3. `start_health_server` with report-only checks:
   - a failing one shows `"fail"` while `status` stays `ok` and the HTTP code stays 200;
   - a passing one shows `"success"`;
   - a raising one shows `"fail"` and is not a 500;
   - a failing real check still fails `status`, even when report-only checks pass.

## Fix

- **Checks:** `check_whatsapp_authorized` + `build_health_info_fns` in `health_server.py`.
- **Server:** `start_health_server(port, check_fns, info_fns=None)` adds report-only fields to the
  body without touching `status` / the HTTP code.
- **Wiring:** `denidin.py` passes `build_health_info_fns(green_api=live_bot.api)`.

## Verification (2026-10-04)

- **Unit tests:** `tests/unit/test_health_server.py` 37/37, including 11 new ones. Full denidin-app
  unit + integration suite: 1,678 passed, 0 failed.
- **Green API docs** (`GetStateInstance`): `notAuthorized` is a documented `stateInstance` value,
  returned in a normal 200 response. The other values are `authorized`, `blocked`, `sleepMode`,
  `starting`, `yellowCard` and `suspended`; only `authorized` passes.
- **Live, real prod instance, logged out (~10:15):** HTTP 200 +
  `{"stateInstance":"notAuthorized"}`, the case the new check rejects.
- **Live, real prod instance, after re-linking (~10:45):** the new `check_whatsapp_authorized`, run
  through the real `whatsapp_api_client_python` client, returned True for
  `{'stateInstance': 'authorized'}`.
- **Service restored:** prod WhatsApp was re-linked by QR scan around 10:30, and messages flowed
  again from 10:30:33.

## Out of scope / follow-ups

- **Re-linking prod WhatsApp:** QR scan on the bot's phone, a human action. This is what restores
  service.
- **Real-time alerting:** Feature 028 FR8.
- **Lost or delayed messages:** whether messages sent during the outage are delivered after re-linking
  will be observed, not assumed (CONSTITUTION: no unverified third-party assumptions).
