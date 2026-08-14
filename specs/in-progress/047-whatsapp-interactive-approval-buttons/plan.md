# Implementation Plan: WhatsApp Interactive Buttons for the Approval Gate

**Branch**: `feature/047-whatsapp-interactive-approval-buttons` | **Date**: 2026-08-14 | **Spec**: `./spec.md`
**Input**: Feature specification from `specs/in-progress/047-whatsapp-interactive-approval-buttons/spec.md`

---

**IMPORTANT**: This plan complies with:
- **CONSTITUTION.md** (§I-III, §V, §XVII): No env vars (buttons sent via the existing
  `notification.api`/Green API client already injected everywhere else — no new credential, no
  new config field), Israel local time unchanged (no new timestamps beyond the existing
  `PendingApproval.created_at`), feature branch workflow, real-external-call integration tests
  (a real webhook-shaped `interactiveButtonsResponse` notification dispatched through
  `bot.router`, matching how every other message type is tested), no monkey-patching (new code
  paths via new methods/handlers, no runtime patching of `whatsapp_chatbot_python`).
- **METHODOLOGY.md** (§II, IV, VII): Integration Contracts written (`contracts/*.md`).

---

## Summary

Add a second, parallel entry point into the existing Feature 022 approval gate
(`PendingApprovalManager`/`AIHandler._resolve_pending_approval`), driven by a real WhatsApp
interactive-buttons tap instead of parsed free text. All open questions were resolved during
`speckit.clarify` (see spec.md Clarifications) and Gate Zero's real round-trip (see
`research.md`) already fixed the exact wire shape. The core design decision this plan adds:
**`PendingApproval` gains a `sent_message_id` field**, populated with the WhatsApp `idMessage`
of the buttons message once it's actually sent, so a later tap's `stanzaId` can be matched
against it — the only way to tell "a tap on the *current* pending approval" apart from "a tap on
a stale, superseded one" (`PendingApprovalManager` tracks at most one pending approval per
`chat_id`, so without this the manager alone can't distinguish the two: a stale tap arriving
after a *newer* approval has replaced the old one would otherwise incorrectly resolve the new
one instead of being silently ignored).

## Technical Context

