# Implementation Plan: Group Conversation Support

**Branch**: `feature/039-group-conversation-support` | **Date**: 2026-08-04 | **Spec**: `./spec.md`
**Input**: Feature specification from `specs/in-progress/039-group-conversation-support/spec.md`
**Estimated Duration**: 5-7 days (revised 2026-08-04 — original 3-5 day estimate predated the
no-reply mechanism (US4a, genuinely new app infrastructure), US5's 3-way behavior split, and
the 9-story/20-task final scope; routing change + new RBAC resolution component with a real
external dependency [Green API group lookup] + new no-reply plumbing + constitution/prompt
guidance + tests across unit/integration/billed tiers; no new UI, no data migration)

---

**IMPORTANT**: This plan complies with:
- **CONSTITUTION.md** (§I-III): No env vars (Green API groups client injected via constructor,
  same DI pattern as every existing manager), UTC timestamps unchanged (no new timestamp
  handling introduced), feature branch + merge-commit workflow.
- **METHODOLOGY.md** (§II, IV, VII): Template structure, phased planning, Integration Contracts
  (`contracts/group-rbac-resolution.md`, `contracts/message-sender-role.md`,
  `contracts/no-reply-mechanism.md`, all written).

---

## Summary

Remove the current literal `"denidin"` text-substring gate on group messages
(`WhatsAppHandler.is_bot_mentioned_in_group`) and replace it with content-based model judgment
as the default (a group message is addressed to DeniDin unless content clearly says otherwise).
Two exception paths, both driven by new `config/runtime_constitution.md` guidance rather than
hard-coded gates: US7's `"@Name"` pattern (a purely self-referential check — does `Name` refer
to DeniDin or not, never "who does it refer to") and US5's no-`"@"`-pattern content judgment,
now correctly split into three outcomes instead of two — answer (clear, for DeniDin) / silent
(clear, for someone else) / ask a question (genuinely unclear) — a real gap found and fixed
after initial test planning, since the original wording conflated "clear but not for me" with
"ask for clarification." The silent outcome requires new infrastructure this app doesn't have
today (US4a): a literal sentinel string the model outputs to mean "send nothing," detected by
`AIHandler` and threaded through as a `should_reply` flag. No new parsed fields for @-mention
data, since Green API's incoming webhook carries no structured @-mention data (confirmed).
**None of US1/US4a/US5/US7 extend to image messages** — confirmed a real architectural
boundary (research.md §9), not an oversight: images never route through
`AIHandler.get_response`, so this etiquette logic has nothing to attach to without separate,
deferred work. US6 explicitly regression-guards that images keep today's unconditional
behavior.
Separately, resolve a real human-readable sender name (Green API's `senderContactName`, no
custom contacts list needed) and surface it both in storage (`Message.sender`, replacing the
raw phone id — no new field) and in what the model actually sees (a new group-aware prefix in
`get_conversation_history_for_session`, US3) — the earlier plan for a new `sender_role` RBAC
field was retracted after review, since it was write-only and RBAC is unrelated to "who said
this." While touching those exact call sites, also retire the pre-existing, app-wide
`sender="AI"`/`recipient="AI"` sentinel convention, confirmed redundant with `Message.role`
(US3a). Separately, add most-permissive-role RBAC resolution for group turns (a new
`GroupMembershipResolver` component backed by a live `bot.api.groups.getGroupData` call, US4) —
additive to `AIHandler`'s existing `user_phone`-override capability, requiring no changes
inside `AIHandler` itself. Group/1:1 session separation (US2) already holds today by
construction and needs only a regression-guard test, not new code.

## Technical Context

