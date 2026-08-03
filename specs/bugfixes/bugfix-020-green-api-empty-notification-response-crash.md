# Bugfix Spec: GreenAPIBot crashes on startup when Green API returns a genuinely empty notification response

## Bug ID
bugfix-020-green-api-empty-notification-response-crash

## Title
`denidin-app` crashes at startup with `TypeError: string indices must be integers` whenever the connected Green API instance responds to an empty notification queue with a truly empty HTTP body, instead of the JSON literal `null`

## Priority
P0 — breaks core functionality entirely: the bot process cannot start at all against an affected instance. Confirmed to already affect `denidin-app-prod` (first real deploy, 2026-08-03) and, as of the same day, the newly-created `denidin-app-dev` Green API instance too — this is not environment-specific, it depends only on which Green API backend deployment the connected instance happens to be served by.

## Status
Fixed and verified. Fix direction approved by human (Option C, 2026-08-03), scope extended to also cover the equivalent bug in `Bot.run_forever()` (same human approval — see "Fix Direction (Approved)" below). Implemented, tested (new unit tests + full existing suite, 586/586 passing), lint/mypy clean (no new issues vs. pre-fix baseline), and re-verified against the real, currently-affected dev Green API instance (`710722700313`) via `tests/integration/test_real_api_connectivity.py`.

## Date Opened
2026-08-03

