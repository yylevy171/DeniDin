# Quickstart: WhatsApp Reactions — Manual Verification Scenarios

All scenarios below run against a real `dev` environment (never `prod`). Starting/using `dev`
requires its own explicit human approval each time, per CLAUDE.md's environment-start rule — this
document does not grant that approval, it only describes what to verify once it's given.

## Scenario 0 — Gate Zero: live Green API reaction call (BLOCKING PREREQUISITE)

**Not run as part of this planning stage.** Requires fresh, explicit human go-ahead when actually
executed.

1. From a real WhatsApp account, send any text message to the dev DeniDin number.
2. Using `raw_request` in a small throwaway script (or directly via the running app once
   Phase 1/2 land), call the reaction endpoint against that message's real `idMessage` with a
   test emoji.
3. **Confirm**: the emoji actually appears on the message in WhatsApp; capture the real HTTP
   request/response (status + body) for `research.md` R1.
4. Send a second, different emoji to the same message. **Confirm**: it replaces (flips) rather
   than stacking a second reaction.
5. Send an empty-string reaction to the same message. **Confirm**: the reaction is cleared.
6. Delete the original message from the phone, then attempt to react to its now-stale
   `idMessage`. **Confirm**: the failure is 4xx-shaped (not 5xx/timeout) and does not need a
   retry.
7. Repeat steps 2-3 targeting a message inside a group chat (`@g.us`). **Confirm**: identical
   behavior to the 1:1 case.

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
reaction call completes (timing this precisely may require a deliberately slow network or a
retry-forcing condition — best-effort scenario).
**Confirm**: no error surfaces to the user, the conversation continues normally, and a WARNING
(not ERROR) is logged.

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
