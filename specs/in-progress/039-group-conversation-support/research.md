# Research: Group Conversation Support

**Feature**: 039-group-conversation-support · Phase 0 output of `speckit.plan`.

All items below were open technical unknowns after `spec.md`/`user-stories.md`. Each is
resolved here by reading the actual current code (file:line) or, where noted, checking Green
API's own published documentation — never assumed.

---

## 1. How does DeniDin discover a WhatsApp group's member list?

**Decision**: Call `bot.api.groups.getGroupData(groupId)` (Green API's group-data endpoint,
https://green-api.com/en/docs/api/groups/GetGroupData/) once per group, with an in-process
cache keyed by `chat_id` to avoid a live API round-trip on every single group turn.

**Rationale**: Confirmed via the installed `whatsapp_api_client_python` SDK
(`venv/lib/python3.11/site-packages/whatsapp_api_client_python/tools/groups.py:67-90`) — this
is the only group-participant-listing method the SDK exposes (siblings:
`createGroup`/`updateGroupName`/`addGroupParticipant`/`removeGroupParticipant`/
`setGroupAdmin`/`removeAdmin`/`setGroupPicture`/`leaveGroup` — none of those list members).
The project's established calling convention is `bot.api.<resource>.<method>(...)`
(`tests/unit/test_green_api_bot.py:45-116` shows this pattern for `bot.api.receiving.*`).
`bot` is currently a module-level global in `denidin.py:78` (a `DeniDinGreenAPIBot` instance);
`WhatsAppHandler` itself (`src/handlers/whatsapp_handler.py`) holds no reference to `bot`
today, so the new group-membership lookup needs its own small component that receives
`bot.api.groups` (or the whole `bot.api`) via constructor injection — consistent with this
codebase's no-monkey-patching, dependency-injection convention (CONSTITUTION §XVII).

**Alternatives considered**:
- *New config listing group→members mapping*: rejected — would require the config to be kept
  in sync by hand every time a group's membership changes on WhatsApp itself (adding/removing
  godfather, admin, or anyone else), a silent-drift risk with no code-level guard. A live API
  call is self-correcting.
- *Resolve membership from message history* (whoever has ever sent a message in this group's
  session): rejected — under-counts (a member who never spoke yet, e.g. admin, wouldn't count
  until their first message) and doesn't match "most-permissive role **present** among the
  group's members," which is about actual group membership, not observed activity.

**Open item for `speckit.tasks`**: exact caching strategy (TTL vs. invalidate-on-error vs.
never-refresh-until-restart) is an implementation detail, not fixed here — flag as a task-level
decision, not a blocking unknown.

---

## 2. Does "most-permissive role" resolution actually need to distinguish GODFATHER from ADMIN?

**Decision**: No — for this feature's purposes, GODFATHER and ADMIN are equivalent, and only
"is at least one of {GODFATHER, ADMIN} present" vs. "no one above CLIENT is present" matters.

