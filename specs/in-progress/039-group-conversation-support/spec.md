# Feature Spec: Group Conversation Support

**Feature ID**: 039-group-conversation-support
**Priority**: TBD
**Status**: Tasked (`plan.md`/`research.md`/`data-model.md`/`contracts/`/`quickstart.md`/
`tasks.md` all written; ready for `speckit.implement`, pending human approval of each
test task per the TDD gate)
**Created**: August 4, 2026

---

## Problem Statement

Today, group messages are only processed if the bot's name is
substring-matched in the text (`WhatsAppHandler.is_bot_mentioned_in_group`,
`apps/denidin-app/src/handlers/whatsapp_handler.py`, line 82); otherwise
`_process_conversational_message` (`denidin.py`, line 307) logs and returns
early with no reply. The entire group shares one session/memory keyed by the
group's own `chat_id` (`SessionManager.get_session`,
`src/managers/session_manager.py`, line 93; `AIHandler.create_request`/
`get_response`, `src/handlers/ai_handler.py`, lines 587/842), with no
distinction between which member sent a given message.

**Target scenario**: a WhatsApp group containing exactly three participants
— godfather, admin, and DeniDin itself. Godfather sends most messages;
admin occasionally joins in. Both address DeniDin **implicitly** — no
@mention — since godfather and admin are not expected to converse with each
other in this group (they have a separate channel for that). Admin also has
a pre-existing separate 1:1 chat with DeniDin, which must keep being managed
as its own distinct session, entirely separate from this group's session.

## Clarifications

### Session 2026-08-04

- Q: Inside the shared group session, whose RBAC role (token limit /
  permissions) governs a given turn? → A: Most-permissive member's role —
  the whole group session is governed by the highest-privilege role present
  among the group's members (e.g. godfather), regardless of which member
  actually sent a given message.
