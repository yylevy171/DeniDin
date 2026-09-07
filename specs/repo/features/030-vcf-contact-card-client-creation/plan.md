# Implementation Plan: vCard Contact Card → Client Creation — Feature 030

**Feature**: 030-vcf-contact-card-client-creation
**Branch**: `030-vcf-contact-card-client-creation`
**Spec**: `./spec.md` · **User stories**: `./user-stories.md`
**Status**: Ready for Task Generation
**Updated**: July 30, 2026

**Compliance**: CONSTITUTION.md (§I no env vars, §II UTC, §III git workflow, §V real-sandbox
integration tests / zero mocking of external services, §VIII test immutability, §X friendly
errors, §XVII no monkey-patching) and METHODOLOGY.md (§I spec-first, §VI TDD, §VII integration
contracts). No feature flag: purely additive routing + conversational-input handling, no behavior
change to any existing path (mirrors Feature 021/026's precedent of shipping additive
input/tool paths without a flag).

---

## Summary

Add two new Green API message-type routers to `apps/denidin-app/denidin.py`:
`contactMessage` (single shared contact) feeds the vCard's raw text into the exact same
conversational `AIHandler` pipeline `textMessage` already uses, so the model proposes an
`add_client` call exactly as it would from typed text — inheriting Feature 026's approval gate
and missing-field behavior with **zero new confirmation/validation code**.
`contactsArrayMessage` (multiple contacts shared at once — confirmed via Green API's docs to be a
genuinely distinct notification type, not multiple vCards inside one `contactMessage`) replies
directly with a friendly "one at a time" message, no AI call at all. No new MCP tool, no new
Morning-side code, no new persisted entity.

## Technical Context

- **Language/Version**: Python 3.11 (`apps/denidin-app`, unchanged).
- **Primary Dependencies**: none new. No vCard-parsing library — the model reads raw vCard text
  directly (research.md Decision 2). Existing `whatsapp_chatbot_python` router, existing
  `openai` Responses API + `PendingApprovalManager` (Feature 022/026), all reused unchanged.
- **Storage**: none new. Morning remains the sole source of truth for client records.
- **Testing**: unit tests for the new `WhatsAppMessage.from_notification` branch and the two new
  router handlers (`apps/denidin-app/tests/unit/`); real-API E2E tests for US1/US2 — **`billed`
  tier, not `expensive`** (Feature 029, merged 2026-07-30, split the old single `expensive` marker
  into `billed`: real, text-only OpenAI calls, no approval/one-at-a-time gate; vs. `expensive`:
  real vision/image/PDF/DOCX calls, keeps the full approval discipline. A shared vCard is plain
  text — no vision call involved — so these qualify as `billed`) in
  `apps/denidin-app/tests/billed/test_denidin_vcf_contact_e2e.py` (`@pytest.mark.billed`, new
  file — mirrors how ledger events split into `test_ledger_event_capture_billed.py` for their
  text-flow tests); a plain integration test for US3 since it never calls OpenAI at all (not
  `billed`, not `expensive` — no external call to gate).
- **Target Platform**: existing containerized runtime, unchanged (no new container, no new port,
  no new config file).
- **Constraints**: no env vars; UTC (N/A — no new timestamp handling); `pathlib.Path` (N/A — no
  new file I/O); no monkey-patching; friendly (Hebrew) errors; tests immutable once approved.

## Constitution Check (pre-Phase 0)

- **No env vars** — PASS: no new config keys.
- **UTC** — N/A: no new timestamp handling.
- **Feature branch** — PASS: `030-vcf-contact-card-client-creation`.
- **Feature flags** — N/A: purely additive new-message-type handling; no existing behavior
  changes for any currently-handled message type.
- **Real-sandbox tests / ZERO-MOCKING** — MUST ADHERE: US1/US2 get real-API E2E tests (real
  OpenAI Responses API + real Morning sandbox via the MCP tunnel) before implementation; no
  `unittest.mock` of either. Classified `billed` (text-only, Feature 029) — runnable freely, no
  per-run approval needed, unlike the stricter `expensive` tier. US3 needs no external call at
  all (declines before ever reaching `AIHandler`), so its test is a plain integration test — not
  `billed`, not `expensive`.
- **No monkey-patching** — PASS: new router handlers and the new `from_notification` branch
  follow the existing pattern (pure functions/dataclass construction, no runtime patching).
- **Test immutability (§VIII)** — no existing test is being changed; this feature only adds new
  tests and new (previously-nonexistent) routing behavior for message types the catch-all
  currently swallows.
- **Friendly errors (§X)** — PASS: US3's decline message and any "missing field" prompts (US2)
  use the project's existing friendly-error/Hebrew-reply style; no stack traces surfaced.

## Integration Contracts (METHODOLOGY §VII)

### Green API webhook → `denidin.py` router (new)

**`denidin.py` MUST**:
- Register `@bot.router.message(type_message='contactMessage')` → parse via
  `WhatsAppMessage.from_notification` (new branch) → run the same turn-processing logic
  `handle_text_message` already runs (group-mention check → `AIHandler.create_request`/
  `get_response` → `WhatsAppHandler.send_response`), extracted into a shared private helper to
  avoid duplicating `handle_text_message`'s ~90 lines of try/except/tracking boilerplate
  (research.md Decision 5).
- Register `@bot.router.message(type_message='contactsArrayMessage')` → reply directly with a
  friendly "one at a time" message (mirrors `handle_unsupported_message_default`'s direct-reply
  pattern) — **no** `WhatsAppMessage`/`AIRequest` construction, **no** `AIHandler` call.
