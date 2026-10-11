# User Stories: Group Conversation Support

**Feature**: 039-group-conversation-support
**Format**: Given-When-Then (Gherkin/BDD), per METHODOLOGY.md §I — MANDATORY, blocks spec approval until present.

Each story traces a complete flow from external entry point (a real WhatsApp group message
arriving via Green API webhook) through system processing to the resulting reply and/or
on-disk state, per METHODOLOGY.md §I's "External Input → System Processing → Output/Response"
requirement. Current-state facts below (file:line) were confirmed by reading the code, not
assumed.

**Current state** (baseline these stories change):
- `WhatsAppHandler.is_bot_mentioned_in_group` (`src/handlers/whatsapp_handler.py:82-106`)
  returns `True` unconditionally for 1:1 chats, and for groups does a case-insensitive
  substring match on `"denidin"` in the message text. Called from
  `_process_conversational_message` (`denidin.py:307-397`, gate at `denidin.py:340-341`); when
  it returns `False`, the handler logs and does a bare `return` — no AI call, no reply, and the
  message is never persisted at all.
- Group vs. 1:1 is detected once, at parse time: `WhatsAppMessage.is_group = '@g.us' in chat_id`
  (`src/models/message.py:39,79`).
- `SessionManager.get_session` (`src/managers/session_manager.py:93-127`) keys sessions by the
  raw `chat_id`. A group's `chat_id` (`...@g.us`) is structurally distinct from any member's 1:1
  `chat_id` (`...@c.us`), so group/1:1 session separation already holds today by construction.
- `UserManager.get_user` (`src/managers/user_manager.py:47-82`) resolves role from a single
  phone number against flat global config lists (`godfather_phone`, `admin_phones`,
  `blocked_phones`); precedence ADMIN > GODFATHER > BLOCKED > CLIENT. Called per-turn with
  whichever single phone number is passed in (`ai_handler.py:871`, `ai_handler.py:911` for
  `max_tokens = user_obj.token_limit`). **No "group members" concept exists anywhere** in config
  or code today (confirmed via grep) — resolving "most-permissive role among the group's
  members" requires a new mechanism to know who the members are.
- `Message.sender`/`Message.recipient` (`src/managers/session_manager.py:29-30`) already capture
  a WhatsApp identity per turn — but as a raw id/JID for user messages, and the literal string
  `"AI"` for assistant messages (`ai_handler.py:1234-1280`, `media_handler.py:271-284`),
  confirmed never read/branched on anywhere (pure redundancy with `role`). No human-readable
  name is ever stored — `WhatsAppMessage.sender_name` (`message.py:35`) is parsed but only ever
  used in logging, never persisted. `get_conversation_history_for_session`
  (`session_manager.py:222-255`) strips every message down to `{role, content}` before it
  reaches OpenAI — `sender` is never included, so even where storage *can* distinguish two
  senders, the model currently can't. (REVISED 2026-08-04: an earlier draft of this doc
  proposed a new RBAC-role field here — retracted, RBAC is irrelevant to "who said this," see
  US3.)
- Media messages (`handle_image_message` etc., `denidin.py:459-517` →
  `WhatsAppHandler.handle_media_message`, `src/handlers/whatsapp_handler.py:252-291`) never call
  `is_bot_mentioned_in_group` at all — confirmed via grep, zero references in
  `media_handler.py` or the media block of `whatsapp_handler.py`. Media in groups is already
  processed unconditionally today, regardless of mention.
- **Green API's incoming webhook carries no structured @-mention data** — confirmed 2026-08-04
  against Green API's own published `ExtendedTextMessage` notification schema (no
  `contextInfo`/`mentionedJid`/`mentionedIds` field documented anywhere in
  `extendedTextMessageData` or `quotedMessage`), independently confirmed against the installed
  `whatsapp_api_client_python` SDK and this repo's test fixtures. Explicit-mention resolution
  therefore cannot be a new parsed field on `WhatsAppMessage` — see US7, which instead treats
  the literal `"@Name"` text pattern as something the model itself interprets, same as any other
  content judgment.

