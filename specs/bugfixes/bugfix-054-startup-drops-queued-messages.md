# Bugfix Spec: Startup deletes queued WhatsApp messages instead of processing them

## Bug ID
bugfix-054-startup-drops-queued-messages

## Title
On every `denidin-app` startup, the `whatsapp-chatbot-python` library clears the Green API
incoming-notification queue (`Deleted old incoming notifications` log line) **before** the
receive loop starts, deleting every notification without dispatching it through the router. Any
WhatsApp message that arrived while the bot was down — a restart, a deploy, a crash, a
watchdog-kill, an outage — is silently lost. The sender gets no reply and no error.

## Priority
**P1** — silent, user-facing data loss on every restart. Real client conversations (legal /
invoicing) are dropped with no trace. Not P0 because it only affects messages sent during a
downtime window, not steady-state traffic.

## Status
**Open.** Root cause observed and narrowed during the 2026-09-06 prod incident response; not yet
confirmed against the library source. Per Bug-Driven Development (METHODOLOGY.md §VII), next
steps: (1) confirm the exact library behavior + any config toggle against the real
`whatsapp-chatbot-python` version in `requirements.txt`, (2) human approval of the root cause,
(3) test-gap analysis, (4) failing test, (5) human approval, (6) minimal fix, (7) verify.

## Date Opened
2026-09-06

## Reported By
yaronlev171, during the 2026-09-06 partial-prod-outage recovery. Two real messages (one godfather
1:1, one group) sent while prod was degraded were never answered; investigation of
`denidin-app-prod` logs showed they were purged at a restart, never routed.

## Evidence (2026-09-06, prod)

- `denidin-app-prod` restarted ~23:12 (2026-09-05) and again ~07:49 (2026-09-06).
- Both startups logged: `whatsapp-chatbot-python:INFO:Deleted old incoming notifications.`
  immediately before `Started receiving incoming notifications.`
- Between those two log lines there is **no** router dispatch, no `[AUDIT-IN]`, no
  `Received message from …`.
- The user's 2 messages were sent during the ~9h degraded window. After the 07:49 restart,
  `Started receiving incoming notifications` was followed by **zero** inbound activity until the
  user re-sent manually (08:17) — confirming the originals were consumed-and-deleted, not queued.
- Green API's queue model: a notification persists until an explicit `DeleteNotification`; the
  library issues those deletes on boot *without* handing the payloads to `bot.router`.

## Affected Area

- `apps/denidin-app/utils/green_api_bot.py` / `apps/denidin-app/denidin.py` `__main__` /
  `GreenAPIMessageSource` — wherever `bot.run_forever()` (or equivalent) is invoked.
- The `whatsapp-chatbot-python` dependency's startup queue-clear behavior (version per
  `apps/denidin-app/requirements.txt`).
- The `HANDLER_REGISTRY` / `dispatch_notification` path (Feature 043) — the target the drained
  notifications should be routed through.

## NO UNVERIFIED THIRD-PARTY ASSUMPTIONS (CONSTITUTION.md)

Before any fix is designed, confirm against a real run / the library source:
- Whether the startup delete is unconditional or has a config flag
  (`deleteNotificationsAtStartup` or similar) in the pinned version.
- Whether `receiveNotification` on boot returns the backlog in order and whether re-processing
  risks duplicates (a notification the bot *did* handle but crashed before deleting).
- Green API's actual queue retention / ordering guarantees.

## Proposed direction (to be refined by clarify / plan)

On startup, **drain and dispatch** the queued notifications through the normal router path
instead of deleting them undelivered — or, at minimum, process only those newer than a bounded
lookback (e.g. last 1h, mirroring the Feature 054 reminder sweep's blast-radius cap) to avoid
replaying very stale traffic. Needs:
- idempotency / dedup against messages already persisted to a session (a redelivered
  notification must not double-reply);
- a bound so a long outage doesn't trigger hundreds of catch-up OpenAI calls at once;
- correct behavior for media messages, group messages, and interactive-button taps in the
  backlog, not just `textMessage`.

## Relationship to other work

- Same incident produced **bugfix-055** (bundled-app stop cascade) — different root cause, same
  2026-09-06 outage.
- The catch-up/lookback shape overlaps with Feature 070's daily-roll startup sweep and Feature
  054's reminder startup sweep — reuse that pattern.
