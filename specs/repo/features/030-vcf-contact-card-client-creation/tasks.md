# Tasks: vCard Contact Card → Client Creation (Feature 030)

**Input**: `plan.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md`, `spec.md`,
`user-stories.md` (US1-US3; US4/RBAC dropped — no new RBAC surface, per spec.md Clarifications).

## Conventions

- `[P]` = parallelizable (different files, no dependency on an incomplete task in this list).
- `[US#]` = maps to the user story of that number in `user-stories.md`.
- `Xa`/`Xb` pairs = METHODOLOGY §VI TDD gate: `a` writes a failing test (RED), `b` implements
  until it passes (GREEN). Per CONSTITUTION §V, no `unittest.mock` of OpenAI/Green
  API/Morning — real sandbox / real router dispatch only.
- 👤 **MANUAL APPROVAL GATE** tasks stay unchecked until a human actually performs them — they are
  not something this session can complete on its own.
- **Test tier (Feature 029, merged 2026-07-30, mid-planning for this feature)**: US1/US2's E2E
  tests are real, **text-only** OpenAI calls (a vCard is plain text, no vision/image call
  involved) → **`billed` tier** (`tests/billed/`, `@pytest.mark.billed`) — runs freely, **no
  per-run approval, no one-at-a-time restriction, no log-reading requirement**; do not apply the
  stricter `expensive`-tier rules to these. US3 makes no OpenAI call at all, so it's a plain
  integration test — neither `billed` nor `expensive`.

---

## Phase 1 — Foundation (shared building blocks, no user-facing behavior yet)

- [x] **T001a** [P] Write unit tests in `apps/denidin-app/tests/unit/test_message.py` for
  `WhatsAppMessage.from_notification`'s new `typeMessage == 'contactMessage'` branch: asserts
  `message_type == 'contactMessage'` and `text_content` contains both `displayName` and the raw
  `vcard` text verbatim (data-model.md framing). Use a fixture notification built from the real
  vCard's content (`tests/fixtures/contacts/00005372-גיל ברטל .vcf`) plus a synthetic one with an
  email present. **RED** — must fail against current code (no such branch exists).
- [x] **T001b** Implement the branch in `apps/denidin-app/src/models/message.py`
  (`WhatsAppMessage.from_notification`, alongside the existing `extendedTextMessage` vs. default
  branch at `message.py:49-52`) per `contracts/contactMessage.json`. **GREEN**.
- [x] **T002a** [P] Write unit tests in `apps/denidin-app/tests/unit/test_whatsapp_handler_errors.py`
  asserting `validate_message_type` now accepts `contactMessage` (mirrors the existing
  `test_validate_message_type_accepts_text_message` test). **RED**.
- [x] **T002b** Implement: add `'contactMessage'` to the accepted types in
  `apps/denidin-app/src/handlers/whatsapp_handler.py:74`. **GREEN**.