---

## User Story 1 — Group text message gets a reply without needing a literal "denidin" substring (Priority: P1)

A godfather or admin sends a plain text message in the target 3-participant group (godfather +
admin + DeniDin) with no literal occurrence of the word "denidin". Today
`is_bot_mentioned_in_group` returns `False` for this and the message is silently dropped — no
reply, not even persisted. This story removes that substring check entirely and makes group
text messages addressed to DeniDin by default (the model judges content, not a hardcoded
string match), matching the target scenario where there's no one else to address.

**Why this priority**: This is the core behavior change the whole feature exists for; every
other story depends on messages reaching the AI pipeline at all.

**Independent Test**: Send a real WhatsApp group text message containing no occurrence of
"denidin" and no explicit WhatsApp @-mention of anyone, from a godfather-role sender; verify a
normal conversational reply is sent back to the group, and the message is persisted to the
group's session (keyed by the group's own `chat_id`, distinct from that sender's 1:1 session).

**Router/Integration Requirement**: The gate at `denidin.py:340-341` (call to
`WhatsAppHandler.is_bot_mentioned_in_group`, whose current implementation does
`"denidin" in message.text_content.lower()` at `whatsapp_handler.py:101`) MUST be removed, not
modified — a group message must reach `ai_handler.get_response` the same way a 1:1 message
does, by default. `"@Name"` text-pattern handling (interpreted by the model itself, not parsed
as structured data) is a separate, additive signal — see US7.

**Acceptance Scenarios**:

1. **Given** a WhatsApp group containing godfather, admin, and DeniDin, **When** the godfather
   sends "מה המצב עם התיק של X?" (no occurrence of "denidin", no explicit @-mention), **Then**
   DeniDin replies in the group with a normal conversational response.
2. **Given** the same group, **When** the admin sends a plain-text message with no mention,
   **Then** DeniDin replies the same way — mention-based gating no longer distinguishes admin
   from godfather for the purpose of "was this addressed to me."
3. **Given** a 1:1 chat (not a group), **When** a message arrives, **Then** behavior is
   byte-for-byte unchanged from today (1:1 was never gated by `is_bot_mentioned_in_group` to
   begin with).

---

## User Story 2 — Group session stays fully separate from any member's 1:1 session (Priority: P1)

Admin has a pre-existing 1:1 chat with DeniDin, entirely separate from the group. Since US1
removes the mention gate, a regression risk is that group and 1:1 traffic for the same person
could accidentally collapse into one session. This story is a regression guard proving that
doesn't happen, backed by the existing `chat_id`-keyed session lookup.

**Why this priority**: Equal priority to US1 — the requirements explicitly call out that a
group conversation and a 1:1 conversation with the same person are distinct contexts; shipping
US1 without proving this holds would risk silently merging admin's private chat history into
the group's shared context (or vice versa).

**Independent Test**: With admin's 1:1 session already containing prior history, send a group
message from admin, then a 1:1 message from admin; verify two distinct session files/records
exist (one per `chat_id`), each containing only the messages sent through that specific chat.

**Router/Integration Requirement**: `SessionManager.get_session` (`session_manager.py:93-127`)
continues to be called with the raw `chat_id` from the incoming notification, unchanged — no
new session-merging logic should be introduced by US1's gate removal.

**Acceptance Scenarios**:

1. **Given** admin has an existing 1:1 session with DeniDin, **When** admin also sends a
   message in the group, **Then** a separate session is created/used for the group's `chat_id`,
   and admin's 1:1 session is untouched (no new messages appended to it).
2. **Given** both sessions now have activity, **When** either is inspected, **Then** the
   group session's history contains only group messages, and admin's 1:1 session's history
   contains only 1:1 messages — no cross-contamination in either direction.

