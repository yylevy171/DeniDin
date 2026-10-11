# Implementation Plan: WhatsApp Reply/Quote Reference Resolution

**Branch**: `feature/032-whatsapp-reply-reference-resolution` | **Date**: 2026-08-04 | **Spec**: `specs/backlog/032-whatsapp-reply-reference-resolution/spec.md`
**Input**: Feature specification from `specs/backlog/032-whatsapp-reply-reference-resolution/spec.md` (CLARIFIED, `speckit.clarify` complete 2026-08-04)

---

**IMPORTANT**: This plan complies with:
- **CONSTITUTION.md** (§I-III): No env vars, UTC timestamps, feature branch workflow.
- **METHODOLOGY.md** (§II, IV, VII): Phased planning, Integration Contracts.

---

## Summary

Capture Green API's `idMessage` on every message DeniDin handles and `quotedMessage.stanzaId`
on incoming replies, then resolve a reply's `stanzaId` back to DeniDin's own stored `Message`
record (`src/managers/session_manager.py::Message`) — scoped to the active/unexpired session
only, which is inherently per-chat since `SessionManager` already maps one `Session` per
`whatsapp_chat`. The resolved message's content/metadata OR — mutually exclusive, 2026-08-04
revision — the full structured `LedgerEvent` record(s) (fetched via a new
`LedgerEventManager.get_event`) if the message has `ledger_event_ids`, is surfaced as extra
prompt context, following the exact pattern `AIHandler.create_ai_request` already uses for
recalled memories (`constitution += memory_context`, `ai_handler.py:668-672`). Media messages
resolve to their already-computed `extracted_text`/`document_analysis`, never raw bytes and
never a fresh vision call.

## Technical Context

**Language/Version**: Python 3.11 (matches `apps/denidin-app` existing codebase).
**Primary Dependencies**: None new — `dataclasses`, existing `src/models/green_api.py`
(`QuotedMessage`), existing `src/managers/session_manager.py`.
**Storage**: Existing JSON file storage under `data/sessions/{session_id}/messages/*.json`
(no new storage technology) — two new fields on the existing `Message` dataclass, plus a new
in-memory index for `idMessage` → `message_id` lookup (see data-model.md).
**Testing**: `pytest`, three tiers (finalized 2026-08-04, see tasks.md's Test Tiers section):
unit + integration (no real OpenAI call — `create_ai_request` only builds the request object)
for all mechanical resolution scenarios; 2 `tests/billed/` tests (text-only, real OpenAI,
proving structured `LedgerEvent` data actually reaches and is usable by the model, and that an
empty resolution doesn't induce hallucination); 2 `tests/expensive/` tests (real vision calls
— a real agreement image and a real bank-deposit image, the only way to cover the bank path
since it has no text-only capture route). Integration tier simulates a real Green API reply
webhook dispatched through `bot.router` (per CONSTITUTION §V, no direct method calls into
internal components).
**Target Platform**: Existing Docker container (`denidin-app-<env>`), no infra change.
**Project Type**: Single project — `apps/denidin-app/src/`.
**Performance Goals**: Resolution must not add a second disk read pass over the whole session
history per incoming message — reuse the session's already-loaded message index (see
research.md Decision 3).
**Constraints**: Must not change `instructions` assembly order (constitution → memory context
→ `---` → date, per CLAUDE.md's prompt-caching note) — resolved-reference context is
additional appended text, inserted in the same position as `memory_context` (before the
`---` separator), not before the constitution's stable prefix.
**Scale/Scope**: Per-message overhead only — no batch/background job. Applies to `textMessage`
and `extendedTextMessage` (replies always arrive as `extendedTextMessage` per Green API), and
by extension the media message types once media messages get `idMessage` captured too.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

- **§I No env vars**: N/A — no new config beyond, at most, a feature flag under
  `config.feature_flags` (default `false`) if the team wants a kill switch (see research.md
  Decision 1).
- **§II UTC timestamps**: `received_at`/`timestamp` fields already exist on `Message`; no new
  timestamp handling introduced beyond what's already there.
- **§III Git workflow**: On `feature/032-whatsapp-reply-reference-resolution`, off `master`. ✅
- **§V Integration tests as E2E**: Reply resolution must be tested by dispatching a real Green
  API webhook payload containing `quotedMessage`/`stanzaId` through `bot.router`, not by
  calling a resolver function directly with hand-built objects — see quickstart.md.
- **§XV No monkey-patching**: Resolution is a new method on `SessionManager` (or a small new
  collaborator it owns), called via normal dependency injection from `AIHandler` — no runtime
  patching.
- **§XVII (config/DI)**: Any new lookup index lives inside `SessionManager`'s existing
  in-memory state (it already keeps `chat_to_session`), not a new global.

**Result**: PASS — no violations requiring Complexity Tracking justification.

## Project Structure

### Documentation (this feature)

```text
specs/backlog/032-whatsapp-reply-reference-resolution/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md         # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/            # Phase 1 output (internal interface contract, not REST/OpenAPI)
│   └── reply-resolution.md
└── tasks.md              # Phase 2 output (speckit.tasks — NOT created by this plan)
```

### Source Code (repository root)

```text
apps/denidin-app/
├── src/
│   ├── models/
│   │   └── message.py            # WhatsAppMessage.from_notification: capture event['idMessage']
│   │                              #   and messageData.quotedMessage.stanzaId (currently discarded)
│   ├── managers/
│   │   ├── session_manager.py    # Message: + whatsapp_id_message, + resolved_reference fields;
│   │   │                          #   SessionManager: idMessage index + resolve_reply() method
│   │   └── ledger_event_manager.py  # + get_event(event_id) read method (new — resolve_reply
│   │                                 #   needs to hydrate full LedgerEvent records, not bare ids)
│   └── handlers/
│       ├── whatsapp_handler.py   # capture idMessage from sendMessage response for outgoing
│       │                          #   messages (research.md Decision 2 — may be deferred)
│       └── ai_handler.py         # create_ai_request: append resolved-reference context to
│                                  #   `constitution` string, same position/pattern as memory_context
└── tests/
    ├── unit/
    │   ├── test_message_model.py       # WhatsAppMessage new-field capture
    │   ├── test_session_manager.py     # resolve_reply() unit coverage (index hit/miss, expiry,
    │   │                                #   cross-chat non-match, content/ledger_events exclusivity)
    │   └── test_ledger_event_manager.py  # get_event() unit coverage
    ├── integration/
    │   └── test_reply_resolution.py    # real Green API reply webhook → bot.router → resolved
    │                                    #   context reaches stored Message, per US1/US2 scenarios
    ├── billed/
    │   └── test_reply_resolution_billed.py     # 2 tests, text-only real OpenAI calls
    └── expensive/
        └── test_reply_resolution_expensive.py  # 2 tests, real vision calls (agreement + bank image)
```

**Structure Decision**: Single project, no new top-level directories. Changes are additive to
existing `models/message.py`, `managers/session_manager.py`, `managers/ledger_event_manager.py`,
`handlers/ai_handler.py`, and (for outgoing `idMessage` capture) `handlers/whatsapp_handler.py`.

## Complexity Tracking

*No Constitution Check violations — table intentionally empty.*