- [x] **T003** Extract `_process_conversational_message(notification)` in
  `apps/denidin-app/denidin.py` from `handle_text_message`'s existing body (`denidin.py:292-384`:
  validate → process → group-mention check → `AIHandler` → send response → error handling), then
  add `@bot.router.message(type_message='contactMessage')` → `handle_contact_message(notification)`
  calling the same helper. **No new test required for the extraction itself** — the existing
  `textMessage`/`extendedTextMessage` unit and integration tests (`test_message_flow.py`,
  `test_media_webhook_routing.py`'s `test_extended_text_message_routes_to_text_handler_not_unsupported`)
  must stay GREEN unchanged, proving the refactor is behavior-preserving for the existing route.
- [x] **T004** [P] Add `runtime_constitution.md` guidance (research.md Decision 6): a shared
  WhatsApp contact card, for a godfather/admin, is a likely request to add that person as a
  Morning client — extract name/phone/email from the vCard content and follow the existing
  `add_client` flow (ask for whatever's missing, confirm before creating). File:
  `apps/denidin-app/config/runtime_constitution.md`.
- [x] **T005** [P] Add a synthetic "complete card" vCard fixture (name + phone + email all
  present) to `apps/denidin-app/tests/fixtures/contacts/`, since the real fixture
  (`00005372-גיל ברטל .vcf`) has no email — needed by US1. Update
  `tests/fixtures/contacts/README.md` to document it.

---

## Phase 2 — User Story 1: Complete contact card → confirm → create (Priority: P1) 🎯 MVP

**Goal**: A godfather shares a contact card with name+phone+email; DeniDin proposes `add_client`,
waits for explicit approval (inherited Feature 026 gate), then creates a real Morning client.

**Independent Test**: Send the synthetic complete-card webhook, confirm, verify via a direct
`MorningClient.search_clients(...)` call that the client now exists with phone/email persisted.

- [x] **T006a** [US1] Write a real-API E2E test
  `test_godfather_shares_contact_card_complete_requires_approval` in NEW file
  `apps/denidin-app/tests/billed/test_denidin_vcf_contact_e2e.py` (`@pytest.mark.billed` —
  text-only OpenAI calls, Feature 029 tier, runs freely with no per-run approval): dispatch a real
  `contactMessage` webhook (T005's synthetic fixture) through `handle_contact_message` → assert no
  `add_client` `mcp_call` on turn 1 (only a confirmation question naming the parsed
  name/phone/email) → send an affirmative turn → assert `add_client` succeeds → verify directly
  against the Morning sandbox. **RED**.
- [x] **T006b** [US1] Run T006a (`pytest tests/billed/test_denidin_vcf_contact_e2e.py -m billed -v`
  — no approval needed, `billed` tier); fix forward
  (`_process_conversational_message`/`from_notification`/`runtime_constitution.md`) until
  **GREEN**.
- [ ] **T007** [US1] 👤 **MANUAL APPROVAL GATE**: run `quickstart.md`'s US1 scenario for real (a
  live WhatsApp contact share) — needs explicit approval to start the relevant dev environment
  first (`scripts/run_all.sh dev`, per CLAUDE.md's "never start an environment without approval"
  rule). **Waived by user decision, 2026-07-31 — not going to be run; automated verification (unit + integration + billed E2E) judged sufficient.**

---

## Phase 3 — User Story 2: Contact card missing a mandatory field (Priority: P1)

**Goal**: A godfather shares a contact card with no email (the real, common case per the real
fixture); DeniDin asks for the missing email before any confirmation/tool call.

**Independent Test**: Send the real fixture's webhook, assert the reply asks specifically for an
email and that no `add_client`/approval state was created.

- [x] **T008a** [US2] Write a real-API E2E test
  `test_godfather_shares_contact_card_missing_email_is_asked_for` in
  `tests/billed/test_denidin_vcf_contact_e2e.py` (`@pytest.mark.billed`), using the **real
  fixture** (`tests/fixtures/contacts/00005372-גיל ברטל .vcf`, no email): assert the reply asks
  for the missing email and that no `add_client` call / no pending-approval state exists; then
  send a follow-up supplying an email and assert the flow proceeds exactly as US1 (confirmation →
  approve → creation). **RED**.
- [x] **T008b** [US2] Run T008a (no approval needed, `billed` tier); fix forward until **GREEN**.
- [ ] **T009** [US2] 👤 **MANUAL APPROVAL GATE**: `quickstart.md`'s US2 scenario, live. **Waived by user decision, 2026-07-31 — not going to be run; automated verification (unit + integration + billed E2E) judged sufficient.**

---

## Phase 4 — User Story 3: Multi-contact share declined (Priority: P2)

**Goal**: Sharing 2+ contacts at once (`typeMessage: "contactsArrayMessage"`, a genuinely
distinct notification type — research.md Decision 1) gets an immediate friendly decline, no AI
call at all.

**Independent Test**: Send a real `contactsArrayMessage` payload, assert the friendly reply and
that no OpenAI/Morning call happened — fully testable without external services, so this is a
**non-expensive** integration test (mirrors `test_media_webhook_routing.py`'s pattern: real
`Notification`, real handler function, no mocks).

- [x] **T010a** [P] [US3] Write an integration test
  `test_contacts_array_message_declines_with_friendly_message` in NEW file
  `apps/denidin-app/tests/integration/test_contact_card_webhook_routing.py` (mirrors
  `test_media_webhook_routing.py`'s `_create_notification`/`_get_sent_message` helper pattern):
  dispatch a real `contactsArrayMessage` webhook (per `contracts/contactsArrayMessage.json`)
  through a to-be-added `handle_contacts_array_message`, assert the friendly "one at a time" reply
  and that `denidin_app.ai_handler` was never invoked. **RED**.
- [x] **T010b** [US3] Implement: add a friendly-message constant (e.g.
  `CONTACT_CARD_ONE_AT_A_TIME`) to `apps/denidin-app/src/constants/error_messages.py`, then add
  `@bot.router.message(type_message='contactsArrayMessage')` →
  `handle_contacts_array_message(notification)` in `denidin.py` that replies directly via
  `notification.answer(...)` — no `WhatsAppMessage`/`AIRequest` construction, no `AIHandler` call.
  **GREEN**.
- [ ] **T011** [US3] 👤 **MANUAL APPROVAL GATE**: `quickstart.md`'s US3 scenario, live (share 2+
  contacts at once from a real device). **Waived by user decision, 2026-07-31 — not going to be run; automated verification (unit + integration + billed E2E) judged sufficient.**

---

## Phase 5 — Polish & Cross-Cutting

- [x] **T012** [P] Update `.github/ARCHITECTURE.md`'s message-flow description and CLAUDE.md's
  "Non-text messages" line to mention `contactMessage`/`contactsArrayMessage` alongside the
  existing four media types.
- [x] **T013** `pylint`/`mypy` pass on every changed file (`message.py`, `whatsapp_handler.py`,
  `denidin.py`, `error_messages.py`) — `python3 -m pylint src/ --fail-under=7.0
  --rcfile=.pylintrc` / `python3 -m mypy src/ --config-file=mypy.ini` from `apps/denidin-app/`.
- [x] **T014** Full default `pytest tests/ -v --tb=short` pass (`-m "not billed and not
  expensive"`, the `pytest.ini` default post-Feature-029) confirming no regression to existing
  `textMessage`/media routing, plus a separate `pytest tests/billed/test_denidin_vcf_contact_e2e.py
  -m billed -v` run (T006b/T008b already ran these individually; this is the final combined pass).

---

## Dependencies & Execution Order

- Phase 1 (Foundation) blocks all of Phase 2-4 — `from_notification`'s new branch and the
  `_process_conversational_message` extraction are prerequisites for every story's router path.
- T004 (`runtime_constitution.md` guidance) is a prerequisite for T006a/T008a passing (the model
  needs this guidance to treat vCard content as an `add_client` trigger at all) — must land
  before those E2E tests are run, though it can be authored in parallel with T001-T003.
- Phase 2 (US1) and Phase 3 (US2) are independent of each other (both only depend on Phase 1) and
  share the same new test file (`test_denidin_vcf_contact_e2e.py`) — can be written and run in
  either order, or together, since `billed` tests carry no per-run approval friction to batch
  around (unlike the old `expensive`-only workflow).
- Phase 4 (US3) is fully independent of Phase 2/3 — no shared code path, no AI call, could be
  done first if preferred (it's the cheapest to verify).
- Phase 5 (Polish) runs last.

## MVP

Phase 1 + Phase 2 (US1) alone delivers the core value: a godfather can share a complete contact
card and get a real Morning client created, with the existing approval gate intact.

## Incremental Delivery

1. Phase 1 → Phase 2 (US1) → ship/verify (MVP).
2. Phase 3 (US2) → ship/verify (handles the common no-email case).
3. Phase 4 (US3) → ship/verify (graceful multi-contact decline).
4. Phase 5 → close out.

## Out of Scope (see spec.md / user-stories.md "Out of Scope")

- Batch-creating all contacts from a `contactsArrayMessage`, or looping confirmation per contact.
- Any change to `add_client`'s validation, approval gate, or schema.
- A dedicated vCard-parsing library/module — the model reads raw vCard text directly
  (research.md Decision 2).
- A dedicated RBAC/non-godfather test — no new RBAC surface is introduced (spec.md Clarifications).