---

## User Story 3 — Every group message shows a human-readable sender name, visible to the model, not just storage (Priority: P1) (REVISED 2026-08-04)

Because the group session is shared across godfather and admin, DeniDin needs to know who said
what within that one shared history. **Storage already distinguishes senders today** —
`Message.sender` captures a WhatsApp identity per message already, unconditionally, group or
not (confirmed via `_finalize_response`, `ai_handler.py:1234-1280`) — so this story is not
about adding new storage capability. It's about two real gaps: (1) that stored identity is a
raw phone number, not a readable name, and (2) `get_conversation_history_for_session` strips
`sender` out entirely before the history reaches OpenAI, so the *model* has no attribution
signal at all today, even though the file on disk does. (An earlier draft of this story
proposed persisting the sender's RBAC role instead — retracted; RBAC is a separate concern,
entirely unrelated to "who said this," see US4.)

**Why this priority**: A prerequisite for US5/US7's judgment calls — the model can't reason
about "was this addressed to admin or to me" if it can't tell godfather's and admin's turns
apart in the first place.

**Independent Test**: Send one group message each from godfather and admin (both saved as
WhatsApp contacts under readable names on the DeniDin number); inspect the persisted
`Message` records — confirm `sender` holds each one's resolved contact name (not a phone
number, not "AI"). Then inspect what `get_conversation_history_for_session` returns for that
session — confirm each user turn's `content` is prefixed with `"[<name>] "`.

**Router/Integration Requirement**: `WhatsAppMessage.from_notification` (`src/models/
message.py`) MUST resolve a new `sender_display_name` attribute (Green API's
`senderData.senderContactName` → `senderName` → raw id fallback chain). Callers of
`SessionManager.add_message`/`add_message_with_tokens`/`add_message_with_token_limit`/
`_store_media_turn`-equivalent (`ai_handler.py:1234-1280`, `media_handler.py:271-284`) MUST
pass that resolved name as `sender=` for user messages (replacing the raw id), and MUST stop
writing the literal string `"AI"` (see US3a below).
`SessionManager.get_conversation_history_for_session` (`session_manager.py:222-255`) MUST
prefix each `role="user"` entry's `content` with `f"[{sender}] "` when the session is a group
session (`"@g.us" in session.whatsapp_chat`); 1:1 sessions and `role="assistant"` entries are
unaffected.

**Acceptance Scenarios**:

1. **Given** the godfather (saved as WhatsApp contact "Godfather") sends a group message,
   **When** it's persisted, **Then** the stored `Message` record has `sender` set to
   `"Godfather"`, not a phone number.
2. **Given** the admin (saved as contact "Admin") subsequently sends a message in the same
   group session, **When** persisted, **Then** its stored record shows `sender: "Admin"`,
   distinctly from the godfather's prior message.
3. **Given** both messages above, **When** `get_conversation_history_for_session` is called for
   that session, **Then** the returned history shows `"[Godfather] <content>"` and
   `"[Admin] <content>"` respectively for each user turn — the actual payload the model
   receives, not just what's on disk.
4. **Given** a sender whose number isn't saved as a WhatsApp contact on the DeniDin account,
   **When** they send a group message, **Then** `sender` falls back to their WhatsApp profile
   name (`senderName`), or the raw number if that's also unavailable — never an error, never a
   blank value.

---

## User Story 3a — Retire the redundant `"AI"` sender/recipient sentinel (Priority: P2) (NEW 2026-08-04)

Pre-existing, not group-specific: every stored assistant message has `sender: "AI"` and every
stored user message has `recipient: "AI"` (`ai_handler.py:1241,1253,1266,1278`,
`media_handler.py:275,281`) — confirmed via grep, this literal string is never read or
branched on anywhere in the codebase, purely redundant with `role` (`"assistant"` already
unambiguously means "this is DeniDin"). Brought into 039's scope per explicit user decision,
since US3 is already touching these exact call sites for the sender-name fix.