- See `contracts/contactMessage.json` / `contracts/contactsArrayMessage.json` for the exact
  confirmed webhook shapes (Green API docs, fetched 2026-07-30).

### `WhatsAppMessage.from_notification` → `AIHandler` (new branch, existing contract)

**`from_notification` MUST**:
- For `typeMessage == 'contactMessage'`: build `text_content` as a short natural-language framing
  containing `contactMessageData.displayName` and the raw `contactMessageData.vcard` text verbatim
  (data-model.md) — no field-level vCard parsing in Python.
- Set `message_type = 'contactMessage'` (existing field) so this turn is distinguishable from a
  typed one if ever needed downstream, without changing how `AIHandler` processes it.

**`AIHandler` PROVIDES (unchanged)**: the existing conversational pipeline — RBAC-gated Morning
MCP tool attachment (Feature 018), `add_client` approval gate + missing-field prompting
(Feature 026). Zero new code in `ai_handler.py` for this feature.

### `runtime_constitution.md` ↔ model (prompt-level guidance, new)

**`runtime_constitution.md` MUST**:
- Add guidance (mirrors existing `add_client` field-requirement guidance): a shared WhatsApp
  contact card, for a godfather/admin, is a likely request to add that person as a Morning
  client — extract name/phone/email from the vCard content and follow the existing `add_client`
  flow (ask for whatever's missing, confirm before creating). See research.md Decision 6.

## Project Structure

### Documentation (this feature)

```text
specs/backlog/030-vcf-contact-card-client-creation/
├── spec.md               # done, approved (Clarifications resolved 2026-07-30)
├── user-stories.md       # done, approved (US1-US3; US4/RBAC dropped - no new RBAC surface)
├── plan.md               # this file
├── research.md           # Phase 0 output
├── data-model.md         # Phase 1 output
├── contracts/            # Phase 1 output
│   ├── contactMessage.json
│   └── contactsArrayMessage.json
└── quickstart.md         # Phase 1 output
```
(`tasks.md` is Phase 2 output — `/speckit.tasks`, not produced by this command.)

### Source Code

```text
apps/denidin-app/src/models/message.py
  # WhatsAppMessage.from_notification: new branch for typeMessage == 'contactMessage',
  # alongside the existing extendedTextMessage vs. default branch (line ~49-52)

apps/denidin-app/src/handlers/whatsapp_handler.py
  # validate_message_type: add 'contactMessage' to accepted types (line ~74)

apps/denidin-app/denidin.py
  # + _process_conversational_message(notification) - extracted shared helper from
  #   handle_text_message's existing body (line 292-384), called by both handle_text_message
  #   and the new handle_contact_message
  # + @bot.router.message(type_message='contactMessage') -> handle_contact_message
  # + @bot.router.message(type_message='contactsArrayMessage') -> handle_contacts_array_message
  #   (direct friendly reply, no AIHandler call)

apps/denidin-app/config/runtime_constitution.md
  # + guidance: shared contact card -> likely add_client request, follow existing flow

apps/denidin-app/tests/unit/
  # + tests for from_notification's new contactMessage branch
  # + tests for handle_contact_message / handle_contacts_array_message routing

apps/denidin-app/tests/billed/test_denidin_vcf_contact_e2e.py    # NEW - @pytest.mark.billed
  # (Feature 029 tier: real, text-only OpenAI calls - runs freely, no per-run approval needed)
  # test_godfather_shares_contact_card_complete_requires_approval (US1)
  # test_godfather_shares_contact_card_missing_email_is_asked_for (US2, uses the real fixture)

apps/denidin-app/tests/integration/test_contact_card_webhook_routing.py    # NEW
  # test_contacts_array_message_declines_with_friendly_message (US3, no OpenAI call - mirrors
  # test_media_webhook_routing.py's pattern, not billed/expensive)

apps/denidin-app/tests/fixtures/contacts/
  # 00005372-גיל ברטל .vcf (real fixture, already added) + README.md (already added)
  # + a synthetic complete-card fixture (name+phone+email) for US1, since the real one has no email
```

**Structure Decision**: Single-project structure (unchanged). All changes live in
`apps/denidin-app` — no `apps/morning-mcp-app` changes at all, since `add_client` itself is
untouched (research.md Decision 3).

## Phased Execution

### Phase 0 — Research (this plan's Phase 0, see research.md)
Fully resolved — Green API webhook shapes confirmed via official docs, no remaining unknowns.
**Checkpoint**: no unknowns block implementation.

### Phase 1 — Routing + vCard framing, TDD
`from_notification`'s new branch, `validate_message_type` update, the two new router handlers
(and the `_process_conversational_message` extraction) — each preceded by a failing test per
CONSTITUTION §V/METHODOLOGY §VI (unit tests for routing/framing, since no external call is
involved at this layer).

### Phase 2 — runtime_constitution.md guidance + real E2E verification
Prompt guidance update; the two new `billed`-tier E2E tests (US1/US2, Feature 029 tier — runnable
freely, no per-run approval) verifying the full path through a real OpenAI call and real Morning
sandbox creation; the plain (non-billed) US3 integration test.

### Phase 3 — Cross-cutting verification
Full spec-to-test traceability pass before `/speckit.analyze`; confirm no regression to existing
`textMessage`/media routing (the shared-helper extraction touches `handle_text_message`'s body).

## Complexity Tracking

No Constitution Check violations requiring justification — this feature adds no new
infrastructure, no new dependency, and reuses the existing `add_client` approval-gate/validation
pipeline verbatim.
