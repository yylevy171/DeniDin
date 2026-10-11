# Contract: Fast-path reaction heuristic

**Location**: `apps/denidin-app/denidin.py`, inside `dispatch_notification()`.

## Hook placement

Inserted as a side-effecting pre-step, **after** the existing dedup check and **before** the
`HANDLER_REGISTRY.get(...)` lookup — never as a new `HANDLER_REGISTRY` entry, since that table's
exact 9-key shape (verified live against `test_denidin_dispatch.py`'s
`test_registry_contains_exactly_these_nine_types_no_more_no_less`) is locked by an existing test.
The existing `interactiveButtonsResponse` special-casing is the precedent for
adding new pre-dispatch behavior without touching the registry's shape.

```python
handler = HANDLER_REGISTRY.get(type_message, CATCH_ALL_HANDLER)
_dispatch_fast_path_reaction(type_message, notification)   # NEW — never raises, logs on failure
handler(notification)
```

`_dispatch_fast_path_reaction` itself (revised 2026-09-12 — see `contracts/group-discretion-gating.md`'s
Correction: there is no separate "addressed to bot" predicate to check first; classification below
IS the gate, for group and 1:1 traffic alike):
1. Classifies the message per `research.md` R2's two lookup tables:
   - `typeMessage in {"imageMessage", "documentMessage"}` → pick from the media pool
     (`["👀", "🔍", "⏳"]`).
   - `typeMessage in {"textMessage", "extendedTextMessage"}` and the text matches the curated
     action-verb keyword list → pick from the action-request pool (`["👍", "🫡", "👌"]`).
   - Anything else (routine chatter, media types with no matching heuristic) → no reaction,
     silently. This is the entire gate — ambient group banter and trivial 1:1 chatter alike simply
     never match either rule, satisfying REQ-084-005/SC-003 without a dedicated addressing check.
2. Resolves the message's real `idMessage` from the inbound webhook payload (already extracted
   inline elsewhere in `green_api_bot.py` for read-receipt purposes — reuse that extraction, do not
   re-derive it) and the `chatId`.
3. Calls `send_reaction(bot, chat_id, id_message, chosen_emoji)` — never blocks `handler(notification)`
   from running afterward regardless of outcome; any exception inside this whole function is caught
   internally, logged at WARNING, and swallowed (REQ-084-007).

## Rapid-burst handling

Per the spec's edge case ("if a user sends multiple messages in rapid succession, the router must
react to the primary actionable message rather than firing duplicate reactions across all parts"):
the fast-path hook reacts to **each dispatched notification independently** — because
`dispatch_notification()` is the single per-webhook entry point, "primary actionable message" in
practice means: only messages that pass the classification in step 2 receive a reaction at all,
so a burst of routine acknowledgment messages alongside one real document/action message produces
exactly one reaction, on that one message, with no extra bookkeeping required. If real-world
testing (`quickstart.md` scenario 8) reveals multiple messages in a burst *each* independently
classify as actionable, that is treated as correct behavior (each is independently actionable), not
a bug — this contract does not attempt cross-message suppression beyond what classification itself
already provides.

## Performance

Synchronous dispatch (plain HTTP via `send_reaction`, no LLM call) — expected to comfortably clear
the <1000ms budget (SC-001), but this is a "should be fine by construction" claim, not a measured
one; `quickstart.md` includes an explicit real-environment timing check before this is treated as
verified.

## Shared flip-not-stack contract with the AI tool

The emoji this hook sends targets the exact same `idMessage` a later `react_to_message` call (fast-
path-set-then-model-flipped) would target — see `data-model.md`'s `whatsapp_id_message` field and
`research.md` R3 (flip-not-stack confirmed live during Gate Zero). No de-dup/suppression logic is
needed here beyond both call sites resolving the same real id.

## Testing

Unit: classification logic (media/action-request/neither) and the addressed-to-bot short-circuit,
against fixed notification payloads — no network, `send_reaction` stubbed.

Integration: a real notification through `bot.router` confirming an addressed message reaches
`send_reaction` (asserted via a stub at the Green API boundary only) and an ambient group message
does not reach it at all.