**Rationale**: `User.token_limit` (`src/models/user.py:38-47`) gives GODFATHER and ADMIN the
identical value (100,000), and `_build_morning_mcp_tools`
(`src/handlers/ai_handler.py:690-706`) gates on membership in `MORNING_MCP_AUTHORIZED_ROLES`
(a set, not an ordering) — so token limit and tool attachment are both already
GODFATHER/ADMIN-symmetric today. "Most-permissive role among the group's members" only needs
a simple precedence check (`ADMIN > GODFATHER > CLIENT > BLOCKED`, reusing
`UserManager.get_user`'s existing precedence logic, `src/managers/user_manager.py:68-78`) to
decide **which single role to resolve to for RBAC purposes**, but for every group actually in
scope for this feature (godfather + admin, the target scenario) both orderings produce
identical `token_limit`/tool-attachment outcomes.

**Alternatives considered**: A dedicated "group role" concept distinct from `Role` — rejected
as unnecessary complexity; reusing the existing `Role` enum and its existing precedence keeps
this a resolution-strategy change, not a new type.

---

## 3. Where does group-RBAC resolution get wired into the call path?

**Decision**: In `_process_conversational_message` (`denidin.py:307-397`), immediately after
`process_notification` and before `create_request`/`get_response`. For `message.is_group`
turns, resolve the most-permissive phone among the group's members and pass it explicitly as
`user_phone=` to both `AIHandler.create_request` (`ai_handler.py:587-609`) and
`AIHandler.get_response` (`ai_handler.py:842-871`) — overriding their current default
(`user_phone or message.sender_id` / `user_phone or sender`, which always resolves to the
individual sender alone). `sender=message.sender_id` continues to be passed unchanged for
message-persistence/tracking purposes (US3's per-sender attribution needs the real sender,
separately from which role's limits govern the turn).

**Rationale**: Confirmed by reading both methods end-to-end — `user_obj` is derived exactly
once per call from a single phone number (`effective_user_phone = user_phone or sender`,
`ai_handler.py:610,869`), and that same `user_obj` drives both `max_tokens`
(`ai_handler.py:911`) and `_assemble_tools`/`_build_morning_mcp_tools`
(`ai_handler.py:928,749-756,690-706`). No changes inside `AIHandler` itself are needed — the
existing `user_phone` parameter already exists precisely to let a caller override "resolve from
sender," it's just never used that way today (every current call site passes `sender` alone,
letting it default).

**Alternatives considered**: Changing `AIHandler` internals to accept a list of candidate
phones and resolve most-permissive itself — rejected; pushes group-specific logic into a
component (`AIHandler`) that has no other awareness of "group" as a concept, when the caller
(`denidin.py`) already has `message.is_group` and is the natural place to make this decision
once per turn.

---

## 4. How is "who said this" attributed on the `Message` model? (REVISED 2026-08-04)

**Original decision (retracted)**: A first pass of this research proposed a new `sender_role`
field storing the sender's RBAC role (`Role` value) per message. **Retracted** — walking
through a concrete example showed it was solving a non-problem: `Message.sender` already
stores the individual sender's raw WhatsApp id per message today, unconditionally, for every
message (group or 1:1) — confirmed by reading `_finalize_response`
(`ai_handler.py:1234-1280`) and `_store_media_turn` (`media_handler.py:271-284`) end to end.
Godfather's and admin's messages in one shared group session are *already* distinguishable by
`sender` value alone, with zero new code. RBAC role, separately, is irrelevant to "who said
this" (per explicit user feedback) and is already fully handled by §3's `user_phone` override
mechanism — nothing about it needs to touch `Message` at all. The retracted field would have
been write-only: nothing in the original design ever read it back (not even the conversation
history sent to OpenAI, which strips everything to `{role, content}` — see below).

**What was actually missing** (confirmed by re-examining the real requirement — "DeniDin
should know who said what," which for this feature concretely means (a) tell godfather's and
admin's messages apart *in the prompt the model sees*, and (b) show a human name, not a raw
phone number):

1. **`Message.sender` currently stores a raw WhatsApp id (`sender_id`, e.g.
   `"972501234567@c.us"`), never a human name.** `WhatsAppMessage.sender_name`
   (`src/models/message.py:35`, populated from Green API's `senderData.senderName`) is parsed
   today but only ever used in logging (`whatsapp_handler.py:55`, `ai_handler.py:622`,
   `denidin.py:335,362`) — never persisted onto `Message`, never used for storage/AI-context.
2. **`get_conversation_history_for_session` (`session_manager.py:222-255`) strips every stored
   message down to `{"role": ..., "content": ...}`** before it reaches OpenAI — `sender` is
   never included. So even though `sender` already distinguishes godfather from admin in
   storage, the model itself has no way to tell them apart in a shared group session today —
   this is the actual gap, not a missing storage field.
3. **The literal string `"AI"` is written as `sender`/`recipient` on assistant/user messages
   respectively** (`ai_handler.py:1241,1253,1266,1278`; `media_handler.py:275,281`;
   `denidin.py:146,353` supply/default to it) — purely as a sentinel meaning "not a real
   WhatsApp identity," fully redundant with `role` (`"assistant"` already means exactly that).
   Confirmed via grep: this value is never read/branched on anywhere (`grep -rn '"AI"' src/`
   returns only these write sites) — pure decorative redundancy, not load-bearing. Pre-existing
   in every 1:1 message today, not group-specific — explicitly brought into 039's scope per
   user decision (2026-08-04), since the same lines are being touched for item 1/2 anyway.

**Revised decision**:
- **Name resolution, no new field for it** — `WhatsAppMessage.from_notification`
  (`src/models/message.py`) gains a resolved display-name value: Green API's
  `senderData.senderContactName` (the name saved in the *receiving* WhatsApp account's own
  contact book — confirmed as a distinct, documented field from `senderName`, see §7 below) if
  present and non-empty, else `senderName`, else the raw `sender_id`. This resolved name is
  what gets passed as `sender=` at every `add_message`/`_store_media_turn` call site, replacing
  the raw id. `message.sender_id` (the raw JID) is untouched and continues to be used,
  unchanged, wherever RBAC needs a real phone number (`UserManager.get_user`) — these are now
  cleanly two different uses of "who sent this" (programmatic identity vs. display identity),
  not conflated.
- **`Message.sender`/`Message.recipient` stop writing the `"AI"` sentinel.** For a user-role
  message: `sender=<resolved display name>`, `recipient=None` (redundant with `role="user"`
  implying "sent to DeniDin"). For an assistant-role message: `sender=None` (redundant with
  `role="assistant"`), `recipient=<the same resolved display name>` (still real information —
  who this specific reply was for — not a sentinel).
- **`get_conversation_history_for_session` gains a group-aware formatting step**: when the
  session's `whatsapp_chat` is a group (`"@g.us" in session.whatsapp_chat`, same check
  `WhatsAppMessage.is_group` already uses), each `role="user"` turn's `content` is prefixed
  with `"[<sender>] "` before being returned — giving the model the missing per-turn
  attribution it needs for US5/US7's judgment calls. 1:1 sessions are unaffected (no
  ambiguity to resolve, and keeps their prompt shape unchanged). This prefixing happens only
  at the point history is formatted for OpenAI — the persisted `content` on disk stays
  unprefixed/clean.

