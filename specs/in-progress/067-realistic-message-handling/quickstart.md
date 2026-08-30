# Quickstart: Realistic Message Handling — Multiple Interfering Messages

**Feature**: `feature/067-realistic-message-handling` · **Date**: 2026-08-30

Manual end-to-end verification, run after all automated tests are green. Every `dev` start
below needs its own explicit human approval (CLAUDE.md "NEVER START AN ENVIRONMENT ... WITHOUT
EXPLICIT APPROVAL").

---

## Prerequisites

1. `apps/denidin-app/config/config.dev.json` → `feature_flags.realistic_message_handling: true`.
2. Both apps up for `dev` (`scripts/run_all.sh dev` — separate approval), `morning-mcp-app-dev`
   status file shows `"status": "running"`.
3. A phone in the dev godfather/admin role.
4. `scripts/windows_prod/tail_logs.sh` equivalent for dev: `docker compose --project-directory .
   -f docker/docker-compose.dev.yml logs -f denidin-app-dev` in a side terminal.

---

## Scenario 1 — Benign additive burst → one merged reply (US1, SC-001)

1. Send, as fast as you can type, three separate messages:
   `קבע פגישה` → `עם דנה` → `מחר ב-3`
   (all three before any reply arrives).
2. **Expect**: exactly **one** reply, addressed to the third message, that reflects all three
   ("פגישה עם דנה מחר ב-15:00 …" or a single clarifying question covering the whole request).
3. **Expect in logs**: one `get_response` call; the producer acked all three notifications
   immediately; the first turn logged a round-boundary cancellation; the merged turn's
   `user_prompt` is the three lines newline-joined.
4. Open the session file under `~/denidin-winprod-data`… no — for dev, the session JSON under
   the dev data root: **three** `role="user"` entries, **one** `role="assistant"` entry.

## Scenario 2 — Create-then-retract → truthful single reply (US3, SC-003)

1. Send `צור קבלה ללקוח <real sandbox client> על 500 שקל`.
2. Before the approval prompt returns, send `בעצם תבטל`.
3. **Expect**: one final reply. Two possible truthful shapes:
   - If OpenAI had **not** yet executed the Morning call server-side: "ביטלתי, לא הופקה קבלה."
     No `PendingApproval` remains for the chat.
   - If OpenAI **had** already executed `create_receipt` server-side in the discarded turn:
     the reply says the receipt (with its number) was already created before the cancel and
     cannot be undone from chat — and still no stale pending approval.
4. **Expect in logs**: `side_effects_journal` populated iff the `mcp_call` actually ran; the
   merged turn's `instructions` contains the `[מערכת: ...]` note **after** the date line; no
   second `create_receipt` attempt.
5. **Expect**: `PendingApprovalManager` has nothing pending for the chat (the discarded turn's
   pending approval, if any, was dropped).

## Scenario 3 — Post-reply message is a fresh turn (US5, SC-005)

1. Send one message, **wait** for the full reply.
2. Send a second message.
3. **Expect**: the second message gets its own independent reply — no merge, no journal, the
   mechanism reset when reply 1 was sent.

## Scenario 4 — Media mid-burst does not disturb the text turn (US4, SC-004)

1. Send `כמה חשבוניות הפקתי החודש?`.
2. Before the reply, send an **image**.
3. **Expect**: the text question gets its answer (one reply). The image gets its **own**
   separate reply on the existing media path. Neither cancels the other. Order of the two
   replies is not guaranteed.
4. **Expect in logs**: no round-boundary cancellation on the text turn; the image went through
   `_process_media_message` as its own work item.

## Scenario 5 — Flag OFF → today's behaviour (US2, SC-002)

1. Set `feature_flags.realistic_message_handling: false`, restart `denidin-app-dev` (separate
   approval).
2. Repeat Scenario 1's three-message burst.
3. **Expect**: **three** separate replies, one per message — exactly today's behaviour. No
   producer/consumer threads spawned (single `run_forever` loop in logs). This proves the gate.

## Scenario 6 — Non-interruptible approval-execution turn (US3 scenario 5)

1. Send `צור קבלה ללקוח <client> על 500 שקל`, wait for the approval prompt.
2. Reply `כן`.
3. Immediately (before the confirmation reply) send `ותוסיף שורה על ייעוץ`.
4. **Expect**: the `כן` execution turn runs to completion and sends its confirmation (receipt
   created). The `ותוסיף שורה` message is then handled as a **new** turn (a fresh
   receipt/clarification), not merged into the execution turn.

---

## Third-party verification observations to record (research.md O1, O2)

- **O1** — during Scenario 2 step 3, confirm from the raw OpenAI response logged by
  `_finalize_response` that a server-side-executed MCP call appears as a `type == "mcp_call"`
  item in `response.output` **on the same response** that also carried the (now-discarded)
  assistant text — i.e. we can always see what ran. Paste the real `response.output` shape into
  research.md O1 and mark it resolved.
- **O2** — during Scenario 1, confirm from Green API logs that the three notifications, acked
  immediately by the producer, are **not** redelivered ~32s later (the
  `RecentNotificationDeduper` window). Record the observed behaviour in research.md O2 and mark
  it resolved.

---

## Static checks

```bash
cd apps/denidin-app
python3 -m pylint src/ --fail-under=7.0 --rcfile=.pylintrc
python3 -m mypy src/ --config-file=mypy.ini
```

## Automated suites

```bash
cd apps/denidin-app
python3 -m pytest tests/unit tests/integration -q          # flag on + off paths
scripts/run_multiple_billed_tests.sh \
  tests/billed/test_realistic_message_handling_billed.py::test_benign_additive_burst_gets_one_reply \
  tests/billed/test_realistic_message_handling_billed.py::test_flag_off_burst_gets_three_replies \
  tests/billed/test_realistic_message_handling_billed.py::test_create_then_retract_burst_is_truthful
```
(sound off on each billed result as it completes).