**Why this priority**: Lower than US3 (its own prerequisite) — this is a cleanup riding along
with US3's changes to the same lines, not something blocking any other story.

**Independent Test**: Send any message (group or 1:1); inspect the two persisted `Message`
records for that turn — confirm the user message has `recipient: null` (not `"AI"`) and the
assistant message has `sender: null` (not `"AI"`), while the assistant message's `recipient`
holds the resolved display name of who it replied to.

**Router/Integration Requirement**: The same four `ai_handler.py` call sites and two
`media_handler.py` call sites from US3 stop passing the literal `"AI"` — `recipient=None` for
user-message calls, `sender=None` for assistant-message calls (their `recipient=` becomes the
resolved display name, not the raw id, consistent with US3).

**Acceptance Scenarios**:

1. **Given** any message turn (1:1 or group), **When** the user-role message is persisted,
   **Then** its `recipient` field is `null`.
2. **Given** the same turn, **When** the assistant-role reply is persisted, **Then** its
   `sender` field is `null` and its `recipient` field holds the resolved display name of the
   human it replied to (not `"AI"`, not a raw phone number).
3. **Given** this change applies identically to 1:1 chats, **When** a 1:1 message is sent,
   **Then** behavior is otherwise unchanged — only the `sender`/`recipient` field values
   differ, not routing, replies, or session behavior.

---

## User Story 4 — Group session RBAC uses the most-permissive role present among its members (Priority: P1)

Per the Clarifications answer, a group's token limit and tool access (e.g. Morning MCP
attachment, gated to godfather/admin today) should be governed by the highest-privilege role
present among the group's members, not resolved per-sender per-turn. Today, role resolution
(`UserManager.get_user`) only ever looks at a single phone number per call, and no concept of
"this group's members" exists in config or code — this story introduces that resolution.

**Why this priority**: Equal priority to US1-US3 — without this, a group containing a godfather
would incorrectly apply per-sender limits (e.g. capping the godfather's own turn at a
lower limit if resolution defaulted to "sender only" instead of "most-permissive present"),
contradicting the explicit clarification.

**Independent Test**: In the target 3-participant group (godfather + admin), send a message
from admin; verify the turn is processed with godfather-level token limit and tool access
(not admin-level), because the group's most-permissive present member is the godfather.

**Router/Integration Requirement**: `AIHandler.get_response`/`create_request`
(`ai_handler.py:842-871`, `ai_handler.py:587-609`) currently resolve role from a single
`effective_user_phone` per call — for `message.is_group` turns, this MUST instead resolve the
most-permissive role across the group's known members before computing `max_tokens`
(`ai_handler.py:911`) and RBAC-gated tool attachment (e.g. Morning MCP), rather than using only
the sender's own role. (How "the group's known members" is determined — e.g. Green API group
participants lookup vs. new config — is an implementation decision for `speckit.plan`, not
fixed by this story.)

**Acceptance Scenarios**:

1. **Given** the group's members are a godfather and an admin, **When** the admin sends a
   message, **Then** the turn's token limit matches the godfather's `token_limit` config value,
   not the admin's.
2. **Given** the same group, **When** the godfather sends a message, **Then** behavior is
   unchanged from today (already the most-permissive role, so per-sender and
   most-permissive resolution agree).
3. **Given** a hypothetical group containing only client-role members (no godfather/admin
   present), **When** a message arrives, **Then** RBAC resolves to the highest role actually
   present (client), not silently escalated.

---

## User Story 4a — DeniDin can send no reply at all (Priority: P1) (NEW 2026-08-04)

Foundational infrastructure both US5 and US7 depend on. Confirmed: nothing in this app today
lets DeniDin decline to reply — `WhatsAppHandler.send_response` (`whatsapp_handler.py:160-177`)
unconditionally sends whatever `response.response_text` is; every message that reaches the AI
pipeline currently always gets a reply sent, with no existing "skip sending" path anywhere
(`grep` for `should_reply`/`no_reply`/`NO_REPLY` across `src/`/`denidin.py` returns nothing).