## Reported By
yaronlev171 (discovered during Feature 035's first real deploy of `denidin-app`/`morning-mcp-app` v0.0.1 to the Windows-hosted `prod` environment)

## Affected Area
- Third-party dependency: `whatsapp_api_client_python.response.Response.__init__` (installed version `0.0.54`, the current latest release on PyPI — confirmed via PyPI's own release history, no newer version exists to pick up an upstream fix)
- Third-party dependency: `whatsapp_chatbot_python.bot.Bot.__init__` / `_delete_notifications_at_startup` (installed version `0.9.9`)
- Our own code: `apps/denidin-app/denidin.py:77-80` — constructs `GreenAPIBot(config.green_api_instance_id, config.green_api_token)` with no `delete_notifications_at_startup` argument, so it defaults to `True` and unconditionally runs the buggy startup-cleanup path on every process start

## Description
On the first real deploy of `denidin-app-prod` to the new Windows-hosted always-on production host (Feature 035), the container crashed immediately on startup:

```
Traceback (most recent call last):
  File "/app/denidin.py", line 77, in <module>
    bot = GreenAPIBot(
  File "/usr/local/lib/python3.9/site-packages/whatsapp_chatbot_python/bot.py", line 58, in __init__
    self._delete_notifications_at_startup()
  File "/usr/local/lib/python3.9/site-packages/whatsapp_chatbot_python/bot.py", line 139, in _delete_notifications_at_startup
    self.api.receiving.deleteNotification(response.data["receiptId"])
TypeError: string indices must be integers
```

The watchdog correctly did not auto-restart the crashed subprocess (by design — no automatic retry on a non-environment-mismatch exit).

## Root Cause (confirmed, not just suspected)

`_delete_notifications_at_startup` (`whatsapp_chatbot_python/bot.py:125-139`) loops:
```python
while True:
    response = self.api.receiving.receiveNotification()
    if not response.data:
        break
    self.api.receiving.deleteNotification(response.data["receiptId"])
```

`Response.__init__` (`whatsapp_api_client_python/response.py`) does:
```python
if self.code == 200:
    try:
        self.data = loads(text)
    except Exception:
        self.data = "[]"
```

Green API's own documentation for `ReceiveNotification` states explicitly: *"The method call ends with an empty response if a timeout is reached"* when the notification queue is empty — i.e. the **documented, official** behavior for an empty queue is a genuinely empty HTTP body (0 bytes), not `null`/`[]`/`{}`.

When the body is truly empty, `json.loads('')` raises a `JSONDecodeError`. The bare `except Exception` swallows this and sets `self.data` to the **string** `"[]"` — not `None`, not an empty list. Back in the loop, `if not response.data: break` does **not** fire (a non-empty string is truthy), so execution falls through to `response.data["receiptId"]` — indexing a string with a string key, which raises the observed `TypeError`.

### This is not a credentials problem, not our code, and not prod-specific

Confirmed via direct, real, read-only calls to the actual Green API (bypassing our code and the client library entirely), from two independent network paths (the Windows box, and this Mac directly):

| Instance | `getStateInstance` | `receiveNotification` raw body | Response headers |
|---|---|---|---|
| prod (`710722700252`) | `{"stateInstance":"authorized"}` | `''` (0 bytes) | bare CORS headers only, no `Content-Security-Policy`/`X-Frame-Options`/etc, no `ETag` |
| new dev (`710722700313`, created 2026-08-03) | not separately re-checked, but same account creation flow | `''` (0 bytes) | identical bare-header profile to prod |
| **old** dev (`7105257767`, in use until 2026-08-03) | (was working fine) | `'null'` (4 bytes) | full Helmet-style header set (`Content-Security-Policy`, `X-DNS-Prefetch-Control`, `X-Frame-Options`, `Expect-CT`, `ETag`, etc.) |

Both a Green-API-console settings change on the prod instance and a full reboot of the old dev instance were tried live, mid-investigation, at the reporter's request — neither changed either instance's behavior. The two response shapes are a fixed characteristic of which backend deployment generation each instance happens to sit behind (both resolve to the same `api.green-api.com` hostname, but are clearly served by different backend stacks based on the header sets alone), not something togglable per-instance or fixable by a reboot/setting.

Credentials were independently confirmed valid throughout (`getStateInstance` → `"authorized"` for the affected prod instance, checked both via the Windows box and directly from the Mac).

**Practical implication**: the *old* dev instance was, by luck, sitting on a backend that serializes an empty queue as `null` (which `json.loads` parses fine, correctly falsy) — masking this latent bug in every dev session so far. The moment dev was cut over to its new instance (2026-08-03, unrelated credential-rotation reason), dev immediately started exhibiting the same empty-body behavior as prod. This bug is not tied to any environment — it will crash `denidin-app` startup on **any** Green API instance served by the newer/standard (and per Green API's own docs, officially correct) backend behavior, whenever the notification queue happens to be empty at process start — which, for a freshly-created or well-drained instance, is close to guaranteed.

## Steps to Reproduce
1. Point `denidin-app` at any Green API instance whose backend serves the documented empty-body behavior for `receiveNotification` (confirmed: both the current prod instance and the new — post-2026-08-03 — dev instance; likely any newly-created instance going forward).
2. Ensure the instance's notification queue is empty (a freshly created/authorized instance already satisfies this).
3. Start `denidin-app` (`docker compose up` / `run_all.sh <env>` / `python denidin.py` directly). It crashes immediately with the `TypeError` above, before any webhook/message handling code ever runs.

## Expected Behavior
`denidin-app` should start successfully regardless of which raw wire-format the connected Green API instance uses to signal "notification queue is empty" — this is squarely a startup-path robustness issue, not something that should ever surface as an unhandled crash.

## Fix Options Considered

**A. Pass `delete_notifications_at_startup=False`** to the `GreenAPIBot(...)` constructor (`denidin.py:77`) — a supported, documented flag on the library's own `Bot.__init__`. One line. Trade-off: skips clearing any real backlog of stale notifications that piled up during downtime entirely, so the very next restart could immediately process/reply to a backlog of old messages rather than starting from a clean slate.

**B. Subclass `Bot`**, override `_delete_notifications_at_startup` (Template Method pattern — explicitly the kind of alternative CONSTITUTION §XVII recommends in place of monkey-patching) with a corrected version that treats any non-dict `response.data` as "queue empty, stop" instead of crashing. Preserves existing cleanup behavior, but leans on a third-party library's private method name/shape, which could silently break again on a future upstream release.

**C. Construct with `delete_notifications_at_startup=False`, then run our own correct drain loop** (calling `self.api.receiving.receiveNotification()`/`deleteNotification()` directly, treating any non-dict `.data` as "empty, stop") immediately before constructing `GreenAPIBot`. Preserves the existing cleanup behavior without depending on the library's private method internals — the tradeoff of B without the fragility.

### Fix Direction (Approved, 2026-08-03)

**Option C**, selected after web research confirmed no upstream fix exists (`whatsapp_api_client_python`/`whatsapp_chatbot_python` last touched Feb 2025, no related GitHub issue filed) and Green API's own docs don't specify the exact empty-body wire format — so this has to be handled in our own code regardless.

**Scope extended beyond the original startup-only report**, per the same approval: while investigating, an additional, previously-undocumented instance of the identical bug was found in `whatsapp_chatbot_python.Bot.run_forever()` (`bot.py:69-89`) — the actual continuous polling loop used for *every* live message check, not just the one-time startup drain. It has the exact same `if not response.data:` / `response.data["receiptId"]` pattern. Unlike the startup path, `run_forever()`'s loop body is wrapped in a broad `try/except Exception`, so it doesn't crash the process — but each occurrence logs a spurious ERROR and stalls polling for 5 seconds, and per Green API's own docs an empty-body response is the *expected*, common outcome whenever there's simply nothing new to deliver (not a rare edge case). Human approved fixing both in this bugfix rather than splitting into a second spec, since they share one root cause and one fix shape.

A third, lower-risk unguarded spot (`Bot._update_settings()`, `bot.py:97-100`, unguarded `settings.data["incomingWebhook"]` from `getSettings()`, called once per bot construction) was identified but **left unfixed** — Green API's docs don't describe `getSettings` as ever returning an empty-body response the way `receiveNotification` does, so it's a much lower-probability recurrence of the same pattern; flagged here for future reference rather than fixed speculatively.

### Implementation

`apps/denidin-app/src/utils/green_api_bot.py` — new `DeniDinGreenAPIBot(GreenAPIBot)` subclass (Template Method, not monkey-patching, per CONSTITUTION §XVII):
- `__init__`: always constructs the parent `Bot` with `delete_notifications_at_startup=False` (bypassing the library's buggy drain entirely), then — if the caller's own `delete_notifications_at_startup` (default `True`) is set — runs our own corrected `_drain_startup_notifications()`.
- `_drain_startup_notifications()`: re-implements the startup drain loop, treating any non-dict `response.data` (the `"[]"` fallback string, `None`, or anything else) as "queue empty, stop" via a shared `_notification_data_or_none()` helper, instead of indexing it as a dict.
- `run_forever()`: re-implements the polling loop with the same corrected check, preserving every other existing behavior unchanged (KeyboardInterrupt breaks the loop, other exceptions are still caught/logged/`sleep(5.0)`'d, `raise_errors=True` still wraps and re-raises as `GreenAPIBotError`).

`apps/denidin-app/denidin.py`: `GreenAPIBot(...)` → `DeniDinGreenAPIBot(...)` (import + one instantiation line changed; no other call sites referenced `GreenAPIBot` directly).

## Test Gap Analysis
Confirmed: none of the existing test suites exercised `GreenAPIBot`/`Bot` construction or polling behavior at all — no test constructed a real or fake `Bot`/`GreenAPIBot` instance and drove its startup-drain or `run_forever()` loop, so there was no automated coverage that would have caught this regardless of which fix direction was chosen. `tests/unit/test_green_api_bot.py` (14 new tests) fills this gap: it independently reproduces the *original* library crash against a bare `Bot` instance (confirmed via a standalone repro script, not just asserted) before verifying `DeniDinGreenAPIBot`'s corrected `_notification_data_or_none()`, `_drain_startup_notifications()`, and `run_forever()` handle the fallback `"[]"` string, `None`, and real notification payloads correctly, and that unrelated exceptions still hit the original catch/log/sleep/`raise_errors` behavior unchanged.

## Test Gap Audit (Additional Green API Usages)
Audited every place our own code (`apps/denidin-app/denidin.py`, `src/handlers/`, `src/managers/`) touches Green API responses. Finding: our code never touches `whatsapp_api_client_python.Response` directly — it only ever reads already-parsed `Notification.event` dicts or calls `notification.answer(...)`, both downstream of the library's internal parsing. No other fragile `.data`-indexing pattern exists in our own code. The two related-but-distinct issues found in the *library's* code (`run_forever()`, now fixed as part of this bugfix; `_update_settings()`, left unfixed — see above) are documented above.

## Acceptance Criteria
- [x] Root cause investigated and confirmed against the real Green API, independent of any assumption about credentials or our own code
- [x] Fix direction approved by human (BDD gate) — Option C, scope extended to `run_forever()`
- [x] Test gap analysis documented
- [x] Failing test(s) written and approved before any fix — `tests/unit/test_green_api_bot.py`, verified to fail against the original unpatched library method
- [x] Fix implemented — `src/utils/green_api_bot.py` (`DeniDinGreenAPIBot`), wired into `denidin.py`
- [x] Tests pass, no regression — full suite 586/586 passing; pylint (`src/` 9.02/10, no new findings vs. pre-fix baseline) and mypy (identical pre-existing error count, 0 new) both clean
- [x] Re-verified against a real deploy — `tests/integration/test_real_api_connectivity.py` re-run against the real, currently-affected dev Green API instance (`710722700313`); also required updating stale credentials in `config/config.test.json` and `creds/DeniDin Dev Creds.txt` (still pointed at the retired old dev instance `7105257767`), which were blocking this verification. Real-device verification of a live Windows-hosted `prod` deploy (per Feature 035's `deploy_and_verify.sh`) is still outstanding — deploying is a separate, explicitly-gated action not taken in this session.

## References
- Feature 035 (`specs/035-windows-always-on-prod/`) — first real deploy that surfaced this bug
- `apps/denidin-app/denidin.py:77-80`
- `whatsapp_chatbot_python/bot.py` (`_delete_notifications_at_startup`, `Bot.__init__`'s `delete_notifications_at_startup` flag)
- `whatsapp_api_client_python/response.py` (`Response.__init__`)
- Green API docs: `ReceiveNotification` — documents the empty-body-on-timeout behavior directly
- `.github/METHODOLOGY.md` §VII (Bug-Driven Development)
