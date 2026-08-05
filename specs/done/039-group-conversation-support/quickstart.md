# Quickstart: Verifying Group Conversation Support

**Feature**: 039-group-conversation-support

Manual verification scenarios for each user story, to run against a running `dev` container
(per CLAUDE.md's environment rules — starting `dev` needs its own explicit approval, every
time). These complement, not replace, the automated test suite in `tasks.md`. Requires a real
WhatsApp group containing the godfather phone, the admin phone, and DeniDin's own number.

## Prerequisites

- `denidin-app-dev` running.
- A WhatsApp group exists with godfather + admin + DeniDin as the only three participants
  (the target scenario), and admin also has a pre-existing 1:1 chat with DeniDin with some
  prior history in it.

## US1 — Group text gets a reply with no "denidin" substring

1. In the group, godfather sends a plain question with no occurrence of "denidin" and no
   `"@"` pattern, e.g. "מה המצב עם התיק של X?".
2. Confirm DeniDin replies normally in the group.
3. Repeat from the admin phone — confirm the same.

## US2 — Group session stays separate from admin's 1:1 session

1. Note admin's existing 1:1 session id/history (`dev_data/sessions/`).
2. Send a message in the group from admin, then a message in admin's 1:1 chat.
3. Confirm two distinct sessions exist, keyed by their respective `chat_id`s (`...@g.us` vs.
   `...@c.us`), each containing only the messages sent through that specific chat — no
   cross-contamination.

## US3 — Sender display-name attribution, visible to the model

0. Prerequisite: godfather and admin are saved as WhatsApp contacts under readable names
   (e.g. "Godfather", "Admin") on the DeniDin WhatsApp number.
1. Send one message from godfather, one from admin, in the group.
2. Inspect `dev_data/sessions/{group_session}/messages/*.json` — confirm godfather's message
   has `sender: "Godfather"` (a name, not a phone number) and admin's has `sender: "Admin"`.
3. Confirm both messages' `recipient` field is `null` (not `"AI"` — see US3a).
4. If a way to inspect the raw payload sent to OpenAI is available (e.g. a debug log of
   `conversation_history`), confirm each turn's content is prefixed `"[Godfather] ..."` /
   `"[Admin] ..."` — this is the part that actually matters: the model seeing who said what,
   not just the stored file.

## US3a — "AI" sentinel retired

1. Send any message (group or 1:1).
2. Inspect the persisted assistant-role message — confirm `sender: null` (not `"AI"`), and
   `recipient` holds the resolved display name of who it replied to.

## US4 — Most-permissive RBAC

1. Send a message from admin in the group; note the reply's behavior (should have access to
   Morning MCP tools if relevant, and godfather-level token budget applied) — compare against
   what admin alone would get in their 1:1 chat (should be identical, since ADMIN's own
   token_limit already equals GODFATHER's — the observable difference to look for is tool
   attachment/context depth, not a token-count difference).
2. (Optional, if a test client-only group is available) Send from a CLIENT-role phone in a
   group with no godfather/admin present; confirm CLIENT-level limits apply.

## US4a — No-reply mechanism works at all

1. Send a message engineered to trigger the no-reply sentinel (easiest: reuse one of US5's or
   US7's "clearly not for me" scenarios below).
2. Confirm no WhatsApp message is received back in the group.
3. Inspect `dev_data/sessions/{group_session}/messages/` — confirm the triggering message WAS
   persisted, but no new assistant-role message was created for that turn.

## US5 — Three-way split: answer / silent / ask (no `"@"` pattern)

**Case A — clearly for someone else → silent, no question:**
1. In the group, godfather sends a message naming the admin directly with clearly
   human-directed phrasing and no `"@"` pattern, e.g. "X, תזכיר לי אחר כך" (using admin's real
   name in place of X — must be unambiguous, not just "no mention of DeniDin").
2. Confirm DeniDin sends **no reply at all** — not a clarifying question, not silence-that-looks-
   like-a-bug, genuinely no message received (per US4a's mechanism).

**Case B — genuinely unclear → asks a question:**
1. Godfather sends a message deliberately ambiguous — plausibly readable as either a question
   to DeniDin or a comment to admin, with no name, no `"@"` pattern (e.g. something that could
   be either "you [DeniDin] check this" or "you [admin] check this" depending on who "you"
   means in context).
2. Confirm DeniDin asks a short clarifying question — not silence, not a substantive guess
   either way.

**Case C — ordinary message → answers normally:**
1. Send an ordinary message with no such signal — confirm DeniDin answers normally (neither
   Case A nor Case B's path fires on typical traffic).

## US6 — Media unaffected

1. Send a real image (e.g. a bank-deposit screenshot) in the group from admin.
2. Confirm it's processed exactly as in a 1:1 chat (extraction, any ledger-event capture,
   reply).
3. Confirm the resulting stored media-turn message has `sender: "Admin"` (the resolved display
   name, not a phone number, not "AI"), per US3.

## US7 — Text-based "@Name" resolution (self-referential check only)

**Case A — "@Name" doesn't refer to DeniDin (works for ANY name, real or not):**
1. Godfather sends a message containing `"@"` followed by admin's real name (or, to prove the
   mechanism doesn't depend on real participant names, arbitrary text like `"@lalalal"`) —
   either via WhatsApp's native @-mention picker or by typing it directly.
2. Confirm DeniDin sends **no reply at all** (US4a) — both the real-name and gibberish variants
   must behave identically, proving the model isn't matching against a roster of real members.

**Case B — "@Name" refers to DeniDin, overrides ambiguous content:**
1. Godfather sends a message with ambiguous-looking content but `"@DeniDin"` (or a close
   variant of DeniDin's own name) present.
2. Confirm DeniDin replies normally despite the ambiguous surrounding content — the `"@"`-tag
   resolves it outright, no clarifying question, no silence.