- Q: What signal should trigger the "ask for clarification" ambiguity path
  (vs. defaulting to "this is addressed to DeniDin")? → A: Content-based —
  regardless of participant count, if a message's text appears directed at
  another human (uses another member's name, replies to their message,
  2nd-person phrasing that doesn't fit DeniDin), treat it as ambiguous/not
  necessarily for DeniDin and ask for clarification rather than guessing.
- Q: Is per-sender attribution needed within the shared group session
  history (so DeniDin knows who said what)? → A: Yes — every message stored
  in the group session is tagged with the sender's identity, so DeniDin's
  context (and the ambiguity/content-based check above) can use it.
  **REVISED 2026-08-04, after a design walkthrough with the user**: the
  original answer here led to a proposed `sender_role` field (RBAC role,
  e.g. "GODFATHER") — retracted as solving the wrong problem. RBAC role is
  irrelevant to "who said this" (confirmed: not needed at all for this
  concern, per direct user feedback) and was already fully handled
  separately (see the most-permissive-role requirement below). What was
  actually missing: (1) `Message.sender` already stores the individual
  sender's raw WhatsApp id per message today, for every message, group or
  not — no new field needed for basic distinguishability; (2) that raw id
  is a phone number, not a readable name, and the user prefers a name; (3)
  the conversation history actually sent to OpenAI strips every message
  down to `{role, content}` — `sender` was never included, so the model
  itself couldn't tell godfather and admin apart in a shared session even
  though storage could. Fixed by: resolving a real display name via Green
  API's own contact-book field (`senderContactName`, see next entry) into
  `Message.sender` (replacing the raw id), and adding a group-aware
  formatting step that prefixes each user turn's content with `"[<sender>]
  "` when building the history sent to OpenAI — so the model, not just the
  stored file, knows who said what. No new field.
- Q: Where does the display name come from — a phone number, or something
  readable? → A: Green API's `senderData.senderContactName` (the name
  saved in DeniDin's own WhatsApp contact book for that number) — already
  provided by Green API automatically, confirmed distinct from the
  already-parsed `senderName` (the sender's own self-set profile name).
  No custom contacts-list implementation needed on our side; the only
  requirement is an operational one — godfather and admin need to actually
  be saved as contacts under readable names on the DeniDin WhatsApp number.
  Fallback chain if `senderContactName` is absent: `senderName`, then the
  raw phone number.
- Q: While touching this exact storage code, should the pre-existing
  `sender="AI"`/`recipient="AI"` sentinel convention (used identically for
  every 1:1 message today, not group-specific) also be cleaned up? → A:
  Yes, included in this feature's scope — confirmed via grep that the
  literal string `"AI"` is written to `Message.sender`/`Message.recipient`
  but never read/branched on anywhere in the codebase; it's pure redundancy
  with `Message.role` (`"assistant"` already unambiguously means "this is
  DeniDin"). Replaced: a user-role message's `recipient` becomes `None`
  (redundant with `role`); an assistant-role message's `sender` becomes
  `None` (redundant with `role`), and its `recipient` becomes the same
  resolved display name as the paired user message (still real
  information — who this specific reply was for — not a sentinel).
- Q: Should the current literal `"denidin"` text-substring check
  (`WhatsAppHandler.is_bot_mentioned_in_group`,
  `src/handlers/whatsapp_handler.py:82-108`) be kept as the mechanism for
  detecting an explicit mention, alongside the new content-based default? →
  A: No — the substring check is removed entirely, not repurposed. Replaced
  by content-based model judgment, described in the next entry.
- Q (2026-08-04, after test-plan review): For a message clearly directed at
  another human (not ambiguous, just unmarked), should DeniDin ask a
  clarifying question, same as the genuinely-unclear case? → A: No — these
  are different outcomes. Clearly-for-someone-else means silence, no reply,
  no question. Asking a clarifying question is reserved exclusively for
  genuinely unclear cases — this was a real gap in the original US5
  wording, which had conflated "content appears directed at another human"
  with "ask for clarification" into one bucket. Fixed: three distinct
  outcomes now (answer / silent / ask), not two.
- Q: For US7's `"@Name"` recognition, does the model need to know who the
  real group members are, to identify who `Name` refers to? → A: No —
  confirmed unnecessary. The check is purely self-referential: does `Name`
  plausibly refer to DeniDin itself (its "Core Identity," already
  established as the first line of `runtime_constitution.md` — no new
  config needed)? Anything that isn't a recognizable reference to DeniDin
  counts as "not me," regardless of whether it's a real participant's name
  or arbitrary text (e.g. `"@lalalal"`) — the model never needs to
  determine who specifically is being addressed, only whether it's itself.
- Q (2026-08-04): Does the new group etiquette (US1's default-address, US5's
  silent/ask split, US7's `"@Name"` self-check, and the underlying no-reply
  mechanism) extend to image messages — e.g. an image captioned
  `"@Admin תראה את זה"` (clearly for admin, not DeniDin)? → A: **No — images
  are explicitly out of scope for all of this; they keep today's behavior
  unchanged (always analyzed and replied to, regardless of caption
  content).** This is a real architectural boundary, not an oversight:
  traced end to end, `MediaHandler.process_media_message` never calls
  `AIHandler.get_response`/`create_request` at all — it calls
  `ImageExtractor.analyze_media` directly, and that extractor's raw vision
  output IS the WhatsApp reply, sent verbatim, with no second conversational
  pass afterward. The vision call does load `runtime_constitution.md`'s
  text (same `_load_constitution()` helper as the text path), but
  concatenated into a single `role: "user"` content block alongside a
  narrow, purpose-built extraction prompt (`prompts/image_analysis.txt`) —
  not through the `instructions` parameter `_build_instructions` uses for
  text turns (the code has an explicit "NO system message!" comment).
  `is_bot_mentioned_in_group` was never called for media either (confirmed
  again). Caption text does reach the model as extra extraction context,
  but nothing checks it for `"@Name"`/addressing signals, and the
  `should_reply` mechanism (US4a) has zero wiring in this path — even if
  the model somehow emitted the no-reply sentinel, `_store_media_turn`/
  `send_response` would send it as if it were a real analysis. Extending
  etiquette here would require real new work (reframing the extractor's
  prompt, wiring `should_reply` detection into the media path) — deferred
  as its own potential follow-on feature, not bundled into 039.
- Q: Is real, structured WhatsApp @-mention metadata (e.g. `contextInfo`/
  `mentionedJid`) available on Green API's incoming webhook, to use as a
  hard override signal? → A: **No — confirmed not available.** Checked
  against Green API's own published incoming-notification schema for
  `ExtendedTextMessage` (2026-08-04): the documented `extendedTextMessageData`
  fields are `text`, `description`, `title`, `containsAutoReply`,
  `mediaType`, `showAdAttribution`, `sourceId/Type/Url`,
  `conversionSource`, `entryPointConversionApp`, `jpegThumbnail`,
  `thumbnailUrl`, `isForwarded`, `forwardingScore`, `previewType`; the
  nested `quotedMessage` only has `stanzaId`, `participant`, `typeMessage`,
  plus quoted-content fields — no mention field anywhere. (Green API's
  *outgoing* `SendMessage` API does support a `mentions`-style parameter for
  DeniDin to tag someone when replying, but that's one-directional — there
  is no equivalent on the receiving side.) This was independently confirmed
  against the installed `whatsapp_api_client_python` SDK and this repo's own
  test fixtures — no mention field anywhere reachable from this codebase
  either. **Decision**: don't build a structured-metadata path at all. A
  real WhatsApp @-mention still inserts visible `"@DisplayName"` text into
  the message body (this part is a real, observable WhatsApp client
  behavior, not Green API metadata) — so explicit-mention resolution is a
  **text-based signal the model itself interprets** as part of its normal
  content judgment: when a message contains an `"@Name"` pattern, DeniDin
  checks only whether `Name` refers to itself — no new parsed field, no
  Green API research dependency, no separate override mechanism from the
  content-based judgment already described. **Correction (2026-08-04, see
  the later "For US7's `\"@Name\"` recognition" entry above for the full
  resolution): this entry originally said the model "determines from
  context/the group's known members whether that `Name` refers to itself
  or to a different participant" — that phrasing implied the model needs
  to know real group members. It doesn't.** The check is purely
  self-referential (does `Name` plausibly refer to DeniDin's own "Core
  Identity"?) — anything that isn't a recognizable reference to DeniDin
  counts as "not me," whether or not it corresponds to any real
  participant. This deliberately keeps the same fragility profile as any
  text-based recognition (it depends on the model correctly recognizing
  itself vs. not-itself from the `@`-tagged name), but does not depend on
  any data Green API doesn't actually provide, and does not depend on
  knowing who else is in the group.

## Requirements (draft, generalized beyond the specific 2-human scenario to
any group DeniDin is added to)

- Remove the current literal `"denidin"` text-substring mention check
  entirely (`WhatsAppHandler.is_bot_mentioned_in_group`) — it is not
  repurposed or kept as a fallback. Group message routing is instead
  decided entirely by the model's own content judgment, informed by prompt
  guidance (no new parsed fields, since Green API's webhook carries no
  structured mention data — per the Clarifications entry above).
- By default, a group message is treated as addressed to DeniDin — the
  model judges this from content, and it will practically always be true,
  since in the target scenario there's no one else in the group to
  address.
- When a message contains a WhatsApp-style `"@Name"` mention pattern in its
  text, the model checks only whether `Name` plausibly refers to DeniDin
  itself (its own established identity — "Core Identity" in
  `runtime_constitution.md`, no new config) — it does **not** need to
  identify who else is being addressed. If `Name` doesn't refer to DeniDin
  (any other string — a real participant's name, a nickname, or arbitrary
  text like `"@lalalal"`), the message is directed at someone else, not
  DeniDin — **no reply is sent at all** (see the no-reply mechanism below;
  this is not the same as asking a clarifying question — nothing is
  ambiguous here, it's unambiguously not for DeniDin). If `Name` does refer
  to DeniDin, the message is directed at DeniDin, and the model should
  answer even if the surrounding content would otherwise look ambiguous.
- The group needs "etiquette" behavior for the remaining case: no `"@Name"`
  pattern either way, but the message's content still appears directed at
  another human participant rather than DeniDin. This splits into two
  outcomes, not one: if it's **clearly** directed at another human (not
  actually ambiguous, just unmarked by an `"@"`), DeniDin stays silent — no
  reply, no question, same no-reply mechanism as the `"@Name"`-not-DeniDin
  case above. Only when it's **genuinely unclear** whether the message is
  for DeniDin or for someone else does DeniDin ask a short clarifying
  question rather than silently guessing — this ask-a-question path is the
  narrowest of the three outcomes, not the general fallback for "not
  obviously addressed to me."
- **New capability required**: nothing in this app today lets DeniDin send
  no reply at all — `WhatsAppHandler.send_response` unconditionally sends
  whatever the AI response text is; every message that reaches the AI
  pipeline currently always gets a reply. This feature introduces that
  capability for the first time: the model outputs a specific literal
  sentinel string (finalized at `speckit.tasks` as the literal `[[NO_REPLY]]`) as
  its entire response when it determines a message isn't for DeniDin;
  `AIHandler` detects the sentinel and signals "don't send," and the
  message is still persisted to the session (for conversational context
  continuity) even though nothing is sent back to WhatsApp.
- The group's own session must be tracked separately from any individual
  member's 1:1 session with DeniDin (e.g. admin's existing private chat) —
  a group conversation and a 1:1 conversation with the same person are
  distinct contexts, not merged.
- Every message persisted into the group's shared session must be tagged
  with the sending member's real, human-readable name (resolved via Green
  API's own contact-book field, not a phone number, not an RBAC role), so
  DeniDin's context can use per-sender attribution even though the session
  itself is shared. This attribution must reach the model itself, not just
  the stored file — conversation history built for a group session must
  visibly label who said each turn.
- RBAC for a group session is governed by the most-permissive role present
  among the group's members (e.g. a group containing a godfather uses
  godfather-level token limits/tool access for the whole session), not
  resolved per-sender per-turn. This is entirely independent of the
  sender-name attribution above — RBAC never touches `Message` storage.
- The pre-existing `sender="AI"`/`recipient="AI"` sentinel convention
  (used identically for every 1:1 message today) is retired as part of
  this feature, since the same storage code is being touched anyway: a
  user message's `recipient` and an assistant message's `sender` become
  `None` (redundant with `role`, which already distinguishes them); an
  assistant message's `recipient` becomes the resolved display name of who
  it replied to.
- Media (images) and text should both be handled in a group exactly as they
  are in a 1:1 chat today — no reduced feature set; only the
  routing/gating and session-identity rules change. **Explicitly, this means
  none of the new etiquette behaviors above (default-address judgment,
  silent/ask split, `"@Name"` self-check, no-reply mechanism) apply to
  images** — a captioned image addressed to another participant still gets
  analyzed and replied to by DeniDin, exactly as today. See the
  Clarifications entry above for why this is a deliberate scope boundary,
  not an oversight.

---

`user-stories.md` (Given-When-Then, P1-P3, 9 stories), the full `speckit.plan` output
(`plan.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`), and `tasks.md`
(`speckit.tasks`, 20 tasks across 12 phases) have all been written for this feature — see
`specs/in-progress/039-group-conversation-support/`. `speckit.analyze` has run (2026-08-04)
and its findings have been remediated. Ready for `speckit.implement`.