**Language/Version**: Python 3.9+ (existing project floor, `apps/denidin-app`)
**Primary Dependencies**: `whatsapp_api_client_python` / `whatsapp_chatbot_python` — already a
dependency, already exposes everything needed
(`api.sending.sendInteractiveButtons`, confirmed live in Gate Zero). No new package.
**Storage**: In-memory only, same as today — `PendingApprovalManager` is not persisted to disk
(per its own docstring: losing a pending approval on restart just means the user re-issues the
request). One new field on the existing in-memory `PendingApproval` dataclass, no new storage
layer, no migration.
**Testing**: **No new automated tests** for this feature, by explicit user decision
(2026-08-14, same kind of scoped exception as Feature 048's) — implementation proceeds directly
from `tasks.md`'s "b" tasks, without a preceding "a" (test-writing) step or its human-approval
gate. **Hard requirement standing in for that coverage**: every existing test that exercises the
approval gate (`tests/unit/test_ai_handler.py`'s pending-approval/`_resolve_pending_approval`/
`_is_affirmative_reply` tests, `tests/unit/test_whatsapp_handler.py`'s `send_response` tests,
any integration test dispatching a real text-based approval reply) must keep passing **with no
change to their logic or assertions** — this feature is additive (a new, parallel entry point),
so nothing about the existing text-approval behavior should need a single existing test to be
touched, let alone rewritten. The full suite (`pytest tests/ -v --tb=short`) is the acceptance
check, run once at the end (Phase 7), in place of per-phase TDD gates. Manual verification per
`quickstart.md` substitutes for the dedicated automated coverage the original TDD task pairs
would have provided (notably US3's stale-tap/supersession scenarios). No `tests/billed/` or
`tests/expensive/` needed either way — nothing here calls OpenAI or vision; the only new
external call (`sendInteractiveButtons`) is Green API, already exercised for real by Gate Zero's
manual round-trip.
**Target Platform**: N/A beyond the code change itself — no container/runtime change (existing
rebuild-on-merge process applies).
**Constraints**: Green API confirmed live: max 3 buttons per message, 25 chars/button label
(both `"כן"`/`"לא"` trivially fit), `body` capped at 20000 chars (the `📋 לאישור:` block is far
under that). `"type": "reply"` is a hard-required field per button (confirmed live — a `400` on
the first Gate Zero attempt without it).
**Scale/Scope**: One new router handler (`denidin.py`), one new `AIHandler` method
(`resolve_button_tap`, parallel to the existing `_resolve_pending_approval`, reusing its
approve/decline execution logic rather than duplicating it), one new `WhatsAppHandler` send
path, one new field + one new method on `PendingApproval`/`PendingApprovalManager`, one new
`AIResponse` field. No new files beyond `contracts/`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

- ✅ **§I No env vars**: buttons are sent via `notification.api` (the same Green API client
  object already reachable from every existing handler) — no new credential, no new
  `config.*` field. No feature flag: this is additive, parallel behavior with the text path
  fully unchanged and unconditional (matches the Scope section's "second door, never closes the
  first" framing) — nothing here needs a gradual-rollout kill-switch beyond what already exists
  for the approval gate itself.
- ✅ **§II Israel local time**: no new timestamp handling — `PendingApproval.created_at` is
  unchanged; `sent_message_id` is an opaque WhatsApp-assigned string id, not a timestamp.
- ✅ **§III Git workflow**: on `feature/047-whatsapp-interactive-approval-buttons`, off
  `master`.
- ✅ **§V no mocking**: N/A in the automated-test sense this feature ships without new tests
  (explicit user decision, see Testing above) — there's no new mock to avoid. What §V governs
  (real internal objects, real external calls, never mocked) remains true in spirit: the
  `sendInteractiveButtons` call itself was verified for real during Gate Zero (not mocked, not
  assumed) and remains a real Green API call at runtime; existing integration tests that do
  exercise the approval gate continue to do so via real `bot.router` dispatch, unchanged.
- ✅ **§XVII No monkey-patching**: all new behavior is new methods/handlers, constructed the
  same dependency-injected way as every existing manager — no runtime patching of
  `whatsapp_chatbot_python`, `PendingApprovalManager`, or `AIHandler`.
- **Re-check after Phase 1 (data-model.md/contracts/ written)**: no new violations. The one
  design point worth flagging explicitly (not a Constitution violation, a scope note): the
  audit trail for "approved via button vs. text" is implemented as `denidin-app`-side logging
  only (see `contracts/button-tap-resolution.md`), not a cross-app change to
  `apps/morning-mcp-app`'s own audit log (bugfix-036) — that app has no visibility into how the
  approval was obtained, and plumbing that context across the MCP boundary was judged out of
  scope for this feature. No Complexity Tracking entry needed — this is a scope decision, not a
  constitutional exception.

## Integration Contracts

Per METHODOLOGY §VII (multi-component feature: `denidin.py` router, `WhatsAppHandler`,
`AIHandler`, `PendingApprovalManager` all gain new responsibilities). Full contracts in
`contracts/`:

1. **`contracts/pending-approval-message-binding.md`** — `AIHandler` ↔ `PendingApprovalManager`:
   the new `sent_message_id` field and `attach_sent_message_id` method, and exactly how/when
   staleness is decided.
2. **`contracts/whatsapp-buttons-send.md`** — `AIHandler`/`denidin.py` ↔ `WhatsAppHandler`: how
   a turn that just created a pending approval gets sent as buttons instead of plain text, and
   how a send failure surfaces (per clarify: an error, never a silent text fallback).
3. **`contracts/button-tap-resolution.md`** — `denidin.py` router ↔ `AIHandler`: the new
   `interactiveButtonsResponse` handler, `resolve_button_tap`'s stanzaId-matching/staleness
   logic, and audit logging of the approval mechanism.

## Project Structure

### Documentation (this feature)

```text
specs/in-progress/047-whatsapp-interactive-approval-buttons/
├── spec.md              # done — Gate Zero CLOSED, Clarifications complete
├── user-stories.md      # done — updated to match clarified button labels/stale-tap behavior
├── research.md          # done — Gate Zero (6/6) + editMessage + router.buttons findings
├── gate-zero-*.json     # done — raw captured webhook evidence
├── plan.md              # this file
├── data-model.md        # Phase 1 output
├── quickstart.md         # Phase 1 output
├── contracts/
│   ├── pending-approval-message-binding.md   # Phase 1 output
│   ├── whatsapp-buttons-send.md              # Phase 1 output
│   └── button-tap-resolution.md              # Phase 1 output
└── tasks.md              # Phase 2 output (/speckit.tasks — not yet run)
```

### Source Code (repository root, single project — `apps/denidin-app/`)

```text
apps/denidin-app/
├── denidin.py                          # MODIFIED — new
│                                        #   @bot.router.message(type_message="interactiveButtonsResponse")
│                                        #   handler (NOT @bot.router.buttons() - confirmed that
│                                        #   only matches the old deprecated button types,
│                                        #   research.md). Extracts chat_id/selected_id/stanza_id
│                                        #   from notification.event, calls
│                                        #   ai_handler.resolve_button_tap(...). Also: after a
│                                        #   normal turn's send_response call succeeds AND the
│                                        #   response carried offer_approval_buttons, calls
│                                        #   pending_approval_manager.attach_sent_message_id(...)
│                                        #   with the returned idMessage.
├── src/
│   ├── models/
│   │   └── message.py                  # MODIFIED — AIResponse gains
│   │                                    #   offer_approval_buttons: bool = False (set True by
│   │                                    #   AIHandler exactly when a new pending approval was
│   │                                    #   just created this turn)
│   ├── managers/
│   │   └── pending_approval_manager.py # MODIFIED — PendingApproval gains
│   │                                    #   sent_message_id: Optional[str] = None;
│   │                                    #   PendingApprovalManager gains
│   │                                    #   attach_sent_message_id(chat_id, id_message); new
│   │                                    #   module-level BUTTON_ID_APPROVE/BUTTON_ID_DECLINE
│   │                                    #   constants
│   └── handlers/
│       ├── ai_handler.py               # MODIFIED — new resolve_button_tap(chat_id,
│       │                                #   selected_id, stanza_id, sender, recipient) method,
│       │                                #   parallel to _resolve_pending_approval but keyed on
│       │                                #   selected_id instead of parsed free text; reuses
│       │                                #   _call_openai_approval_api and the same
│       │                                #   duplicate-execution guards verbatim. Sets
│       │                                #   AIResponse.offer_approval_buttons=True at the same
│       │                                #   point PendingApproval is first set() (existing
│       │                                #   ~line 1591).
│       └── whatsapp_handler.py         # MODIFIED — new send path used when
│                                        #   response.offer_approval_buttons is True: calls
│                                        #   notification.api.sending.sendInteractiveButtons(...)
│                                        #   instead of notification.answer(...), returns the
│                                        #   sent idMessage on success. On failure: logs (same
│                                        #   pattern as existing send_response error handling),
│                                        #   leaves the pending approval in place uncleared, and
│                                        #   sends a distinct plain-text error notice via the
│                                        #   existing notification.answer(...) path so the user
│                                        #   isn't left with nothing (clarify: "surface an
│                                        #   error", not a silent fallback to the approval text
│                                        #   itself — the user is told the prompt failed to send,
│                                        #   not shown a degraded version of it).
└── tests/
    ├── unit/
    │   ├── test_pending_approval_manager.py   # MODIFIED — attach_sent_message_id tests
    │   └── test_ai_handler.py                  # MODIFIED — resolve_button_tap
    │                                            #   approve/decline/stale-mismatch tests
    └── integration/
        └── test_button_tap_routing.py          # NEW — real interactiveButtonsResponse-shaped
                                                  #   notification through bot.router: approve
                                                  #   path, decline path, and stale-tap (mismatched
                                                  #   stanzaId) no-op path, all via real objects
```

**Structure Decision**: Single project, no new top-level modules — every change is a
modification to an existing file already owning this responsibility (`pending_approval_manager`
for approval state, `ai_handler` for resolution logic, `whatsapp_handler` for the Green API send
boundary, `denidin.py` for router registration), matching this codebase's existing shape. No
changes to `apps/morning-mcp-app` (out of scope — this feature is entirely `denidin-app`-side;
see the audit-trail scope note above).

## Complexity Tracking

No Constitution Check violations requiring justification.
