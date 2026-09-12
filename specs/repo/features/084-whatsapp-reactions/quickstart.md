# Quickstart: WhatsApp Reactions — Manual Verification Scenarios

All scenarios below run against a real `dev` environment (never `prod`). Starting/using `dev`
requires its own explicit human approval each time, per CLAUDE.md's environment-start rule — this
document does not grant that approval, it only describes what to verify once it's given.

## Scenario 0 — Gate Zero: live Green API reaction call (CLOSED — 2026-09-12)

Ran live against the real dev Green API instance and a real dev WhatsApp account, human-approved
and human-present to visually confirm each result. See `research.md` R1 for the full write-up.
Summary of what was confirmed:
1. ✅ Correct endpoint: `POST {{host}}/waInstance{{idInstance}}/sendReaction/{{apiTokenInstance}}`,
   payload `{"chatId", "idMessage", "reaction"}` — the originally assumed `sendMessageReaction`
   path and `messageId` payload key were both wrong, corrected from the real observed behavior.
2. ✅ Reacting to a real inbound (user-sent) message: reaction visibly appeared.
3. ✅ Flip (second call, same `idMessage`, different emoji): replaced, did not stack.
4. ✅ Clear (`reaction: ""`): reaction visibly disappeared.
5. ⚠️ Reacting to a message the bot itself sent (self-reaction): API returns 200 but never
   renders — a real limitation, non-blocking since this feature never needs it (see `research.md`
   R4).
6. ⚠️ Reacting to a bogus/nonexistent `idMessage`: also returns 200 — no synchronous 4xx signal
   exists for a deleted-target-message scenario, which changes Scenario 9 below.
7. 🔲 Group chat (`@g.us`): not tested — explicit human decision to skip, assumed identical by
   analogy to the confirmed 1:1 mechanism. Revisit if a specific test assertion needs it verified.

## Scenario 1 — Document ingestion with deferred resolution (UAT-1, P1)

**Given** a godfather/admin sends a fee-agreement PDF or image to DeniDin.
**Step**: observe the reaction that appears on the sent document.
**Confirm**: an in-flight emoji from `["👀", "🔍", "⏳"]` appears in under 1 second.
**Step**: continue the conversation through any clarification DeniDin asks for (e.g. a missing
client phone/email).
**Step**: complete the flow until the ledger event is actually persisted.
**Confirm**: the reaction on the *original document message* (not the clarification messages)
flips to ✅.

## Scenario 2 — Rejected document (UAT-1 variant)

**Given** the same flow as Scenario 1, but the workflow is abandoned or explicitly declined.
**Confirm**: the original document's reaction flips to ⚠️ or ❌ rather than staying on the
in-flight emoji or flipping to ✅.

## Scenario 3 — Action request & tool outcome flip (UAT-2, P1)

**Given** a godfather/admin sends "Create an invoice for 5,000 ILS for Client Y".
**Confirm**: an in-flight emoji from `["👍", "🫡", "👌"]` appears quickly, before the AI's
substantive reply arrives.
**Step**: wait for the invoice creation to actually complete via Morning.
**Confirm**: the reaction flips to ✅ (or 🎉) alongside the success reply.

## Scenario 4 — Failed/blocked action

**Given** the same command as Scenario 3, but against invalid input (e.g. an unresolvable client
name) so Morning/validation rejects it.
**Confirm**: the reaction flips to ⚠️ or ❓ alongside the explanatory reply — never ✅.

## Scenario 5 — Creative/conversational sentiment (UAT-3, P2)

**Given** a 1:1 message like "Happy Rosh Hashana!" or "You're a lifesaver, thank you."
**Confirm**: a contextually appropriate, non-generic emoji (e.g. 🍯, 🙏) is attached alongside
the normal conversational reply. Absence of a reaction here is not a failure (SHOULD, not MUST) —
note whether one appeared and whether it felt appropriate.

## Scenario 6 — Ambient group silence (UAT-4, P2)

**Given** a group chat where two human participants chat with each other, not mentioning or
addressing DeniDin, with no financial/ledger intent.
**Confirm**: zero reactions appear. Additionally, grep the app's logs for the time window and
confirm no `send_reaction`/reaction-endpoint call was even attempted (not just that none
succeeded) — this is what SC-003 actually requires.

## Scenario 7 — Trivial 1:1 discretion (UAT-4, P2)

**Given** a routine 1:1 exchange (e.g. the user says "ok thanks" after a normal reply).
**Confirm**: no reaction is forced onto this trivial turn.

## Scenario 8 — Rapid message burst

**Given** a user sends 3 messages in quick succession: two routine remarks and one real document
upload, all within a few seconds.
**Confirm**: exactly one reaction appears, on the document message — not on the two routine
remarks, and not duplicated.

## Scenario 9 — Message deleted before reaction

**Given** a document is sent, then deleted from the sender's phone before DeniDin's fast-path
reaction call completes.
**Confirm**: per Gate Zero's finding (`research.md` R1 item 5), Green API returns 200 regardless
of whether the target message still exists — so this scenario is expected to produce **no error
at all**, just a silent no-op reaction. No error surfaces to the user, the conversation continues
normally, and no WARNING is logged either (there is nothing to detect as a failure in this case —
confirm the implementation does not falsely log a failure it cannot actually observe).

## Scenario 10 — Green API 5xx / timeout

**Given** a way to simulate a Green API 5xx or timeout on the reaction endpoint specifically
(e.g. a temporary network fault injected at the test/staging level, not against real prod
infrastructure).
**Confirm**: exactly one retry occurs after ~1 second, then a WARNING is logged on continued
failure, and the core conversational turn/ledger transaction is entirely unaffected either way.

## Timing check (SC-001)

Across Scenarios 1 and 3, time the interval between webhook arrival (app log timestamp) and the
fast-path reaction actually being sent (app log timestamp). **Confirm**: consistently under 1.0
second — do not treat the "no LLM call, so it should be fast" design assumption as verified until
this is actually measured against the real dev environment.