**Language/Version**: Python 3.9+ (existing project floor, `apps/denidin-app`)
**Primary Dependencies**: `whatsapp_api_client_python` (already a dependency — this feature is
the first caller of its `bot.api.groups.getGroupData` method, no new package)
**Storage**: Existing flat-JSON message/session files (`data/sessions/`) — no new fields; two
existing `Message` fields (`sender`/`recipient`) change what value they're populated with (see
data-model.md), no migration needed (historical messages keep their old values, read fine as-is
— this is a go-forward formatting change, not a schema change)
**Testing**: `pytest` — `tests/unit/` (new `GroupMembershipResolver` tests, `SessionManager`
sender/recipient-value tests, `WhatsAppMessage.sender_display_name` resolution/fallback-chain
tests, `AIHandler` no-reply-sentinel-detection tests), `tests/integration/` (real webhook-shaped
group notification dispatched through `bot.router`, per CONSTITUTION §V's true-integration
requirement — covers US1/US2/US3/US3a/US4/US4a/US6 routing/persistence/RBAC/no-reply behavior
with real internal objects), `tests/billed/` (real, text-only OpenAI calls to verify the
model's content-based judgment — 6 cases, none needing vision/image:
1. US1 — plain group message, no signal → substantive reply (default-address)
2. US5 — clearly directed at another human, no `"@"` → no reply sent at all (silent, not a question)
3. US5 — genuinely unclear content, no `"@"` → a clarifying question is sent (not silent, not a substantive answer)
4. US5 (negative) — ordinary unambiguous message → substantive reply, neither exception path fires
5. US7 — `"@Name"` where `Name` isn't DeniDin (real name or arbitrary text) → no reply sent at all
6. US7 — ambiguous content but `"@DeniDin"` present → substantive reply despite the ambiguity

these are genuinely model-behavior questions, not deterministic code paths, so they need real
API calls per CONSTITUTION's zero-mocking policy). No new `tests/expensive/` needed — US6 is a
media-path regression guard against unchanged code, already covered by existing expensive media
tests.
**Target Platform**: Same as rest of `apps/denidin-app` — Docker container, Linux
**Project Type**: Single project (existing `apps/denidin-app` structure)
**Performance Goals**: N/A — group traffic volume is low (single-digit groups, per the target
scenario); the one new external call (`getGroupData`) is cached, not per-turn
**Constraints**: MUST NOT make a live Green API `getGroupData` call on every group turn
(caching required, per research.md §1); MUST NOT break OpenAI prompt-caching on the constitution
prefix (new etiquette guidance goes into the stable constitution text, per research.md §6)
**Scale/Scope**: One new component (`GroupMembershipResolver`, ~50-100 LOC), 5 existing files
modified (`denidin.py` — group RBAC wiring [US4] AND the new `should_reply` check before
`send_response` [US4a], `src/handlers/whatsapp_handler.py`, `src/handlers/ai_handler.py`
[sender-name/`"AI"`-sentinel call-site argument changes (US3/US3a) + no-reply-sentinel
detection and `AIResponse.should_reply` (US4a) — no changes to `create_request`/`get_response`
signatures], `src/handlers/media_handler.py`, `src/managers/session_manager.py`), 1 existing
model modified (`WhatsAppMessage` — new `sender_display_name` attribute), 1 existing response
model modified (`AIResponse` — new `should_reply: bool` field, default `True`), 1
config/content file modified (`config/runtime_constitution.md` — group-etiquette guidance
covering US1/US5/US7, including the no-reply-sentinel instruction)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

- ✅ **§I No env vars**: `GroupMembershipResolver` receives its Green API groups client via
  constructor injection (same pattern as `MemoryManager`/`MediaFileManager`/
  `LedgerEventManager`), constructed in `denidin.py`'s `initialize_app`. No new
  `feature_flags` needed — this replaces existing gating behavior outright rather than adding
  a gradually-rolled-out path (matches Feature 033's precedent for a storage/behavior-shape
  change to always-on behavior).
- ✅ **§II UTC timestamps**: No new timestamp handling introduced by this feature.
- ✅ **§III Git workflow**: On `feature/039-group-conversation-support`, off `master`.
- ✅ **§V Integration tests, no mocking**: New integration tests dispatch real webhook-shaped
  group notifications through `bot.router` (true integration, not direct method calls),
  exercising real `WhatsAppHandler`/`AIHandler`/`SessionManager`/`GroupMembershipResolver`
  objects together. The one new external-service boundary this feature adds (Green API's
  `getGroupData`) is a real network call in integration/billed tests, per the project's
  zero-mocking policy for external services — never mocked, same treatment as existing Green
  API/OpenAI calls elsewhere in the suite.
- ✅ **§XVII No monkey-patching**: `GroupMembershipResolver` injected via constructor, no
  runtime patching of `WhatsAppHandler`/`AIHandler`.
- ✅ **No new env vars, no `os.getenv`**: N/A, none introduced.
- **Re-check after Phase 1 (data-model.md/contracts/ written)**: No new violations — no new
  fields at all on `Message` (only value changes at existing call sites),
  `sender_display_name` is a plain new `WhatsAppMessage` attribute,
  `GroupMembershipResolver` is a plain dependency-injected component, matching every existing
  manager's shape in this codebase. No Complexity Tracking entries needed.

## Project Structure

### Documentation (this feature)

```text
specs/in-progress/039-group-conversation-support/
├── user-stories.md      # MANDATORY, Given-When-Then (done)
├── spec.md              # This feature's spec, incl. Clarifications (done)
├── plan.md              # This file
├── research.md          # Phase 0 output (done)
├── data-model.md         # Phase 1 output (done)
├── quickstart.md         # Phase 1 output (done)
├── contracts/
│   ├── group-rbac-resolution.md    # Phase 1 output (done)
│   ├── message-sender-role.md      # Phase 1 output (done)
│   └── no-reply-mechanism.md       # Phase 1 output (done)
└── tasks.md               # Phase 2 output (/speckit.tasks — done, 20 tasks/12 phases)
```

### Source Code (repository root, single project — `apps/denidin-app/`)

```text
apps/denidin-app/
├── src/
│   ├── models/
│   │   └── message.py             # MODIFIED — WhatsAppMessage gains sender_display_name
│   │                                #   (senderContactName → senderName → raw id fallback, US3);
│   │                                #   AIResponse (message.py:146) gains new should_reply:
│   │                                #   bool field, default True (US4a)
│   ├── handlers/
│   │   ├── whatsapp_handler.py    # MODIFIED — is_bot_mentioned_in_group removed (US1);
│   │   │                           #   group-routing no longer gates on it
│   │   ├── ai_handler.py          # MODIFIED — (US3/US3a) call-site argument changes only:
│   │   │                           #   sender=message.sender_display_name instead of raw id;
│   │   │                           #   drop the "AI" sentinel from sender=/recipient=. (US4a)
│   │   │                           #   _finalize_response detects the no-reply sentinel in
│   │   │                           #   response_text, sets AIResponse.should_reply=False,
│   │   │                           #   skips assistant-message persistence for that turn. No
│   │   │                           #   changes to create_request/get_response signatures
│   │   │                           #   (research.md §3 for the separate, unrelated
│   │   │                           #   user_phone-override RBAC change)
│   │   └── media_handler.py       # MODIFIED — _store_media_turn: same sender-name + "AI"-
│   │                                #   sentinel fixes as ai_handler.py, applied to the media path
│   ├── managers/
│   │   ├── session_manager.py     # MODIFIED — get_conversation_history_for_session gains
│   │   │                           #   group-aware "[sender] " content prefixing (US3); no new
│   │   │                           #   Message field
│   │   └── group_membership_resolver.py   # NEW — GroupMembershipResolver (US4)
│   └── ...                         # (denidin.py: _process_conversational_message wires group
│                                     #   RBAC resolution before create_request/get_response
│                                     #   [US4]; checks ai_response.should_reply before calling
│                                     #   send_response [US4a]; initialize_app constructs
│                                     #   GroupMembershipResolver, same pattern as other managers)
├── config/
│   └── runtime_constitution.md    # MODIFIED — new group-etiquette section (US1 default, US5
│                                    #   three-way split, US7 self-referential @Name check,
│                                    #   no-reply sentinel instruction for US5/US7's silent paths)
└── tests/
    ├── unit/
    │   ├── test_group_membership_resolver.py   # NEW
    │   ├── test_message.py                       # MODIFIED — sender_display_name fallback-chain tests
    │   ├── test_session_manager.py               # MODIFIED — sender/recipient value + history-prefix tests
    │   └── test_ai_handler.py                     # MODIFIED — no-reply-sentinel detection tests
    ├── integration/
    │   └── test_group_conversation_routing.py    # NEW — US1/US2/US3/US3a/US4/US4a/US6 via real
    │                                              #   bot.router dispatch of group-shaped
    │                                              #   notifications (incl. no-reply-sentinel →
    │                                              #   send_response NOT called, message still
    │                                              #   persisted)
    └── billed/
        └── test_group_etiquette_billed.py         # NEW — 6 real-OpenAI content-judgment cases
                                                     #   (US1, US5 x3, US7 x2 — see Testing above),
                                                     #   text-only, cheap tier
```

**Structure Decision**: Single project, following `apps/denidin-app`'s existing
`src/managers/`+`src/handlers/` layout — `GroupMembershipResolver` is a new peer of
`MemoryManager`/`MediaFileManager`/`LedgerEventManager` in `src/managers/`, not a new
top-level module. No changes to `apps/morning-mcp-app` (out of scope — this feature doesn't
touch Morning MCP's own code, only which roles get the tool attached, an existing
`AIHandler`-side gate that's unchanged).

## Complexity Tracking

No violations to justify — no entries.

---

See `contracts/group-rbac-resolution.md`, `contracts/message-sender-role.md`, and
`contracts/no-reply-mechanism.md` for the full Integration Contracts (METHODOLOGY §VII).
`tasks.md` is written and `speckit.analyze` has run — ready for `speckit.implement`.
