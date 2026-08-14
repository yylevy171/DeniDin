# Feature Specification: WhatsApp Interactive Buttons for the Approval Gate

**Feature Branch**: `feature/047-whatsapp-interactive-approval-buttons`
**Created**: 2026-08-09
**Status**: Draft — backlogged, pre-clarification
**Priority**: P2
**Input**: User description (2026-08-09, during bugfix-028): *"doesnt whatsapp allow a button to
press which can be used for approval in our case? (and a 2nd button for 'dont approve' of
course)"*

---

**IMPORTANT**: This spec complies with:
- **CONSTITUTION.md** (§I-III, §V, §XVII, NO UNVERIFIED THIRD-PARTY ASSUMPTIONS): No env vars,
  UTC timestamps internally, feature branch workflow, integration tests as E2E, no
  monkey-patching.
- **METHODOLOGY.md** (§I, II, VIII, IX, X): Spec-first development, mandatory user stories,
  Terminology Glossary, Technology Choices, Requirement IDs.

**Required Files**: `user-stories.md` (present, DRAFT) ✅ · `spec.md` (this file, DRAFT) ·
`plan.md` (NOT STARTED) · `research.md` (present, 2026-08-14 — **Gate Zero CLOSED**, see below) ✅ ·
`data-model.md` (NOT STARTED) · `contracts/` (NOT STARTED) · `quickstart.md` (NOT STARTED) ·
`tasks.md` (NOT STARTED).

---

## Origin

Proposed by the user while bugfix-028's Cluster B was being fixed. Two of that cluster's five
sub-bugs exist only because an approval is a **free-text word** that has to be parsed:

- **B1** — the prompt ended `— לאשר?` while the parser's whitelist held `אישור` and not `לאשר`,
  so the prompt taught a word it then rejected. The user answered `לאשר` twice, got the identical
  prompt back twice, and gave up.
- **B2** — WhatsApp prefixes RTL text with U+200F RIGHT-TO-LEFT MARK, which is not whitespace, so
  a plain `‏כן` was read as a refusal. Verified live: 2026-08-09 04:00:45 UTC.

A button carries an **identifier**, not a word. Neither failure mode can occur on that path:
there is nothing to spell, nothing to typo (`מאשאת`), and no invisible formatting character to
survive a `.strip()`.

## What is already known (verified 2026-08-09, not assumed)

**Sending is supported by the client library already in use.** `whatsapp_api_client_python`
exposes `sendInteractiveButtons` and `sendInteractiveButtonsReply`
(`tools/sending.py:470,512`); the older `sendButtons` / `sendTemplateButtons` /
`sendListMessage` are present but marked deprecated in favour of them. **No new dependency is
needed for the outbound half.**

**The inbound half is entirely unknown.** Nothing in the library or in either app references a
button-reply webhook type — no `buttonsResponseMessage`, no `interactiveButtonsReply`. Our router
(`denidin.py:502-624`) handles `textMessage`/`extendedTextMessage`, `contactMessage`,
`contactsArrayMessage`, `imageMessage`, `documentMessage`, `videoMessage`, `audioMessage`, plus a
catch-all — so a button tap today would fall into the catch-all and do nothing useful.

## ✅ Gate Zero — a real button round-trip, before any design (CLOSED 2026-08-14, see research.md)

**No design work, no `plan.md`, no code may begin until a real button has been sent to a real
WhatsApp number, tapped by a real person, and the resulting webhook JSON captured and recorded in
`research.md`.**

This is not ceremony. CONSTITUTION's NO UNVERIFIED THIRD-PARTY ASSUMPTIONS rule exists because of
exactly this class of mistake, and bugfix-028 produced two fresh examples in one session: a
"type 300 carries no VAT" premise taken from a UI observation and never reproduced against the
API (it was wrong, and inflated a real ₪2,360 document to ₪2,784.80), and a "Morning's payment
object accepts bank details" assumption (the field names were wrong, and they only persist on one
payment type). Both were settled in minutes by a real call.

What the round-trip must establish:
1. The exact `typeMessage` a tapped button produces.
2. Where the button's identifier lives in the payload, and whether the button's *label* is also
   carried (it must not be the thing we key on — labels are display text).
3. Whether the reply is linked to the original message (a `quotedMessage`/`stanzaId` or similar),
   which decides whether we can bind a tap to a *specific* pending approval rather than "the
   chat's current one".
4. Behaviour in **group** chats, where DeniDin also operates.
5. What happens on an **old** button — one whose approval has already been resolved, expired, or
   superseded. Whether WhatsApp/Green API blocks it or delivers it like any other message
   determines how much of the guard has to live in our code.
6. Whether the buttons render on the real paid WhatsApp Business numbers this project uses (both
   dev and prod have their own — see CLAUDE.md's asymmetry note).

## Scope

**In scope**: an additional, *parallel* route into the existing Feature 022 approval gate.

**Out of scope**: replacing the free-text route. The text path stays exactly as it is — a user
who types `כן` must still be understood, whether or not buttons render on their device, and
whether or not the button is still tappable. This feature adds a second door to the same room; it
does not close the first.

**Explicitly not solved by this feature**: bugfix-028's **B3** and **A4**. A button still needs a
message saying what is being approved. The structured `📋 לאישור:` block (document type, date,
client, amount, VAT, purpose, plus optionals) remains mandatory and unchanged — buttons change how
the answer arrives, never what the question must contain.

## Open questions for clarification

1. **Two buttons or three?** "אישור" / "ביטול" — or a third for "עוד פרטים"?
2. **What happens to a stale button** once an approval has been resolved by text, superseded, or
   has expired — silently ignore, or reply explaining it's no longer live? (Depends on Gate Zero
   finding 5.)
3. **Groups** — should buttons appear at all in a group chat, where any member could tap them?
   Note RBAC for a group turn already resolves to the most-permissive member
   (`GroupMembershipResolver`), which is a *different* question from who physically tapped.
4. **Audit** — bugfix-036 notes the MCP server has no audit trail. Should a tap be recorded
   distinguishably from a typed approval, so "who approved this document, and how" stays
   answerable?

## Related work

- `specs/done/022-explicit-approval-for-document-creation/` — the gate this plugs into.
- `specs/done/046-hebrew-approval-synonyms/` — widened the affirmative whitelist; the layer this
  feature would make largely unnecessary for tapped approvals.
- `specs/in-progress/bugfixes/bugfix-028-invoicing-and-approval-gate-p0-cluster.md` — **B1** and
  **B2** are the motivating defects; **B3** is the part buttons do *not* address.