**Why this priority**: P1, not P2 — both US5's "clearly for someone else" outcome and US7's
"@Name doesn't refer to me" outcome are meaningless without this; it's a shared prerequisite,
not itself the exception-path behavior.

**Independent Test**: Trigger a turn where the model outputs the no-reply sentinel; verify no
WhatsApp message is sent, but the triggering user message is still persisted to the session
(conversation context isn't lost, even though nothing was said back).

**Router/Integration Requirement**: The model outputs a specific literal sentinel string as its
entire `response_text` (finalized at `speckit.tasks` as the literal `[[NO_REPLY]]`) when instructed to
by the constitution (US5/US7's guidance). `AIHandler._finalize_response`
(`ai_handler.py:1102-1284`) MUST detect this sentinel and expose a `should_reply: bool` (or
equivalent) on `AIResponse`, still performing the normal `add_message`/
`add_message_with_token_limit` persistence for the user's message (and skipping persistence of
an assistant reply, since none was actually sent). `_process_conversational_message`
(`denidin.py:307-397`) MUST check this flag and skip calling
`WhatsAppHandler.send_response` when `should_reply` is `False`.

**Acceptance Scenarios**:

1. **Given** the model outputs the no-reply sentinel for a turn, **When** `_finalize_response`
   processes it, **Then** no call to `WhatsAppHandler.send_response` happens for that turn.
2. **Given** the same turn, **When** inspected afterward, **Then** the triggering user message
   is still persisted to the session, but no corresponding assistant-role message was created.
3. **Given** a normal turn where the model does NOT output the sentinel, **When** processed,
   **Then** behavior is completely unchanged — a reply is sent exactly as today.

---

## User Story 5 — DeniDin distinguishes "clearly for someone else" (silent) from "genuinely unclear" (asks) — never conflating the two (Priority: P2) (REVISED 2026-08-04)

Even with the mention gate removed, godfather and admin might occasionally address each other
directly in the group rather than DeniDin (e.g. using the other person's name, or replying to
each other's prior message), with no explicit WhatsApp `"@Name"` pattern either way (US7
handles that case, and takes precedence when present). **This story originally conflated two
different outcomes into one "ask for clarification" bucket — corrected after review.** There
are three distinct outcomes for a group message, not two:
1. Clearly directed at DeniDin → answer normally (US1's default).
2. **Clearly directed at another human** (not actually ambiguous — just unmarked) → **silent,
   no reply, no question** (US4a's no-reply mechanism). This is the corrected case: earlier
   wording had this asking a clarifying question, which is wrong — there's nothing to clarify
   when it's already clear.
3. **Genuinely unclear** whether it's for DeniDin or someone else → ask a short clarifying
   question. This is now the *only* case that asks anything, and it's narrower than "not
   obviously addressed to me" — it requires actual ambiguity, not just absence of an explicit
   marker.

**Why this priority**: Lower priority than US1/US4/US4a because it's explicitly the exception
path, not the common case — the target scenario has no one else in the group to address, so
this mostly matters for the generalized "any group" case.

**Independent Test**: Two separate scenarios needed (they exercise different outcomes):
- *Clearly-for-someone-else*: godfather sends a message using the admin's name in clear,
  unambiguous 2nd-person address (e.g. "X, תזכיר לי אחר כך" where X is admin's actual name),
  with no `"@"` pattern; verify DeniDin sends no reply at all (US4a).
- *Genuinely-unclear*: godfather sends a message that could plausibly be read either as a
  question to DeniDin or as a comment to admin (deliberately ambiguous phrasing, no name, no
  `"@"` pattern); verify DeniDin asks a short clarifying question rather than guessing either
  way.

**Router/Integration Requirement**: Prompt/behavior-level, not a hard routing gate —
`config/runtime_constitution.md` (loaded per `AIHandler`'s system-prompt construction) needs
group-etiquette guidance that explicitly separates these two outcomes (silent vs. ask) rather
than merging them, and instructs the model to output US4a's no-reply sentinel for the
clearly-for-someone-else case specifically (not for the genuinely-unclear case, which gets a
normal clarifying-question reply). This guidance only applies when US7's `"@Name"` signal is
absent — an explicit `"@Name"` pattern (whether or not it refers to DeniDin) always wins over
this content-based judgment.

**Acceptance Scenarios**:

1. **Given** a group message clearly directed at another human by name/2nd-person phrasing (not
   ambiguous), with no `"@"` pattern, **When** processed, **Then** DeniDin sends no reply at all
   (US4a) — not a clarifying question.
2. **Given** a group message whose content is genuinely unclear (could plausibly be for DeniDin
   or for a human participant), **When** processed, **Then** DeniDin asks a short clarifying
   question rather than guessing either way.
3. **Given** an ordinary message with no such signal (the common case), **When** processed,
   **Then** DeniDin answers normally — neither the silent path nor the ask path fires on
   typical traffic.
4. **Given** the target 2-human scenario (godfather + admin only, no one else to address),
   **When** either sends an ordinary message, **Then** neither exception path fires —
   consistent with the spec's "exception path, not the common case" requirement.
5. **Given** a message whose content alone would look ambiguous, **When** it also carries an
   explicit `"@Name"` pattern, **Then** neither of this story's paths fire at all — US7's
   explicit-mention resolution takes over instead.

---

## User Story 6 — Media messages in a group keep working unchanged, with the same sender-tagging — and NONE of US1/US4a/US5/US7's etiquette logic (Priority: P3) (SCOPE CLARIFIED 2026-08-04)

Media handling (`handle_image_message` etc.) never had a mention gate to begin with, so US1's
gate removal doesn't change its routing. This story is a regression guard confirming media
stays fully functional post-change, and picks up the same sender-attribution as US3 applies to
text. **Explicitly confirmed out of scope**: none of US1's default-address judgment, US4a's
no-reply mechanism, US5's silent/ask split, or US7's `"@Name"` self-check apply to images —
this is a real architectural boundary (see spec.md's Clarifications), not an oversight.
`MediaHandler.process_media_message` never calls `AIHandler.get_response`/`create_request` at
all — it calls `ImageExtractor.analyze_media` directly, and that extractor's raw vision output
IS the WhatsApp reply, with no `should_reply` wiring and no caption-addressing check anywhere.
A captioned image clearly addressed to another participant (e.g. `"@Admin תראה את זה"`) still
gets fully analyzed and replied to, unchanged from today.

**Why this priority**: Lowest priority — it's confirming a no-op on the routing side, plus
extending an already-designed mechanism (US3) to the media path; no new routing logic is
introduced.

**Independent Test**: Send a real image (e.g. a bank-deposit screenshot) in the group from
admin; verify it's processed exactly as it is today (extraction, any ledger-event capture,
reply), and the resulting stored media-turn message carries admin's resolved display name per
US3 (not a raw phone number, not "AI").

**Router/Integration Requirement**: No change to `denidin.py:459-517` /
`WhatsAppHandler.handle_media_message` routing. The only requirement is that `_store_media_turn`
(`media_handler.py:245-284`, already touched by US3/US3a for the sender-name and `"AI"`-sentinel
fixes) applies those same fixes on the media path, not just the text path.

**Acceptance Scenarios**:

1. **Given** the group, **When** admin sends an image, **Then** it's processed identically to
   today's 1:1/group-unchanged behavior (extraction quality, any ledger-event capture, reply
   content) — no regression from US1's routing change.
2. **Given** the same media turn, **When** the resulting message is persisted, **Then** its
   `sender` holds admin's resolved display name, consistent with US3's fix for text messages.
3. **Given** an image sent with a caption that would clearly trigger US5's silent path or US7's
   no-reply path if it were plain text (e.g. captioned `"@Admin תראה את זה"`), **When**
   processed, **Then** DeniDin still fully analyzes the image and sends a substantive reply —
   none of the etiquette/no-reply logic fires for media, confirming the scope boundary above.

---

## User Story 7 — DeniDin recognizes a text-based "@Name" mention, checking only whether it refers to itself (Priority: P2) (REVISED 2026-08-04)

Green API's incoming webhook carries no structured @-mention metadata (confirmed 2026-08-04
against Green API's own published notification schema — see "Current state" above), so this
can't be a new parsed field the way `is_group`/`chat_id` are. What WhatsApp's native @-mention
UI does reliably do is insert visible `"@DisplayName"` text into the message body — an
observable, real piece of text, just not structured data. **Corrected framing**: the model does
NOT need to identify *who* `Name` refers to — only whether it refers to DeniDin itself. This is
a purely self-referential check, anchored on `runtime_constitution.md`'s existing "Core
Identity" line ("You are DeniDin...") — no new config, no dependency on knowing real group
members. Any `Name` that isn't a recognizable reference to DeniDin counts as "not me," whether
it's a real participant's name, a nickname, or arbitrary text (e.g. `"@lalalal"`, `"@papapa"`)
— the model never resolves who the message is *actually* for, only that it isn't DeniDin.

**Why this priority**: Equal priority to US5 — it's the other half of the same "how do we know
who a message is for" problem, and is what makes US5's exception paths genuinely rare rather
than the primary mechanism: a group message that visibly `"@"`-tags something is a much
stronger signal than prose alone, so the model should weigh it heavily rather than treat it as
just more ambiguous content.

**Independent Test**: In a group with godfather, admin, and DeniDin, have the godfather type a
message containing `"@"` followed by literally anything that isn't a reference to DeniDin (a
real participant's name, or arbitrary text like `"@lalalal"` — both must produce the same
result, since the model isn't identifying a specific addressee); verify DeniDin sends no reply
at all (US4a's no-reply mechanism, not a clarifying question — this is unambiguous). Separately,
have the godfather `"@"`-tag DeniDin (e.g. `"@DeniDin"`) in a message whose surrounding content
alone would otherwise look ambiguous; verify DeniDin replies normally despite the ambiguous
content.

**Router/Integration Requirement**: No new parsed field on `WhatsAppMessage` — this is
prompt/behavior-level, same as US5. `config/runtime_constitution.md` needs guidance instructing
the model to recognize a literal `"@Name"` pattern in message text and check only whether
`Name` plausibly refers to itself (its established "Core Identity") — if not, output US4a's
no-reply sentinel; if so, answer normally regardless of surrounding ambiguity. Checked by the
model before falling back to US5's softer, no-`"@"`-pattern judgment.

**Acceptance Scenarios**:

1. **Given** a group message containing an `"@Name"` pattern where `Name` is not a recognizable
   reference to DeniDin (a real participant's name OR arbitrary text like `"@lalalal"` — both
   must behave identically), **When** processed, **Then** DeniDin sends no reply at all
   (US4a) — regardless of what the rest of the message text says, and regardless of whether
   `Name` corresponds to any real group member.
2. **Given** a group message whose surrounding content alone reads ambiguously (would otherwise
   trigger US5's ask-a-question path), **When** the message also contains an `"@Name"` pattern
   naming DeniDin, **Then** DeniDin answers normally — the `"@"`-tag resolves the ambiguity
   outright, no clarification question is sent, no no-reply sentinel is output.
3. **Given** a group message with no `"@Name"` pattern at all, **When** processed, **Then**
   routing falls through to US1's content-based default (and US5's silent/ask paths as the
   exception cases) unchanged — US7's signal only applies when a literal `"@Name"` pattern is
   actually present in the text.
