# Tasks: Mark Incoming Messages as Read (Blue Checkmarks) — Feature 045

**Input**: `plan.md`, `spec.md`, `user-stories.md` (this directory)
**Prerequisites**: plan.md (done), spec.md (done, CLARIFIED)

---

**Compliance**: CONSTITUTION.md §V — mocking Green API (a third-party service) IS permitted in
`tests/unit/`, but `tests/integration/` must use the real Green API, never a mock (per
CLAUDE.md's resolution of the ZERO MOCKING banner vs. §I/§V). METHODOLOGY.md §VI (TDD, RED
before GREEN). **No feature flag** — explicit user decision (2026-08-07): this is small,
low-risk, easily-revertable, best-effort/log-only on failure, and always on once merged.

**Chosen call site (resolves plan.md's open scoping question)**: `DeniDinGreenAPIBot.run_forever()`
(`src/utils/green_api_bot.py`) already sits at the one true chokepoint every incoming
notification passes through — `data = _notification_data_or_none(response.data)` — BEFORE
`self.router.route_event(data["body"])` dispatches to any per-type handler. This is earlier
than any router handler and needs no per-handler duplication across
text/contact/image/document/video/audio. `data["body"]` (the raw Green API webhook payload)
already contains `idMessage` and `senderData.chatId` directly — no need to first build a
`WhatsAppMessage`. `DeniDinGreenAPIBot` gains an optional `on_notification_received` callback
attribute (default a no-op), invoked with `data["body"]` right before `route_event`; `denidin.py`
sets it, after `initialize_app()` builds `denidin_app` (needed for the blocked-sender check via
`denidin_app.ai_handler.user_manager.get_user(phone).role`).

---

## Phase 3: User Story 1 — Mark a message read immediately on receipt (Priority: P1)

**Goal**: every non-blocked sender's incoming message gets `bot.api.marking.readChat(chatId,
idMessage=<that message's id>)` called against it, before any RBAC/session/AI processing.

**Independent Test**: `pytest tests/unit/test_read_receipt.py -v` for the decision logic;
`pytest tests/billed/test_real_api_connectivity.py -v -m billed` (real Green API, existing
billed-tier file) for the end-to-end confirmation.

- [x] T001 [US1] **[TEST — RED, unit]** Create `apps/denidin-app/tests/unit/test_read_receipt.py`
  covering the new pure decision function (name TBD at implementation, e.g.
  `_extract_read_receipt_target(body: dict) -> Optional[tuple[str, str]]` returning
  `(chatId, idMessage)` or `None` when either key is missing from a raw notification body) and
  the orchestrating callback (e.g. `mark_message_read(bot, body, is_blocked: bool) -> None`)
  with `bot.api.marking.readChat` **mocked** (permitted for external services in `tests/unit/`,
  per CONSTITUTION.md §V). Cases: not blocked → called once with the extracted
  `(chatId, idMessage)`; blocked → not called; missing `idMessage`/`chatId` in the body → not
  called; `readChat` raising an exception → swallowed, logged, does not propagate (best-effort
  per plan.md). Confirm these FAIL against current code (the functions don't exist yet) — RED
  checkpoint. **DONE 2026-08-07** — confirmed RED (ImportError, functions didn't exist).
- [x] T002 [US1] **[IMPL — GREEN]**
  - `apps/denidin-app/src/utils/green_api_bot.py`: add the two functions from T001 (or land them
    in a new small module, e.g. `src/utils/read_receipt.py`, if that reads cleaner — implementer's
    call, keep it small); add `on_notification_received: Optional[Callable[[dict], None]] = None`
    param/attribute to `DeniDinGreenAPIBot.__init__`; call it (if set) with `data["body"]`
    immediately after the `_notification_data_or_none` check, before `route_event`, wrapped in its
    own try/except so a hook failure can never break the polling loop itself.
  - `apps/denidin-app/denidin.py`: after `initialize_app()`, set
    `bot.on_notification_received = <closure over denidin_app>` implementing the blocked-check
    (`denidin_app.ai_handler.user_manager.get_user(phone).role == Role.BLOCKED` when RBAC is
    enabled, else never-blocked), then calling `mark_message_read(bot, body, is_blocked)`.
  - Re-run T001 — confirm GREEN. **DONE 2026-08-07** — confirmed GREEN: 9/9 passed. Full
    `tests/unit/` (733 passed) and `tests/integration/` (29 passed) also re-run, no
    regressions (one pre-existing `test_green_api_bot.py` test needed the new hook read
    defensively via `getattr` since it builds `DeniDinGreenAPIBot` via `object.__new__`,
    bypassing `__init__` — fixed in the hook itself, not by editing that test).
- [x] T003 [US1] **[TEST — real Green API, `tests/billed/`]** Add a new test to
  `apps/denidin-app/tests/billed/test_real_api_connectivity.py` (same file, same
  `config`/`green_api_client` fixtures as the existing `test_greenapi_can_send_message`,
  `pytestmark = pytest.mark.billed` already covers it — real Green API calls this cheap/no
  per-run approval needed, per CLAUDE.md's billed-tier rules). Pattern: call
  `green_api_client.journal.lastIncomingMessages(minutes=1440)` (same call already used live
  during `speckit.clarify`, see spec.md Q1), take the most recent entry (`pytest.skip(...)` if
  the list is empty — no incoming message in the lookback window to exercise), then call
  `green_api_client.marking.readChat(chatId=<that message's chatId>,
  idMessage=<that message's idMessage>)` and assert the real response is `200` with
  `data.get('setRead') is True` — the same structured confirmation obtained manually during
  clarify. Note in the test's docstring that this only verifies Green API's own acknowledgment
  of the call, not the recipient-visible blue-checkmark render itself (that part was confirmed
  once, manually, by a human checking their real device during `speckit.clarify`, and isn't
  re-automatable via the API alone). **DONE 2026-08-07** — real call against DeniDin test
  instance's actual journal, confirmed `200 {'setRead': True}`.

**Checkpoint**: `pytest tests/unit/test_read_receipt.py -v` (plain run) and
`pytest tests/billed/test_real_api_connectivity.py -v -m billed` (explicit, real-API run) both
pass. **DONE — all 6 tests in the billed file pass, including the new one.**

---

## Dependencies

- T002 depends on T001 (RED before GREEN).
- T003 depends on T002 (needs the real wiring in place to exercise end-to-end).
- No dependency on any other in-flight feature.

## Parallel Execution

Not applicable — three sequential tasks, one small feature.

## Implementation Strategy

**MVP = the whole feature**: T001-T003 is the entire scope. Once all pass, this feature is
complete — proceed to closing out per `plan.md`'s Phase 4 (move spec to `specs/done/`).