**Alternatives considered**: A parallel `sender_role`/`sender_name` field kept alongside the
existing `sender` (rather than repurposing `sender` itself) — rejected per direct user
feedback: introduces a second representation of "who sent this" with no consumer needing the
raw id back out of storage (confirmed via grep — nothing reads `Message.sender` expecting a
phone-number shape). One field, correctly populated, is simpler and was the actual ask.
Deprecating/removing the now-mostly-vestigial `recipient=` external parameter on
`AIHandler.create_request`/`get_response` (every real caller already always passes `"AI"`) —
noted but deferred, out of scope for 039: touches public method signatures across the app,
a larger blast radius than the storage-field fix itself.

---

## 4a. Does Green API provide contact-name resolution, or do we need to build our own?

**Decision**: Green API already provides it — `senderData.senderContactName` — no custom
contacts-list implementation needed.

**Rationale**: Green API's notification schema documents two distinct name fields on
`senderData`: `senderName` (the sender's own self-set WhatsApp profile name — uncontrolled,
could be anything) and `senderContactName` (the name saved in the *receiving* WhatsApp
account's own address book for that number — exactly what a hand-built "contacts list" would
provide, except Green API resolves it automatically from WhatsApp's own contact storage).
Confirmed neither field is currently parsed for `senderContactName` in this repo — only
`senderName` is (`src/models/message.py:76`). The only work required is (a) parsing
`senderContactName` with the fallback chain in §4, and (b) an **operational** step (not code):
saving godfather/admin as real contacts under readable names on the DeniDin WhatsApp number.

**Alternatives considered**: A config-driven phone→name mapping maintained in this repo —
rejected for the same reason config-driven group membership was rejected in §1: it would drift
from reality (someone's saved contact name changes) with no code-level guard, whereas Green
API's resolution is always current because it reads the actual contact book.

---

## 5. Is there a reliable way to detect a real WhatsApp @-mention structurally?

**Decision**: No — confirmed not available on Green API's incoming webhook. Already resolved
in `spec.md`'s Clarifications session (2026-08-04); restated here since it's a Phase 0-relevant
"why we're NOT building X" research item. See spec.md for the full citation of Green API's
documented `ExtendedTextMessage` schema. Feature 039 does not add any new parsed field for
this — `"@Name"` recognition (US7) is entirely a model-content-judgment concern, implemented
via `config/runtime_constitution.md` guidance, not new code in `src/models/message.py`.

---

## 6. Where does new group-etiquette/ambiguity guidance go in the constitution?

**Decision**: A new section in `config/runtime_constitution.md` (currently 807 lines, no
existing group-specific guidance — confirmed via grep, the only "group" hit in the file is
unrelated financial-summary language at line 471).

**Rationale**: This is the established pattern for behavior that's a model judgment call rather
than hard-coded logic — e.g. existing ledger-event-recognition guidance already lives here
(referenced throughout `ai_handler.py`'s docstrings as "the runtime constitution's ... rule").
Per `AIHandler`'s system-prompt construction (`ai_handler.py`'s `_build_instructions`,
`ai_handler.py:758-774`), the constitution text is the stable, cacheable prefix of every call —
new group-etiquette guidance MUST be added as part of that same stable block, not injected
per-call, to preserve OpenAI's prompt-caching benefit (per `CLAUDE.md`'s architecture notes on
`ai_handler.py`).

**Alternatives considered**: A separate, per-call-injected "group context" string — rejected;
would break the prompt-caching property that keeps constitution-loading cheap, for content
(etiquette rules) that doesn't actually vary per call the way memories/dates do.

---

## 8. How does DeniDin send no reply at all? (NEW 2026-08-04, from test-plan review)

**Decision**: A literal sentinel string — finalized at `speckit.tasks` as `[[NO_REPLY]]`
(double-bracketed to make accidental collision with genuine Hebrew conversational text as
close to impossible as a plain-text sentinel can get)
that the model outputs as its entire `response_text` when instructed to by the constitution;
`AIHandler._finalize_response` detects it and sets a `should_reply: bool` (or equivalent) on
`AIResponse`; `_process_conversational_message` skips `WhatsAppHandler.send_response` when
`False`.

**Rationale**: Confirmed this capability doesn't exist anywhere today —
`WhatsAppHandler.send_response` (`whatsapp_handler.py:160-177`) unconditionally sends
`response.response_text`; grepping `src/`/`denidin.py` for `should_reply`/`no_reply`/
`NO_REPLY` returns nothing. A text sentinel was chosen (over a structured function-call/tool
signal) per explicit user preference — simpler, no new tool-schema/Responses-API plumbing,
consistent with how other behavior-level decisions in this feature (US1/US5/US7) are already
expressed as constitution guidance rather than hard-coded gates. The user message that
triggered a no-reply turn is still persisted (`add_message`/`add_message_with_token_limit`
called normally for it) — only the assistant-side persistence and the actual WhatsApp send are
skipped — so conversation context isn't lost even though nothing was said back.

**Alternatives considered**: A structured signal (e.g. a lightweight function-call/tool the
model invokes to declare "no reply," separate from `response_text` entirely) — more robust
against the model accidentally including extra text alongside the sentinel, but more
implementation work (new tool schema, another round-trip pattern to design) for a decision
that's ultimately about a single boolean; rejected as disproportionate for what this needs.

---

## 9. Does the new group etiquette (US1/US4a/US5/US7) extend to image messages? (NEW 2026-08-04)

**Decision**: No — confirmed as a deliberate, explicit scope boundary, not an oversight. Images
keep today's behavior unchanged: always analyzed and replied to, regardless of caption content.

**Rationale**: Traced `MediaHandler.process_media_message` end to end
(`media_handler.py:135` → `ImageExtractor.analyze_media` → `_vision_extract`,
`image_extractor.py:70-177`). Images never touch `AIHandler.get_response`/`create_request` at
all — the extractor's raw vision output IS the WhatsApp reply (`media_handler.py:148,230`,
sent verbatim via `whatsapp_handler.py:314-315`), with no second conversational pass. The
vision call does load `runtime_constitution.md` (same `_load_constitution()` helper), but
concatenated into a single `role: "user"` content block alongside a narrow, purpose-built
extraction prompt (`prompts/image_analysis.txt`) — not through the `instructions` parameter
`_build_instructions` (`ai_handler.py:758-788`) uses for text turns; the code has an explicit
"NO system message!" comment (`image_extractor.py:145`) marking this as a deliberately
different call shape. `is_bot_mentioned_in_group` was never called for media either (reconfirmed).
Caption text reaches the model as extraction context (`"User's question/message: {caption}"`,
`image_extractor.py:76-84`) but nothing checks it for addressing signals, and US4a's
`should_reply` mechanism has zero wiring in this path.

