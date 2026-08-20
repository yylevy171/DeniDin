# Implementation Plan: Mark Incoming Messages as Read (Blue Checkmarks) — Feature 045

**Feature**: 045-mark-messages-read
**Branch**: `feature/045-mark-messages-read`
**Spec**: `./spec.md` · **User Stories**: `./user-stories.md`
**Status**: Ready for Task Generation
**Updated**: 2026-08-07

**Compliance**: CONSTITUTION.md (§I no env vars — reuses existing Green API credentials
already in config; §II UTC — N/A, no timestamps added; §III git workflow; §V real-external-
call, zero-mocking — `readChat` is a real Green API call, already live-verified during
`speckit.clarify`, never mocked in tests either; §XVII no monkey-patching). **No feature
flag** (explicit user call, 2026-08-07): this is a small, low-risk, easily-revertable behavior
with a hard best-effort/log-only failure mode (see Q5) — no gradual-rollout or kill-switch need
that would justify one. Always on once merged.

---

## Summary

All open questions resolved during `speckit.clarify` (see spec.md), including a live-verified
real call (`bot.api.marking.readChat` → `200 {'setRead': True}` → visually confirmed blue
checkmark). **Deliverable**: call `bot.api.marking.readChat(chatId, idMessage=<inbound
message's real id>)` as early as possible in message handling — right after a webhook
notification is parsed, before RBAC/session/AI processing — for every non-blocked sender,
every message type. Best-effort: failures are logged only, never block the rest of the flow,
never retried.

## Technical Context

- **Language/Version**: Python 3.11 (unchanged).
- **Primary Dependencies**: none new — `bot.api.marking.readChat` is already available via the
  existing `whatsapp-chatbot-python`/`whatsapp_api_client_python` dependency.
- **Storage**: N/A — no new persisted state.
- **Testing**: decision logic (extraction, blocked-skip, flag-check) covered by a `tests/unit/`
  test with `bot.api.marking.readChat` mocked (permitted for external services in unit tests,
  per CONSTITUTION §V). Real end-to-end confirmation lands in the existing
  `tests/billed/test_real_api_connectivity.py` (already `pytest.mark.billed`, real Green API,
  no mocking) alongside its existing `test_greenapi_can_send_message` — reuses that file's
  `config`/`green_api_client` fixtures rather than inventing a new integration-test path.
- **Target Platform**: N/A — no container/runtime change beyond the code change itself
  (existing rebuild-on-merge process applies, per "Merging a code fix does not redeploy it").
- **Constraints**: RBAC resolution normally happens after this point in the flow (session load,
  group-membership resolution) — but "is this sender blocked" (Q4) needs a role lookup, which
  today happens later. Needs a lightweight early role check (reusing `UserManager`, not
  duplicating its logic) before the `readChat` call, or accepting the call fires before the
  blocked-check and treating "skip blocked users" as a soft best-effort filter rather than a
  hard ordering guarantee — to be decided in `tasks.md` based on how invasive an early
  role-lookup would be to the existing flow.
- **Scale/Scope**: one new call site (`DeniDinGreenAPIBot.run_forever`'s notification hook),
  one new unit test, one new `billed`-tier real-API test.

## Constitution Check

- **No env vars** — PASS: reuses existing `green_api_instance_id`/`green_api_token` config.
- **UTC** — N/A.
- **Feature branch** — PASS: `feature/045-mark-messages-read`.
- **Feature flags** — N/A by explicit user decision (2026-08-07): scope too small/low-risk to
  warrant one; see Compliance note above.
- **Real-sandbox/zero-mocking (§V)** — PASS: real `readChat` call, already live-verified;
  new `billed`-tier test hits the real Green API, no mocking.
- **No monkey-patching** — PASS: new call site, no runtime patching.
- **Friendly errors (§X)** — PASS: failures are logged only (this is cosmetic, non-blocking),
  no user-facing error message needed since nothing about the rest of the flow changes.

## Project Structure

```text
specs/backlog/045-mark-messages-read/
├── spec.md          # done — CLARIFIED
├── user-stories.md  # done — CLARIFIED
├── plan.md          # this file
└── tasks.md         # next — /speckit.tasks
```
(No `research.md` — the one open technical question was already resolved live during
`speckit.clarify`, not deferred to a research phase. No `data-model.md`/`contracts/` — no new
entities or external contracts beyond the already-existing, already-confirmed `readChat` call
shape. No `quickstart.md` — no new user-facing setup steps, no config to touch, nothing to
enable.)

### Source Code

```text
apps/denidin-app/src/utils/green_api_bot.py
  # + read-receipt decision helper(s): extract (chatId, idMessage) from a raw notification
  #   body; orchestrator that checks blocked-status and calls bot.api.marking.readChat,
  #   best-effort (exceptions caught, logged, never propagate)
  # + DeniDinGreenAPIBot gains an on_notification_received hook, called from run_forever()
  #   right before route_event, wrapping the call above

apps/denidin-app/denidin.py
  # + after initialize_app(), wire bot.on_notification_received to a closure over denidin_app
  #   (for the blocked-sender check via ai_handler.user_manager)

apps/denidin-app/tests/unit/test_read_receipt.py
  # + new: decision-logic tests, bot.api.marking.readChat mocked

apps/denidin-app/tests/billed/test_real_api_connectivity.py
  # + new test alongside existing test_greenapi_can_send_message: real readChat call via
  #   journal.lastIncomingMessages, asserting the real {'setRead': True} response
```

## Phased Execution

### Phase 1 — Test (TDD)
Write the `tests/unit/` test for the decision logic (mocked Green API call), per METHODOLOGY
§VI — RED first (helper functions don't exist yet).

### Phase 2 — Implementation
Add the helper functions and the `on_notification_received` hook, wire it in `denidin.py`.
Test goes GREEN.

### Phase 3 — Real-API confirmation
Add the `billed`-tier test in `test_real_api_connectivity.py`, confirm it passes against the
real Green API.

### Phase 4 — Close out
Move spec to `specs/done/` once merged.

## Complexity Tracking

No Constitution Check violations requiring justification. The one design wrinkle (blocked-
sender check needing to happen earlier than today's RBAC resolution point) is a scoping detail
for `tasks.md`, not a constitutional exception.