Extending etiquette to images would require real new work: reframing the extractor's prompt to
first ask "is this addressed to me" before extraction, and wiring `should_reply` detection
into `_store_media_turn`/`send_response`'s media-specific call sites (separate from the text
path's wiring, since the call shapes differ). Explicitly deferred — not bundled into 039.

**Alternatives considered**: Applying the `"@Name"` self-check only (skip images captioned to
someone else, but still process ambiguous/uncaptioned ones) — rejected as inconsistent scope
(partial etiquette is arguably more confusing than none) and still requires the same new
`should_reply` wiring in the media path that full etiquette would need, for no less effort.

---

## Summary of resolved unknowns

| # | Unknown | Resolution |
|---|---------|-----------|
| 1 | Group member discovery | `bot.api.groups.getGroupData(groupId)`, cached |
| 2 | GODFATHER vs ADMIN precedence granularity | Treat as equivalent; reuse existing `Role` precedence |
| 3 | Call-path wiring point | `_process_conversational_message`, override `user_phone=` |
| 4 | Per-message "who said this" attribution (REVISED 2026-08-04) | No new field — `Message.sender` repurposed to hold a resolved display name (not RBAC role, not a raw id); `"AI"` sentinel dropped; conversation history gains group-aware sender-name prefixing |
| 4a | Contact-name source | Green API's `senderData.senderContactName`, no custom contacts list |
| 5 | Real @-mention metadata | Confirmed unavailable; not built |
| 6 | Etiquette guidance location | New section in `config/runtime_constitution.md` |
| 7 | (folded into 4a numbering above — Green API contact-name confirmation) | — |
| 8 | How DeniDin sends no reply at all (NEW 2026-08-04) | Literal sentinel string in `response_text`, detected by `AIHandler`, `should_reply` flag skips `send_response` |
| 9 | Does etiquette extend to images? (NEW 2026-08-04) | No — confirmed architectural boundary; images keep today's unconditional behavior, deferred as a follow-on |

No NEEDS CLARIFICATION items remain unresolved.
