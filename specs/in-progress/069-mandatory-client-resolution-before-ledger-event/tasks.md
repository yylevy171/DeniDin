# Tasks: Post-Turn Ledger Capture with Mandatory Client Resolution

**Feature**: 069-mandatory-client-resolution-before-ledger-event
**Branch**: `feature/069-mandatory-client-resolution-before-ledger-event`
**Input**: [plan.md](./plan.md) · [spec.md](./spec.md) · [user-stories.md](./user-stories.md) · [research.md](./research.md) · [data-model.md](./data-model.md) · [contracts/](./contracts/)

> **Redesigned 2026-09-01.** This file is rebuilt around the post-turn recognition mechanism.
> The old inline-`capture_ledger_event` design (MCP-suppression narrowing, the
> `record_unresolved_ledger_capture` tool, a new `DOCXExtractor` AI call, the old
> `contracts/ledger-capture-suppression.md` / `contracts/unresolved-capture-logging.md`) is
> **gone** — see the `contracts/` folder (C1/C2/C5/C6, C3, C4, C9) for the current design.

---

## Compliance (binding)

- **METHODOLOGY §VI** — "TDD" here = the **`billed`/`expensive` acceptance suite** (real
  OpenAI + real Morning sandbox, user-perspective). Those scenarios are **described in
  user-experience terms** in Phase 11; the **test code is written AND run once, together, as
  a final acceptance pass, after every Phase 2–10 unit/integration task is GREEN**.
- **METHODOLOGY §VI.b + Feature 069 deviation** (operator direction, 2026-09-01: *"unit and
  integration tests I don't need to approve"*) — every unit/integration **Task A (tests)** is
  still written **RED first**, before its Task B, and is **immutable once committed** — but
  there is **no human approval gate** between Task A and Task B for the unit/integration tier.
  The **👤 approval gates that remain**: constitution / operator-facing **wording** (§XIX —
  T015 and any wording delta) and **every `expensive` acceptance run** (one per test, every
  time). `billed` runs freely. Recorded in `plan.md` Complexity Tracking.
- **METHODOLOGY §XIX** — the rewritten `config/runtime_constitution.md` "Ledger Event
  Recognition" section (contract C4) and any operator-facing string are **UX-impacting**:
  drafted and **👤 user-approved before the dependent impl task**, and land in the **same PR**
  as the code. **HARD STOP.**
- **METHODOLOGY §XXI** — the rewritten "Ledger Event Recognition" section gets an explicit
  scope statement (when the client-resolution gate applies / does NOT — `payer_name`,
  `חשבונית`-by-construction / ambiguity→ask) + **bidirectional** cross-references with
  "Resolving a client by name", and out-of-scope notes in "Reminder Management" and
  "Invoice Management". Note this feature **removes** a tool (`capture_ledger_event`) from the
  main turn and keeps one read-only tool (`query_ledger_events`).
- **CONSTITUTION §V / ZERO MOCKING of internal components** — unit tests may mock **only**
  OpenAI / Green API; integration & acceptance tests mock nothing internal and never set a
  feature flag. **No feature flag.** ~~No config key~~ → **superseded 2026-09-03 (design
  thread decision #2): ONE config key, `ledger_recognition_context_window_hours` (float,
  default 1.0, DI, no env var)** — the recognition call's context window. First and only
  config key for the feature.
- **CONSTITUTION §XVIII** — Morning tunnel down during resolution → tell the operator, the
  event never completes, **zero** events persisted. No guessed `client_name`.
- **CLAUDE.md — ledger schema is human-only** — `CURRENT_SCHEMA_VERSION` stays **2**, **no**
  `LedgerEvent` field added (the store-anyway marker is free text in the existing
  `description`), **no test asserts `schema_version`'s value** anywhere.
- **CLAUDE.md — `billed` vs `expensive`** — `billed` run freely via
  `scripts/run_single_test.sh` / `scripts/run_multiple_billed_tests.sh` (sound off each
  result live); every `expensive` run needs its **own fresh explicit approval**, one at a
  time, read `logs/test_logs/` first. Never `pytest … | tail`/`| grep`/`| head`.
- **Recorded-date pointer** — **superseded 2026-09-03 (design thread decision #10):**
  `הסכם` / `בנק` → `event_datetime` **and** the `event_id` timestamp component come from the
  **completing message** (the message that completed the event this round — the T4 reply in a
  resolution detour, the correction message for an amendment), via its persisted
  `Message.timestamp` parsed + formatted `%d/%m/%Y %H:%M`. `חשבונית` → the **Morning document
  datetime** (`creation_date` from the real `create_*` response). `trigger_message_id` in the
  verdict is **informational only** (audit breadcrumb). **Never** `now_local()`, never the
  recognition-call clock. Every hardcoded acceptance-test `event_datetime` expectation depends
  on this.

## Format: `- [ ] [TaskID] [P?] [Story?] Description with file path`

- **[P]** — parallelizable (different file, no dependency on an incomplete task).
- **[US#]** — user-story phases only (Setup / Enabler / `speckit.analyze` / Acceptance /
  Polish carry none).
- **T###a** = write tests (RED, written before its Task B, immutable once committed) ·
  **T###b** = implement (BLOCKED until T###a is written and RED — **no** approval gate for the
  unit/integration tier per the 2026-09-01 deviation).
- All paths are under `apps/denidin-app/` unless stated.

### Phase-number map (tasks.md ↔ plan.md "Phase plan")

`tasks.md` adds an explicit **Setup** (Phase 1) and **Polish** (Phase 12). `plan.md`'s phase
plan starts numbering at the enabler. Mapping: `tasks 2 (Enabler)` = `plan 1` · `tasks 3` =
`plan 2 (US1)` · `tasks 4` = `plan 3 (US3)` · `tasks 5` = `plan 4 (US2)` · `tasks 6` =
`plan 5 (US4)` · `tasks 7` = `plan 6 (US5)` · `tasks 8` = `plan 7 (US8)` · `tasks 9` =
`plan 8 (US7 incl. 7d / US9)` · `tasks 10` = `plan 8b (US10)`. `speckit.analyze` is **T030A**
(monotonic: `T030` < `T030A` < `T031`), between tasks.md Phase 10 and Phase 11.

**Story renumbering (2026-09-02 re-lock):** the old bank-deposit-image-naming-an-institution
story was **deleted** ("remove, irrelevant"); everything after it shifts down one — old US9
(won't-provide-email/phone) → **US8**, old US10 (photographed `הסכם`) → **US9**, old US11
(`docx` `הסכם`) → **US10**. US7 gains **7d** (exact Morning match → no question, no new
client — the image analog of US6).

---

## 🔁 DESIGN-THREAD ADDENDUM — decisions 1–12 (2026-09-03, ALL LOCKED, "approved. go on")

An extended design thread refined the recognition mechanism. The task bodies below predate
it; where they conflict, **this addendum wins**. All landed in the Phase 2–8 code as of
2026-09-03 (full `tests/unit` + `tests/integration` green, 1321 passed), uncommitted.

| # | decision | where it lives now |
|---|---|---|
| 1 | Design A (smart post-turn recognition call) kept — not option B/C. | `AIHandler.recognize_ledger_event` |
| 2 | **Context window = past 1 hour.** New config key `ledger_recognition_context_window_hours` (float, default 1.0, DI, no env var) — the feature's ONLY config key. | `models/config.py`, `denidin.py` `__main__` config_dict, `_assemble_recognition_input` |
| 3 | Narrowed prompt job — **NARROW, 3-part trigger**: the last operator message (1) COMPLETED an event, OR (2) STATES a whole standalone event, OR (3) ADDS TO / CORRECTS / CANCELS an arrangement in the window OR the ledger. Judge the last message only; never sweep the window for old un-captured events. `[client]` messages are context only. | `config/ledger_recognition_prompt.md` |
| 4 | **Content-fingerprint dedup in CODE** (not prompt, not event_id): `בנק` = source_type+client+txn_date+normalized amount+bank triplet+date; `הסכם` = agreement_id+sorted components+vat+payer+date; `חשבונית` keeps its existing (date, display_number) guard. Same content same day = skip; any content change = new record (amendment). | `LedgerEventManager._content_fingerprint` / `_is_duplicate_recognized_event` |
| 5 | Amendments = match today: 2nd `יצירה` record, folded current state, no in-place edit. | (unchanged behavior) |
| 6 | **`Message.mcp_calls` persisted** — added to the `Message` dataclass, threaded through `add_message*`, populated on the assistant store from that turn's `AIResponse.mcp_calls`. Local function calls (the conversation's own `query_ledger_events`) are NOT persisted. | `session_manager.py`, `ai_handler._finalize_response` |
| 7 | Client "resolved" = **MCP evidence in the window ONLY** (`resolve_client_name` exact match / `add_client` / `create_*` success). A name in prose/OCR is a candidate, never resolution. RISK #2 accepted (strict) + a relentless constitution rule ("resolve every time, explicit call, no 'I know them'"). Full fix = Feature 072. | prompt + constitution |
| 8 | Crash-window gap accepted — no startup recognition sweep. | — |
| 9 | **The recognition call ALWAYS queries the ledger once up front** when the round concerns a client (identity-hinted, client's name) → full client history as context → then decides. `query_ledger_events` attached; bounded chained loop, cap `MAX_RECOGNITION_QUERY_ROUNDS = 3`; in-memory (no tunnel dep). Fallback → `reference_hint` + `REFERENCE_PLACEHOLDER` = today's parity. | `recognize_ledger_event` |
| 10 | **Dating: `הסכם`/`בנק` → `event_datetime` AND `event_id` timestamp = the COMPLETING message** (not the economic-content message). `חשבונית` → the Morning document datetime. `trigger_message_id` in the verdict = informational only. | `_message_epoch` (renamed from `_trigger_epoch`), `persist_recognized_event` |
| 11 | **Option 1**: dedicated prompt file `config/ledger_recognition_prompt.md` (mtime-cached `_load_recognition_prompt()`, same `constitution_config.base_dir`). Ledger-recognition rules move OUT of the constitution; the constitution keeps only the conversational side. | new file + `_load_recognition_prompt` |
| 12 | **Field taxonomy** (#3.5): kill the "generated" bucket → mandatory / conditional / keep-if-provided + a "filled by: model\|code" side-annotation. A deterministic **`_mandatory_field_gaps` check runs IN THE LEDGERER** over the fully-assembled event. **On a gap: PERSIST ANYWAY, flagged incomplete** — `[רישום חלקי — חסר: <fields>]` into `description`. | `LedgerEventManager._mandatory_field_gaps` + `persist_recognized_event` |

**Task-body corrections implied by the addendum:**
- T004b / T005b / T006a / T023a etc. — every mention of "the **trigger** message's timestamp"
  / "option A" for `הסכם`/`בנק` dating → **the completing message** (#10).
- T004a/T004b — `recognize_ledger_event` now also attaches `query_ledger_events` + runs a
  bounded query loop; instructions come from `_load_recognition_prompt()`, not the full
  constitution (`constitution_text` param kept but ignored for call-site compat) (#9, #11).
- "No config key exists" (Compliance) → one config key, #2.
- T015 wording — the §XIX draft is **T015 DRAFT v3** (scratchpad), **applied 2026-09-03 after
  the user approved** ("approved. go on", with wording latitude); T017b done. The recognition
  rules moved to `config/ledger_recognition_prompt.md`; the constitution section was slimmed.
- Dedup (#4) + completeness re-check (#12) are new deterministic ledgerer steps — add unit
  coverage in the Phase 12 polish / alongside T005a's file.
- denidin.py button-tap handler also runs `_run_post_turn_ledger_recognition` now (parity).
- **Media routing (Phases 9–10), as built 2026-09-03:** `_process_media_message` (denidin.py)
  rewrites the inbound notification's `messageData` to a `textMessage` carrying the stash and
  calls `_process_conversational_message(notification)` — it does **not** build a synthetic
  `AIRequest` and does **not** add a separate `T025b` routing helper. `_send_ai_response_and_attach`
  + `_run_post_turn_ledger_recognition` run because the conversational path already runs them.
  `whatsapp_handler.handle_media_message` now returns the `MediaHandler` result dict (typed
  `Optional[Dict]`) and suppresses the plain media summary when `ledger_stash` is present.
- **T028b `docx` signal, as built 2026-09-03:** `DOCXExtractor.analyze_media` previously
  returned no `document_analysis` at all and `_analyze_document` hardcoded `document_type
  = "generic"` — there was no working signal. Added a deterministic classmethod
  `_classify_document_type(text)` (keyword scan for `הסכם שכר טרחה` / `שכר טרחה` /
  `הסכם התקשרות` / `הסכם ייצוג` → `"הסכם"`, else `"generic"`) and surfaced `document_analysis`
  from `analyze_media`. **No new OpenAI call** — within Assumption 8. `media_handler.py` Step 10
  routes on `media_type == "docx" and document_analysis["document_type"] == "הסכם"`.
- **`_content_fingerprint` (#4) bug fix:** its inner `amt()` now coerces its argument to `str`
  before `_normalize_amount` — a persisted stored event's component `amount` is already a
  normalized number, and the regex-based normalizer crashed on a bare int.

---

## Phase 1: Setup

**Purpose**: baseline the working tree; no code change.

- [ ] T001 Confirm `git branch --show-current` is `feature/069-mandatory-client-resolution-before-ledger-event`; activate **this clone's own** venv and verify `which python3` resolves inside `apps/denidin-app`; run `python3 -m pytest tests/unit tests/integration -q` from `apps/denidin-app/` and record the green baseline.
- [ ] T002 [P] Rewrite `apps/denidin-app/tests/fixtures/ledger_069/README.md` for the redesigned manifests: the per-fixture ground-truth convention (`<name>.<ext>` + `<name>.manifest.json`, shape per `contracts/payload-fidelity-manifest.md`), the 8 fixture names (`agreement_new_client.txt`, `agreement_ambiguous.txt`, `agreement_photo_multi.png`, `agreement_doc_multi.docx`, `deposit_zero_matches.png`, `deposit_one_partial.png`, `deposit_two_plus.png`, `deposit_exact_match.png`), the `client_resolution.scenario` enum, US1–US10 mapping. The README **must pin the exact persisted `LedgerEvent` field names** manifests key against — read them from `src/managers/ledger_event_manager.py`'s `record` dict (~lines 1079–1145; note there is **no** `accounting_document_type` — the document type lives in `event_subtype`, verified line 1084) — so a manifest never asserts against a Hebrew stash label. No fixture files yet — authored in Phase 11.

---

## Phase 2: Mechanism move — the enabler slice (C1 / C2 / C5 / C6)

**Purpose**: delete the inline-`capture_ledger_event` machinery and stand up the post-turn
recognition call + the ledgerer + the three breadcrumbs + the `denidin.py` post-turn hook.
No story-visible behavior on its own; **delivers US1 and US3 behavior once green**.

**⚠️ CRITICAL**: Phases 3–11 are BLOCKED until this phase is complete.

### Tests (Task A — RED, written and committed before any Task B; no approval gate)

- [x] T003a [P] Write `tests/unit/test_main_turn_tools.py` (C5, `contracts/recognition-and-logging.md`): a godfather/admin conversational turn is assembled with `query_ledger_events` attached and **without** `capture_ledger_event` / `LEDGER_EVENT_TOOL`; `_call_openai_ledger_followup_api`, the bugfix-018 `morning_mcp_used_this_turn` suppression symbol, `_handle_ledger_event_capture`, and the `protocol_violation` (`len(ledger_calls) > 1` / `single_call_unparseable`) branch are **gone** (import-level / `hasattr` / attribute assertions). A client-role turn still gets no ledger tools. OpenAI mocked.
- [x] T004a [P] Write `tests/unit/test_recognition_call.py` (C2, `data-model.md §2`): `recognize_ledger_event(self, *, session, reply_text, turn_mcp_calls, constitution_text) -> dict` — given a constructed session + `turn_mcp_calls` + a stubbed OpenAI response returns the right verdict: `complete` with a fully schema-mapped `event` + `trigger_message_id` when every mandatory field for the `source_type` is present; `none` on a missing mandatory field / unresolved client / a read-only Morning question / ordinary chatter / a mid-detour turn; `declined` (with `source_type` + `client_name_stated` + `reason:"declined_by_operator"`) when the transcript shows the operator was offered the closed store-anyway question and explicitly answered *don't store*; **one-shot retry** on a parse failure / `is_incomplete_capture` (reuses `capture_ledger_events_from_text`'s retry shape); a successful `create_*` in `turn_mcp_calls` → `event.source_type == "חשבונית"` mapped from the **tool result**, not the prose (`event_subtype` = doc type, `accounting_document_display_number` / `amount` / `txn_date` from the response); the method's input assembly includes the conversation + `reply_text` + `turn_mcp_calls` verbatim + `constitution_text`; **output is never appended to the session** and never returned up the reply path; **multi-event / staggered (FR-069-016, gate G16)**: given a turn whose context holds one now-complete event plus a sibling still missing a mandatory field, the verdict is `complete` for the finished one only; on a later turn where the sibling's last field arrives, that turn's call returns `complete` for the sibling — one event per turn, never a lost sibling. OpenAI mocked.
- [x] T005a [P] Write `tests/unit/test_ledgerer.py` (C6, `data-model.md §3`): `persist_recognized_event(verdict, session, completing_message_id)` on a `complete` verdict → `event_datetime` = the message named by `verdict["trigger_message_id"]`, its persisted `Message.timestamp` ISO string parsed and formatted `%d/%m/%Y %H:%M` (option A, 2026-09-02 — **not** `local_from_timestamp`, **not** `now_local()`); `captured_at` = `now_local()`; `event_id` = source-type prefix (`A`=`הסכם`, `B`=`בנק`; `חשבונית` keeps the existing accounting prefix) + `DDMMYY` + `HHMM` + same-minute sequence digit; `הסכם` → `agreement_id` + per-component `component_id`, **one persisted file per component** (via the existing `merged_event = {**shared, **component}` loop, `ledger_event_manager.py:1173`); an already-decided `event.reference` id → denormalized into `_linked_document` display fields from the in-memory index (**no** lookup of *whether* to link); `חשבונית` dedup through `_ensure_accounting_document_cache()` keyed on `accounting_document_display_number` (`ledger_event_manager.py:1163-1169`); the new `event_id`(s) appended to the **completing** message's `Message.ledger_event_ids` (**not** the trigger message); **no** OpenAI call, **no** `resolve_client_name` call, **no** ledger query (assert via a spy that raises on any of them); `declined` → **nothing** persisted, no index append, no `Message` mutation; `none` → nothing. **No assertion on `schema_version`'s value.**
- [x] T006a [P] Write `tests/unit/test_ledger_capture_breadcrumbs.py` (C6 logging, `data-model.md §4`): exact `[069]` line formats for `recognized` (before persist), `written` (after persist, one per persisted event, carrying the real `event_id`), and `declined by operator` (on a `declined` verdict, carrying `name=<client_name_stated!r>` + `reason=declined_by_operator`); `type` map `בנק`→`deposit` / `הסכם`→`agreement` / `חשבונית`→`invoice`; every line carries a `now_local()` `time=` field with a real offset; `none` → **no** INFO line (DEBUG only); a `recognized` with a following `written` is paired on `session`. caplog; OpenAI not involved.
- [x] T007a [P] Write `tests/integration/test_ledger_client_resolution_routing.py` — the enabler slice (C1): a real `textMessage` webhook JSON for an exact-match `הסכם` → `bot.router` → `_process_conversational_message` → (OpenAI stubbed: a normal reply, then a `complete` recognition verdict) → **exactly one** `LedgerEvent` file under `{data_root}/events/`, `client_name` == the exact Morning name, the operator's normal conversational reply is present (not only a resolution question), the completing `Message.ledger_event_ids` links the new `event_id`, the C6 `recognized` + `written` lines both appear, and `_call_openai_ledger_followup_api` is **never** invoked (it no longer exists). Real router/handlers/managers; only OpenAI + Green API mocked.
- [x] **Checkpoint (no approval gate)**: confirm T003a–T007a are all written, RED, and committed before starting the Task B items. Tests are immutable once committed.

### Implementation (Task B — BLOCKED until T003a–T007a are written and RED)

- [x] T003b In `src/handlers/ai_handler.py`: **DELETE** `_call_openai_ledger_followup_api`; the bugfix-018 MCP-suppression guard (`morning_mcp_used_this_turn` → strip `capture_ledger_event`); the `protocol_violation = len(ledger_calls) > 1` / `single_call_unparseable` whole-turn-rejection machinery; `_handle_ledger_event_capture`; and `LEDGER_EVENT_TOOL` / `capture_ledger_event` from `_assemble_tools` / `_build_ledger_event_tool` for the **main conversational turn**. **KEEP** `query_ledger_events` attached to the main turn for godfather/admin. Leave `LEDGER_EVENT_TOOL`'s **schema constant** in place (reused by the recognition call). **BLOCKED until T003a is RED.**
- [x] T004b Implement `recognize_ledger_event(self, *, session, reply_text, turn_mcp_calls, constitution_text) -> dict` in `src/handlers/ai_handler.py` — one dedicated **text-only** OpenAI call (generalizes `capture_ledger_events_from_text`, `ai_handler.py:~3321`, from "OCR'd media text" to "whole turn context") using `LEDGER_EVENT_TOOL`'s JSON schema for the `event` object; assembles input from the session messages + `reply_text` + `turn_mcp_calls` (calls **and results** verbatim) + `constitution_text`; returns the tri-state verdict (`data-model.md §2`); one-shot retry on parse failure / `is_incomplete_capture`; **no** follow-up round-trip; output never surfaced. `חשבונית` branch: when `turn_mcp_calls` holds a successful `create_*`, populate `event` from the real Morning response. **BLOCKED until T004a is RED.**
- [x] T005b Implement `persist_recognized_event(verdict, session, completing_message_id)` in `src/managers/ledger_event_manager.py` — **THE LEDGERER**, zero-AI (FR-069-004). On `complete`: resolve `event_datetime` by looking up the message named by `verdict["trigger_message_id"]` in `session` and parsing its persisted `Message.timestamp` ISO string, formatted `%d/%m/%Y %H:%M` (the hard pointer, option A); `captured_at = now_local()`; mint `event_id` (+ `agreement_id` / per-component `component_id` for `הסכם`); explode `event.components` via the existing `merged_event = {**shared, **component}` loop; denormalize an already-decided `event.reference` into `_linked_document` (`ledger_event_manager.py:~1060-1077`); dedup (`self._index`; `חשבונית` via `_ensure_accounting_document_cache()`); persist immutable JSON (`json.dump(record, f, sort_keys=True, ensure_ascii=False, indent=2)` → `.json.tmp` → `.replace()`); `self._index.append(record)`; append the new `event_id`(s) to the **completing** message's `Message.ledger_event_ids`; emit the `recognized` (before persist) + `written` (after, one per event) INFO breadcrumbs. On `declined`: emit the `declined by operator` INFO breadcrumb; persist nothing. On `none`: nothing (DEBUG only). Reuse `add_ledger_events_from_call`'s persistence path — **no** OpenAI, **no** client / Morning / ledger lookup. `CURRENT_SCHEMA_VERSION` and `_ensure_accounting_document_cache()` **unchanged**. **BLOCKED until T005a + T006a are RED.**
- [x] T007b In `denidin.py`: extract the existing `_process_conversational_message` send + pending-approval-attach block (~lines 588–595: `sendInteractiveButtons` when `offer_approval_buttons`, then `pending_approval_manager.attach_sent_message_id(...)` + `pending_local_tool_approval_manager.attach_sent_message_id(...)`) into a thin module-level helper `_send_ai_response_and_attach(chat_id, ai_response, answer_fn)` (byte-for-byte identical behavior — existing tests stay green). Add a module-level helper `_run_post_turn_ledger_recognition(*, session, chat_id, sender_phone, reply_text, turn_mcp_calls)` that runs **only** for a godfather/admin turn (same RBAC predicate that gates `query_ledger_events`), calls `ai_handler.recognize_ledger_event(...)` then `ledger_event_manager.persist_recognized_event(...)`, and is wrapped so **any exception is logged and swallowed** (FR-069-006 — the reply the operator already got changes 0 bytes). Wire one post-turn call to `_run_post_turn_ledger_recognition(...)` into `_process_conversational_message`, after `_send_ai_response_and_attach(...)`. **BLOCKED until T007a is RED.**
- [x] T008 Run `python3 -m pytest tests/unit/test_main_turn_tools.py tests/unit/test_recognition_call.py tests/unit/test_ledgerer.py tests/unit/test_ledger_capture_breadcrumbs.py tests/integration/test_ledger_client_resolution_routing.py -v` + full `tests/unit` + `tests/integration` — all green.
- [x] T008b (operator request, 2026-09-03) **Ledger-event audit**: `src/utils/ledger_audit_log.py` — `log_ledger_event_created(record)` emits one INFO `[AUDIT-LEDGER]` line per persisted event carrying the event's **full JSON** (keys sorted). Single call site: `LedgerEventManager.add_ledger_event` right after `self._index.append(record)`, so BOTH the post-turn ledgerer and the Feature 025 sweep are covered. Unit test: `tests/unit/test_ledger_audit_log.py`.
- [x] T008c (operator request, 2026-09-03) **Bare-contact-detail hardening** (the "email only" false-capture bug seen in testing): explicit negative scoping added to `RECOGNITION_TOOL`'s description AND `recognize_ledger_event`'s instructions ("a bare email / phone / ID / address / client name, or a field supplied for a client record, is NOT a ledger event → `verdict='none'`; when in doubt, none"). Code-level model instruction only, never operator-facing — not §XIX-gated. Billed proof: T041b.

**Checkpoint**: the inline mechanism is gone; every godfather/admin turn ends with one
text-only recognition call whose output feeds the zero-AI ledgerer; every recognized /
written / declined capture is traceable in the log.

---

## Phase 3: User Story 1 — Mechanism move / decoupling, exact-match client (Priority: P1) 🎯

**Goal**: prove the decoupled path captures a complete `הסכם` for an exact-match client with
**no second reply round-trip** and **no inline tool** — and (US6 anti-over-prompt) adds
**zero** friction when the name already matches Morning exactly (FR-069-001..008).

**Independent test**: `user-stories.md` US1 Independent Test.

- [x] T009a [US1] Extend `tests/integration/test_ledger_client_resolution_routing.py` with the US1 assertions — an exact-match `הסכם` turn: the reply is produced by the main turn **independently** of recognition (force `recognize_ledger_event` to raise → the reply is byte-for-byte unchanged, SC-009); exactly one `LedgerEvent` after the turn against the exact Morning name; **zero** client-identity question in the reply (US6); the `recognized` + `written` breadcrumbs pair on `session`. OpenAI stubbed.
- [x] T009b [US1] No new production code expected beyond Phase 2 — if T009a surfaces a decoupling gap, apply the minimal fix in `denidin.py` / `ai_handler.py`. Otherwise mark "covered by Phase 2". **BLOCKED until T009a is RED.**
- [x] T010 [US1] ✅ Self-verify checkpoint (no user gate): decoupled exact-match `הסכם` text captures silently, one turn, reply unchanged — full billed proof is Phase 11 (T039).

**Checkpoint**: the decoupled capture path works end-to-end for the clean case.

---

## Phase 4: User Story 3 — Regression guard (no spurious capture / no lost reply) (Priority: P1)

**Goal**: the two historical incidents the deleted suppression guard existed for become
**structurally impossible** — there is no inline `capture_ledger_event` to misfire, and the
reply is produced independently of recognition (FR-069-005, US3).

**Independent test**: `user-stories.md` US3 Independent Test (both historical shapes).

- [x] T011a [US3] Extend `tests/integration/test_ledger_client_resolution_routing.py` with the US3 shapes — (a) **2026-07-28**: a turn where the model reads `list_invoices` output back to the operator → the reply is delivered intact, the post-turn recognition call sees a read-only Morning question and returns `none`, **0** `LedgerEvent` files; (b) **2026-08-02**: a two-word field-filling reply ("עבור ייעוץ") mid-`create_combo_document` approval → reply intact, recognition returns `none` (incomplete event), **0** files. Plus the structural assertion: no `capture_ledger_event` / `LEDGER_EVENT_TOOL` in the main-turn tool list. OpenAI stubbed.
- [x] T011b [US3] No new production code expected — apply a minimal fix only if T011a fails. Otherwise "covered by Phase 2". **BLOCKED until T011a is RED.**
- [x] T012 [US3] ✅ Self-verify checkpoint (no user gate): both shapes produce an intact reply and no spurious event — full billed proof is Phase 11 (T041).

**Checkpoint**: the suppression guard is safely gone; no regression on either incident shape.

---

## Phase 5: User Story 2 — Morning "create" captured synchronously (Priority: P1) — C8

**Goal**: a `create_*` Morning MCP call that succeeds in a conversation is a complete
`חשבונית` event (client resolved by construction); the recognition call — whose input
includes the `create_*` call **and its result** — recognizes it **synchronously that turn**
from the real Morning response, and it dedups against Feature 025 (FR-069-012/025/026/027/028).

**Independent test**: `user-stories.md` US2 Independent Test.

- [x] T013a [US2] Extend `tests/integration/test_ledger_client_resolution_routing.py` with the US2 scenario — a turn whose `turn_mcp_calls` carries a successful `create_invoice` call + a realistic Morning response → the post-turn recognition call returns `complete` with `source_type="חשבונית"`, `event_subtype` = the document type, `accounting_document_display_number` / `amount` / `txn_date` from the **response** (assert they are **not** re-derived from the operator prose — feed prose that disagrees); exactly one `חשבונית` `LedgerEvent` after the turn; assert the display number is now in `_ensure_accounting_document_cache()` so a subsequent `add_ledger_events_from_call(session_id="accounting-reconciliation", …)` with the same display number is a **no-op** (Feature 025 next-tick dedup, C8). OpenAI + Morning stubbed.
- [x] T013b [US2] Any wiring needed so `persist_recognized_event` routes a `חשבונית` verdict through `add_ledger_events_from_call` unchanged (expected: none beyond Phase 2's T005b). **BLOCKED until T013a is RED.**
- [x] T014 [US2] ✅ Self-verify checkpoint (no user gate): an in-conversation Morning create yields exactly one `חשבונית` event that turn; Feature 025 writes no second file — full billed proof is Phase 11 (T040).

**Checkpoint**: conversation-sourced Morning documents land in the ledger synchronously,
deduped against the reconciliation sweep.

---

## Phase 6: User Story 4 — FLAGSHIP: new-client typed `הסכם` + constitution guidance C4 (Priority: P1)

**Goal**: a `הסכם` text naming a client Morning has never heard of → full name + email +
phone → `add_client` approval → the agreement is captured against the newly-created Morning
client with **every** fee component / date / subtype / `payer_name` from the original text
intact, and `event_datetime` = the **original agreement message's** timestamp
(FR-069-010..019, FR-069-020/021/022). No new resolution machinery — `add_client` reuses
`PendingApprovalManager` unchanged (C7).

**Independent test**: `user-stories.md` US4 Independent Test.

> **STATUS 2026-09-03 (updated)**: T016a's multi-turn new-client scenario + the
> declined-approval branch are implemented and GREEN
> (`test_us4_new_client_agreement_nothing_until_client_created`,
> `test_us4_declined_approval_writes_nothing`). **T015 DRAFT v3 was presented and
> the user approved it** ("approved. go on", wording latitude granted) — **T015
> and T017b are DONE**: the recognition rules now live in the NEW
> `config/ledger_recognition_prompt.md`; the constitution's "Ledger Event
> Recognition" section was slimmed to the conversational side; all
> `capture_ledger_event` cross-refs updated; a back-ref sentence added into
> "Resolving a client by name". The §XIX gate is cleared for Phases 9–10 wording
> (Phase 9/10 stash strings still get a wording pass if they change what the
> operator sees).

- [x] T015 [US4] ✅ **DONE 2026-09-03** (user-approved, wording latitude). Instead of a
  single rewritten constitution section, the recognition rules moved to a NEW dedicated file
  `config/ledger_recognition_prompt.md` (decision #11), and the constitution's "Ledger Event
  Recognition" section was slimmed to the conversational side only. Original task text kept
  below for the record. — **Draft** the **rewritten "Ledger Event Recognition" section** for `config/runtime_constitution.md` (contract C4), with the new subsection **"אימות לקוח לפני רישום אירוע"** ("Client resolution before an event is recorded"), covering **all** of C4's behavioral requirements G1–G17: recognition is **post-turn, not an inline tool** (remove all old inline-`capture_ledger_event` guidance — call it N times, the components-array workaround, one-call-per-turn); the conversational model's only ledger tool is `query_ledger_events` (read/search); the **per-type mandatory-field contract + "complete event" definition** (`data-model.md §1` tables); **mandatory client resolution** for `הסכם` / `בנק` / `חשבונית` via the **identical** steps as "Resolving a client by name" (exact → silent same turn; 1 non-exact candidate → name it + offer create-new; 2+ → list + offer create-new; none → full name + email + phone → `add_client` → its own approval; reuse a client resolved earlier in the same conversation, no re-ask); resolution is **a sub-step, never the goal** — the terminal step is the event being recorded with the resolved name **and every other extracted field** (wording explicitly **not** "ends in create new client"); **store-anyway** only after a **2nd** email/phone decline, then a distinct closed "store without full client details, or not?" question, marker phrase `[לקוח לא אומת במורנינג]` into `description` on *store*, `declined` on *don't store*; **ambiguous** disambiguation reply → re-ask **once** as a closed choice, then abandonment (cite the existing "short/ambiguous replies answer the most recently pending question in the same context" rule); **does NOT apply to** `payer_name` (free text, may differ from `client_name`) or the `חשבונית` client (resolved by construction); tunnel down → tell the operator, capture nothing. Plus **bidirectional cross-references** (§XXI): "Resolving a client by name" → "this same process is mandatory before a `הסכם` / `בנק` / `חשבונית` ledger event can be complete"; "Reminder Management" → out-of-scope note; "Invoice Management" → explicit line that the client-resolution sub-step of a ledger recognition is not itself a document-creation action. **👤 USER APPROVAL GATE — exact wording approved before T017b (METHODOLOGY §XIX HARD STOP).**
- [ ] T016a [US4] Extend `tests/integration/test_ledger_client_resolution_routing.py` with the US4 multi-turn scenario — OpenAI stubbed to: turn 1 `resolve_client_name`(0 matches) + a reply asking for full name + email + phone, recognition → `none`, **no** file; turn 2 (operator supplies the three) `add_client` → pending approval, recognition → `none`; turn 3 (approval "כן") `add_client` resolves, then the **completing** turn's post-turn recognition → `complete`. Assert: **no** `LedgerEvent` file until turn 3; after turn 3 exactly one `הסכם` event with `client_name` == the created Morning name, **every** fee component + agreement date + `event_subtype` + `payer_name` present (`payer_name` persisted **verbatim**, not routed through resolution, `payer_name != client_name`), `event_datetime` == `local_from_timestamp(<turn-1 message ts>)`; the `Message.ledger_event_ids` back-link is on the **turn-3** (completing) message; the declined-approval branch ("לא") writes **no** file and creates **no** client. Real router/handlers/`PendingApprovalManager`; only OpenAI + Green API stubbed.
- [ ] T016b [US4] If T016a surfaces a wording gap in the T015 guidance for the new-client sub-step (G6/G7), draft the delta and re-obtain **👤 user approval**, then apply. Otherwise: no code change — "covered by T017b". **BLOCKED until T016a is RED** (the wording-delta path still needs §XIX approval).
- [x] T017b [US4] ✅ **DONE 2026-09-03** — applied `config/ledger_recognition_prompt.md` (new) + the slimmed constitution "Ledger Event Recognition" section + all `capture_ledger_event` cross-ref edits + the "Resolving a client by name" back-ref. Constitution + prompt both hot-reload by mtime; `_load_recognition_prompt()` is the code loader.
- [ ] T018 [US4] ✅ Self-verify checkpoint (no user gate): the new-client `הסכם` text flow behaves per US4 scenarios 1–4; the full guidance section exists for every later phase to lean on. Full billed proof is Phase 11 (T042).

**Checkpoint**: new-client `הסכם` text path complete; the constitution client-resolution gate
is live.

---

## Phase 7: User Story 5 — Ambiguous client name on a fee agreement (Priority: P1)

**Goal**: a `הסכם` text naming a partial/near match → DeniDin lists **every** candidate + the
create-new option and captures nothing until the operator chooses; an ambiguous
disambiguation reply → re-ask **once** as a closed choice, then abandonment (G3/G4/G9,
FR-069-018). No new code beyond the T015 guidance.

**Independent test**: `user-stories.md` US5 Independent Test (5a / 5b / scenario 5).

- [ ] T019a [US5] Extend `tests/integration/test_ledger_client_resolution_routing.py` with the US5 scenarios — OpenAI stubbed to: **5a** `resolve_client_name`(1 non-exact candidate) → reply naming the one + offering create-new (not "be more specific"), recognition → `none`; **5b** `resolve_client_name`(2+ candidates) → reply listing all + create-new, `none`; operator picks a candidate → next turn's recognition → `complete` with that exact name; **scenario 5** a bare "כן" / unrelated reply → one re-ask as a closed choice, `none`, no file; a **2nd** still-ambiguous reply → abandonment, no file, no capture; **G15** a correction to an arrangement resolved earlier in the same conversation → reuse the prior exact Morning name, no 2nd `resolve_client_name`, captured as a fresh event.
- [ ] T019b [US5] Wording delta for G3/G4/G9 if T019a surfaces a gap → **👤 approval** → apply. Otherwise "covered by T017b". **BLOCKED until T019a is RED.**
- [ ] T020 [US5] ✅ Self-verify checkpoint (no user gate): ambiguous `הסכם` text behaves per US5 5a/5b + scenario 5 — full billed proof is Phase 11 (T043).

**Checkpoint**: all text-path `הסכם` resolution behavior (exact / new / ambiguous) delivered.

---

## Phase 8: User Story 8 — Won't provide email/phone → single closed ask (or proactive election), then store-anyway or don't-store (Priority: P3)

**Goal**: `add_client` needs full name + email + phone; if the operator declines email/phone,
DeniDin asks — **once**, with **no** re-ask for email/phone first — the **distinct closed
question**: store the event with the operator-stated name as free text +
`[לקוח לא אומת במורנינג]` in `description` (no Morning client created), **or** don't store it
(`declined` verdict → nothing persisted → one INFO `declined by operator` line). The operator
may also **proactively** elect store-anyway up front ("תרשום גם בלי אימייל וטלפון") — DeniDin
honours it directly with **no** "בטוח?" / "are you sure?" confirmation turn. Never a default;
store-anyway is never volunteered before the operator has declined the contact details or
proactively asked for it (FR-069-033/034/035).

**Independent test**: `user-stories.md` US8 Independent Test (all three variants).

- [ ] T021a [US8] Extend `tests/integration/test_ledger_client_resolution_routing.py` with the US8 branches — OpenAI stubbed to: decline email/phone → **one** closed store-anyway question (assert there is **no** re-ask for email/phone first, and store-anyway is offered on this single turn); **(a)** "store anyway" → the completing turn's recognition → `complete` with `event.client_name` = the operator-stated free text **and** `[לקוח לא אומת במורנינג]` inside `event.description`, **no** `add_client` call, exactly one file, all other provided fields present; **(b)** "don't store" → recognition → `declined` (carrying `source_type` + `client_name_stated`), **no** file, exactly one `[069] ledger capture declined by operator: … reason=declined_by_operator` INFO line; **(c)** operator instead supplies all three → normal `add_client` → capture, store-anyway never shown; **(d)** operator **proactively** asks to store without email/phone before being asked → DeniDin honours it directly with **no** "בטוח?" turn in the transcript → `complete` with the marker, exactly one file.
- [ ] T021b [US8] Any wiring for the store-anyway `description` marker path (expected: none — the recognition call writes the phrase per the T015 guidance, the ledgerer persists `description` verbatim). Wording delta for G8/G8a/G8b/G8c only if not already covered by T015 → **👤 approval**. **BLOCKED until T021a is RED.**
- [ ] T022 [US8] ✅ Self-verify checkpoint (no user gate): US8 branches behave as specified; `{data_root}/events/` gains **no** file on the don't-store branch, **exactly one** marked file on store-anyway (asked **or** proactive) — full billed proof is Phase 11 (T045).

**Checkpoint**: the operator-final-say escape hatch is in place; the `declined` verdict + its
breadcrumb work.

---

## Phase 9: User Stories 7 (incl. 7d) + 9 — Media (image) ledger path gains interactive resolution (Priority: P1 / P2) — C3

**Goal**: `MediaHandler`, on recognizing a `בנק` **or** `הסכם` ledger event off an **image**,
STOPS persisting directly and routes the extractor output + extracted text into the shared
conversational pipeline as a **synthetic turn** carrying a verbatim structured **stash**
(`build_ledger_stash_text`), so `resolve_client_name` / `add_client` /
`PendingApprovalManager` / multi-turn history + the **same post-turn recognition call** do
the work, and **every** extracted field (banking triplet for `בנק`; every fee component for
`הסכם`) survives the resolution detour (FR-069-045/046/047, FR-069-013/020/022). An **exact**
Morning match on the slip (US7d) captures the `בנק` event directly with **no** question and
**no** new client. **No new AI call is added to any extractor** — the extractor's existing
analysis is the routing signal only.

**Independent test**: `user-stories.md` US7 (7a/7b/7c/7d), US9 Independent Tests.

### Tests (Task A — RED, written and committed before any Task B; no approval gate)

- [ ] T023a [P] [US7] Write `tests/unit/test_ai_handler_media_ledger_routing.py` — `build_ledger_stash_text(extracted_text, analysis, source_type, source_medium)` (contract C3, `data-model.md §5`): the stash contains every non-null field of `analysis` as its own labelled `label: value` line and the **verbatim** `extracted_text` block (unmodified), and `לא זוהה` for every None; `source_type == "בנק"` → header `📸 התקבלה תמונה של אסמכתת העברה/הפקדה בנקאית.` + ordered fields `תת-סוג`,`סכום`,`מטבע`,`תאריך הפקדה`,`מספר בנק`,`מספר סניף`,`מספר חשבון`,`שם על האסמכתא`,`מספר אסמכתא` (banking triplet first); `source_type == "הסכם"` → agreement header (`📸 התקבלה תמונה של הסכם שכר טרחה.` for image) + ordered `תת-סוג`,`שם הלקוח בהסכם`,`תאריך ההסכם`, then **one line per fee component** (percent: `אחוז: <value> — <basis/description>`; fixed: `סכום קבוע: <value> <currency> — <description>`), then `מע"מ`,`שם המשלם`; `source_medium == "image"` → frame line `--- טקסט שחולץ מהתמונה (מילה במילה) ---`; `source_medium == "document"` → `--- טקסט שחולץ מהמסמך (מילה במילה) ---` + agreement header `📄 התקבל קובץ מסמך (DOCX) של הסכם שכר טרחה.`; multiple events → one labelled `אירוע N מתוך M` block each + a `מספר אירועים זוהו` note. OpenAI not involved (pure string builder).
- [ ] T024a [P] [US7] `tests/unit/test_media_handler.py` — a recognised `בנק`/`הסכם` **image** and a `docx` `document_type == "הסכם"` → `result["ledger_stash"]` / `["ledger_stash_source_type"]` are set, `add_ledger_events_from_call` is **not** called, the media turn's own `Message.ledger_event_ids` stays empty, `{data_root}/events/` gains no file; `ledger_events` empty → ordinary media turn (no stash); Step 11 `_store_media_turn` still runs. **Plus** `tests/unit/test_denidin_media_ledger_routing.py` (C1, added 2026-09-03) — `_process_media_message` rewrites the notification's `messageData` to a `textMessage` carrying the stash (keeping `senderData` / `timestamp` / `idMessage`) and calls `_process_conversational_message`; no-stash / `None` result → no synthetic turn. OpenAI mocked. (Built 2026-09-03.)
- [ ] T025a [P] [US7] Extend `tests/integration/test_ledger_client_resolution_routing.py` — a real `imageMessage` webhook JSON → `bot.router` → `WhatsAppHandler.handle_media_message` → `MediaHandler` (real extractor with the vision call mocked to a fixed OCR + classify dict) → OpenAI stubbed to emit an exact-match `resolve_client_name` reply, then a `complete` recognition verdict → **exactly one** `LedgerEvent` with the resolved name, linked from the completing `Message`, **no** `add_ledger_events_from_call` invocation. One `בנק` image case, one `הסכם` image case.
- [x] **Checkpoint (no approval gate)**: confirm T023a + T024a + T025a are written, RED, and committed before the Task B items.

### Implementation (Task B — BLOCKED until T023a / T024a / T025a are written and RED)

- [ ] T023b [US7] Implement `build_ledger_stash_text(extracted_text, analysis, source_type, source_medium)` in `src/handlers/ai_handler.py` (contract C3, `data-model.md §5`).
- [ ] T024b [US7] Rewire `src/handlers/media_handler.py` Step 10 — when `analysis_result["ledger_events"]` holds an event with `source_type` ∈ {`בנק`, `הסכם`} (image), **or** `media_type == "docx"` and `document_analysis["document_type"] == "הסכם"`, build the stash (`source_medium` = `"image"` / `"document"`) and return it on the result dict as `ledger_stash` / `ledger_stash_source_type` **instead of** calling `add_ledger_events_from_call`; on exception log + return no stash (the ordinary media summary path then runs). `whatsapp_handler.handle_media_message` returns that dict and suppresses the plain summary when `ledger_stash` is set; `denidin.py` (T025b) does the synthetic-turn routing. Step 11 `_store_media_turn` unchanged. (Built 2026-09-03.)
- [ ] T025b [US7] In `denidin.py` `_process_media_message`: capture the `handle_media_message` result; when `result["ledger_stash"]` is set, rewrite `notification.event["messageData"]` to a `textMessage` shape carrying the stash (keeping `senderData` + timestamp) and call `_process_conversational_message(notification)` — which already runs `_send_ai_response_and_attach(...)` **and** `_run_post_turn_ledger_recognition(...)` (Phase 2's T007b). No separate media routing helper, no synthetic `AIRequest` construction. The conversational path stays byte-for-byte identical (existing tests green). (Built 2026-09-03.)
- [ ] T026 [US7] Run `python3 -m pytest tests/unit/test_ai_handler_media_ledger_routing.py tests/unit/test_media_handler.py tests/integration/test_ledger_client_resolution_routing.py -v` + full `tests/unit` + `tests/integration` — all green.
- [ ] T027 [US7] ✅ Self-verify checkpoint (no user gate): the image `בנק` and `הסכם` paths route through resolution + the post-turn recognition call (US7 7a/7b/7c, plus the 7d silent exact-match path, and US9 behavior) — full vision proof is Phase 11's expensive suite.

**Checkpoint**: no image-sourced `בנק` / `הסכם` event persists without client resolution;
the stash carries the full payload across the detour; capture happens once, post-turn.

---

## Phase 10: User Story 10 — `docx` multi-component fee agreement, routed into the conversational pipeline (Priority: P2)

**Goal**: a `הסכם` `.docx` flows through the **same** Phase 9 routing + stash builder, only
`source_medium="document"`. `MediaHandler` uses `DOCXExtractor`'s **existing**
`document_analysis.document_type` as the routing signal — per `bugfix-028` a `docx` is always
`הסכם` or unknown, never `בנק`. **No `capture_ledger_events_from_text` call and no new OpenAI
call is added to `DOCXExtractor`** (spec Assumption 8). Recognition is the post-turn
text-only call (`config.ai_model`) → US10 acceptance is **`billed`**, not `expensive`.

**Independent test**: `user-stories.md` US10 Independent Test.

- [ ] T028a [US10] Extend `tests/integration/test_ledger_client_resolution_routing.py` with a `הסכם` `docx` case — a real `documentMessage` webhook JSON → router → `MediaHandler` → `DOCXExtractor` (real python-docx parse of a small `.docx`; the extractor's existing optional text analysis mocked so `document_analysis.document_type == "הסכם"`) → assert the synthetic turn is routed with `source_medium="document"`, `add_ledger_events_from_call` is **not** called, and after a mocked exact-match resolution + `complete` verdict exactly one `LedgerEvent` is persisted, linked from the completing `Message`. Extend `tests/unit/test_media_handler.py` (T024a) with the `docx` `document_type == "הסכם"` → routing case, `source_medium="document"`. **No** assertion about a new `DOCXExtractor` OpenAI call (there isn't one).
- [ ] T028b [US10] In `src/handlers/extractors/docx_extractor.py`: add the deterministic classmethod `_classify_document_type(text)` (keyword scan — no OpenAI call) and surface `document_analysis` (`{document_type, summary, key_points}`) from `analyze_media` (it previously returned none; `_analyze_document` hardcoded `"generic"` — there was no usable signal, contrary to C3b's "existing signal" wording). In `src/handlers/media_handler.py`: route on `media_type == "docx" and document_analysis["document_type"] == "הסכם"` (Phase 9's Step-10 branch), `source_medium="document"`. In `docx_extractor.py` + `src/handlers/extractors/base.py`: add a note that **ledger recognition is now post-turn (in `AIHandler.recognize_ledger_event`), for every medium** — the extractor does not run it. **No** `capture_ledger_events_from_text` call added. (Built 2026-09-03.) **BLOCKED until T028a is RED.**
- [ ] T029 [US10] Run the full `tests/unit` + `tests/integration` suites — all green.
- [ ] T030 [US10] ✅ Self-verify checkpoint (no user gate): a `.docx` fee agreement triggers the identical resolution detour as a photographed one, with `📄`/"מסמך" wording instead of `📸`/"תמונה" — full billed proof is Phase 11 (T046).

**Checkpoint**: all arrival paths for a `הסכם` / `בנק` ledger event (typed text, contact-card
text, image, `.docx`) go through mandatory client resolution and the one post-turn
recognition call.

---

## 🔎 `speckit.analyze` — cross-artifact consistency check (between Phase 10 and Phase 11)

- [ ] T030A Run `speckit.analyze` over `spec.md` + `user-stories.md` + `plan.md` + `research.md` + `data-model.md` + `contracts/` + `tasks.md`. Resolve any inconsistency **before** writing acceptance-test code. (Task id `T030A` is deliberately between Phase 10's T030 and Phase 11's T031 — it runs there.)

---

## Phase 11: Acceptance (billed + expensive) — the "TDD" pass (METHODOLOGY §VI)

**Purpose**: the real, end-to-end, user-perspective proof. Written **and** run **once,
together, after every Phase 2–10 unit/integration task is GREEN**. Scenarios are stated in
user-experience terms; exact `pytest` node ids are finalized when the code is written.

### Fixtures + ground-truth manifests (C9, `contracts/payload-fidelity-manifest.md`)

- [ ] T031 [P] Author the **detail-rich** typed `הסכם` fixtures + sibling `*.manifest.json` under `tests/fixtures/ledger_069/`: `agreement_new_client.txt` (US4 — and, via a `store_anyway` manifest variant handled inline in the test, US8) and `agreement_ambiguous.txt` (US5). Each carries **≥3 distinct fee components** (fixed retainer + success % + per-hearing fee at minimum), an explicit agreement date, `event_subtype`, and — for `agreement_new_client.txt` — a `payer_name` **distinct** from the client (e.g. a company paying on the client's behalf) with the manifest marking it `resolved: false` (the FR-069-017 free-text assertion). Manifest shape per C9: `source_kind`, `expected_event` (with `components: [{kind, value, description}]`), `client_resolution` (`scenario` ∈ `exact_match`/`one_partial_then_pick`/`two_plus_then_pick`/`zero_matches_then_new`/`store_anyway`, `morning_name_after_resolution`, `expects_marker_in_description`). `agreement_id` is **not** manifested.
- [ ] T032 [P] Author `agreement_doc_multi.docx` + `agreement_doc_multi.manifest.json` (US10 — `source_kind: "document"`, ≥3 components: fixed retainer + success % + per-hearing fee, agreement date in the body, a client name that has only a **near-match** in the sandbox roster) using a real `.docx` (commit a small python-docx build script alongside if helpful).
- [ ] T033 [P] Author `agreement_photo_multi.png` + `agreement_photo_multi.manifest.json` (US9 — photographed printed agreement, `source_kind: "image"`, same ≥3-component shape as `agreement_doc_multi`, same near-match client).
- [ ] T034 [P] Author the `בנק` deposit-slip images + manifests: `deposit_zero_matches.png` (US7a — payer name matches **nothing** in the roster), `deposit_one_partial.png` (US7b — one near-match), `deposit_two_plus.png` (US7c — two near-matches), `deposit_exact_match.png` (US7d — payer name is an **exact** match for an existing Morning client: no disambiguation question, no `add_client`, captured directly). Each slip shows amount + deposit date + **all three** banking numbers + a reference/confirmation number + a name; each manifest splits the banking triplet into separate fields (`bank_number` / `bank_branch` / `bank_account`).
- [ ] T035 Seed / document the Morning **sandbox** client roster the acceptance suite assumes: exact-match clients (US1/US6/US7d), an ambiguity pair (US5 5b), single near-matches (US5 5a, US7b, US9/US10), a two-near-match set (US7c), and the new clients US4/US7a/US8 will create. Cross-reference `tests/billed/GROUND_TRUTH_CLIENTS.md`; record the full roster in the new test modules' docstrings.

### Assertion helpers (C9 — test code for the billed/expensive tier, written here not earlier)

- [ ] T036 Write the shared helper module in `tests/billed/` (importable from `tests/expensive/`): `assert_event_matches_manifest(event, manifest)` — `PROVENANCE_IGNORE = {"event_id","event_datetime","captured_at","session_id","message_id","schema_version","reference_hint","agreement_id","component_id","_linked_document"}`; **forward** (every `expected_event` key present & equal on the persisted event, string-normalized — trim / collapse whitespace; a `null` in `expected` means the event's value must also be null/absent); **backward** (every populated non-`PROVENANCE_IGNORE` event key is in `expected_event` OR is `client_name` OR is `description` — any other populated field ⇒ **fail** "unexplained field"); `event["client_name"] == morning_name_after_resolution`; on `expects_marker_in_description` → `"[לקוח לא אומת במורנינג]" in event["description"]` AND `event["client_name"] == <operator-stated name>` (overrides the Morning-name check); else assert the marker phrase is **absent**; when the manifest carries a `payer_name` with `resolved: false`, assert it is persisted **verbatim** and `payer_name != client_name`. **No test asserts `schema_version`'s value.**
- [ ] T037 Write `assert_event_matches_manifest_two_hop(extractor_output, event, manifest)` in the same module — **Hop 1**: the extractor's `analyze_media()` output (`ledger_events[0]` for images / `document_analysis` + fields for `docx`, plus `extracted_text`) contains every field in the manifest (catches OCR/vision loss before the detour; for US9/US10 this is where "the model read all ≥3 fee components off the source" is proven); **Hop 2**: the persisted `event` matches Hop 1's extracted values (catches a field dropped *in the resolution detour or the recognition call*). Used by US7 (7a/7b/7c/7d) and US9 (images), and US10 (`docx`).
- [ ] T038 Extend `tests/e2e_helpers.py` as needed for the resolution detour: reuse `ClarificationAnswerBank` / `converse_until_ledger_events_captured` / `reserve_ledger_event_bucket_prefixes` (`A` / `B` prefixes); add a `live_morning_tunnel` fixture dependency helper the acceptance tests and the reworked pre-existing tests (T049) share; add answer-bank entries for the "full name + email + phone → approve" detour.

### `billed` acceptance — `tests/billed/test_e2e_ledger_post_turn_capture.py` (NEW)

Real OpenAI (text-only) + real Morning sandbox. Run via `scripts/run_multiple_billed_tests.sh`
(**sound off each result live**). Each scenario: a real webhook turn sequence; assert
operator-visible replies, file presence/absence, C6 breadcrumb lines, and — on every
event-creating scenario — `assert_event_matches_manifest` **exhaustively**.

- [ ] T039 [P] [US1] Describe + write `test_us1_mechanism_move` — decoupled exact-match `הסכם` capture: one turn, one `הסכם` event vs the exact Morning name, **no** second reply round-trip, `recognized` + `written` breadcrumbs, exhaustive manifest match.
- [ ] T040 [P] [US2] Describe + write `test_us2_morning_create_synchronous` — ask DeniDin to create a Morning invoice for an existing client → after it confirms creation, exactly one `חשבונית` event with the Morning display number + amount + `txn_date` + `event_subtype` equal to the **real `create_*` response** (assert against the captured response, not a fixture); Feature 025's next tick writes no second file for that display number.
- [ ] T041 [P] [US3] Describe + write `test_us3_regression_guard` — a `list_invoices` read-back turn **and** a "עבור ייעוץ" field-filling reply mid-`create_combo_document` approval → both replies delivered intact, **0** spurious `LedgerEvent` files.
- [ ] T041b [P] [US3] (operator request, 2026-09-03 — real bug seen in testing) Describe + write `test_us3_bare_email_no_capture` — a godfather sends **only an email address** (no fee arrangement, no deposit, no Morning doc), gets a normal reply → assert **0** `LedgerEvent` files **and** the post-turn recognition verdict is `none` (no `[069] ledger capture recognized` / `written` line) — neither *during* the reply (the inline path is gone) nor *after* it (the recognition call must classify a bare contact detail as `none`). Same shape for a bare phone number / bare client name as inline sub-assertions if cheap. Guards T008c.
- [ ] T042 [P] [US4] Describe + write `test_us4_new_client_agreement` — FLAGSHIP: new client, DeniDin asks full name + email + phone → `add_client` approve → exactly one `הסכם` event, exhaustive manifest match **including the FR-069-017 `payer_name` free-text assertion** and `event_datetime` == the original agreement message's timestamp; "לא" to the approval → **no** client, **no** file.
- [ ] T043 [P] [US5] Describe + write `test_us5_ambiguous_agreement` — 5a (1 near-match → names it + create-new; pick it → event vs manifest), 5b (2+ → list all + create-new; drive to "new" → event), scenario 5 (bare "כן" → one re-ask closed choice → 2nd ambiguous → abandonment, **no** file), G15 (later correction reuses the resolved name, no 2nd resolution round).
- [ ] T044 [P] [US6] Describe + write `test_us6_exact_match_silent` — exact-match client → **zero** client-identity question, normal reply unchanged, one `הסכם` event; manifest match. (Inline text + inline expected dict, single hop.)
- [ ] T045 [P] [US8] Describe + write `test_us8_store_anyway_and_dont_store` — decline email/phone → **one** closed store-anyway question, **no** re-ask for email/phone first (assert store-anyway **not** mentioned before the single decline); "store anyway" → exactly one event, `client_name` == the operator-stated free text, `[לקוח לא אומת במורנינג]` in `description`, **no** Morning client, all other fields per the `store_anyway` manifest variant; "don't store" → **no** file + one INFO `[069] ledger capture declined by operator … reason=declined_by_operator` line; **proactive-election variant** — operator says "תרשום גם בלי אימייל וטלפון" up front → honoured directly, exactly one event, **no** "בטוח?" / "are you sure?" turn anywhere in the transcript; supply all three instead → normal `add_client` → capture, store-anyway never shown.
- [ ] T046 [P] [US10] Describe + write `test_us10_docx_multi_component_agreement` — `.docx` for a client Morning has only a **near-match** for → candidate + create-new offered, **no** file; "לקוח חדש" → full name + email + phone → approve → exactly one `הסכם` event, **two-hop** assertion (`DOCXExtractor` output vs `agreement_doc_multi.manifest.json`, then persisted event vs extractor output — **every** fee component both hops); pick the near-match instead → event against the existing client, same full payload. (`billed` — recognition is text-only.)
- [ ] T047 Run T039–T046 via `scripts/run_multiple_billed_tests.sh <node_id> …` (stop-on-first-failure; **every** failure is its own stop → full report + fresh user input before any fix / re-run / continue). **Sound off each `[N/TOTAL] PASSED/FAILED` live.** Read `logs/test_logs/pytest_results/*.txt` for full output.

### `expensive` acceptance — `tests/expensive/test_e2e_media_client_resolution.py` (NEW)

Real **vision** OpenAI + real Morning sandbox. **Each test needs its own fresh explicit user
approval before every run**, one at a time, read `logs/test_logs/` first, never re-run after
it reached OpenAI without fresh approval. `scripts/run_single_test.sh` only.

- [ ] T048a [P] [US7] Describe + write `test_us7_deposit_image_7a_zero_matches` — FLAGSHIP: `deposit_zero_matches.png` (a payer name, amount, deposit date, bank/branch/account, reference) → "no client X, give full name + email + phone" → email → phone → `add_client` approve → exactly one `בנק` event; **two-hop** (extractor output vs `deposit_zero_matches.manifest.json` full banking triplet, then persisted event vs extractor output); `client_name` == the created Morning name, **never** the raw OCR string.
- [ ] T048b [P] [US7] Describe + write `test_us7_deposit_image_7b_one_partial` — as 7a but Morning has one near-match → DeniDin names that candidate + offers create-new; drive to "new" → event, two-hop; **and** pick the candidate instead → event against it, same full banking payload, **no** new client.
- [ ] T048c [P] [US7] Describe + write `test_us7_deposit_image_7c_two_plus` — Morning has two near-matches → both listed + create-new; drive to "new" → event, two-hop.
- [ ] T049a [P] [US7] Describe + write `test_us7_deposit_image_7d_exact_match` — `deposit_exact_match.png` (payer name is an **exact** match for an existing Morning client) → **no** disambiguation question, **no** `add_client` in the transcript → exactly one `בנק` event captured directly against that existing client; **two-hop** (extractor output vs `deposit_exact_match.manifest.json` full banking triplet, then persisted event vs extractor output); `client_name` == the exact Morning name.
- [ ] T049b [P] [US9] Describe + write `test_us9_photographed_multi_component_agreement` — `agreement_photo_multi.png` for a client Morning has only a near-match for → candidate + create-new; "לקוח חדש" → full name + email + phone → approve → exactly one `הסכם` event; **two-hop**, **every** fee component asserted both hops; pick the near-match instead → event against the existing client, same payload; decline email/phone → the US8 single closed choice (no re-ask), unchanged.
- [ ] T050 Request approval and run `test_us7_deposit_image_7a_zero_matches` (`scripts/run_single_test.sh <node_id>`). Report the result from `logs/test_logs/pytest_results/*.txt`. **STOP** — do not run any other expensive test without fresh per-test approval.
- [ ] T051 (after approval, **one at a time**, each its own STOP-on-failure report) Run `test_us7_deposit_image_7b_one_partial`, then `_7c_two_plus`, then `test_us7_deposit_image_7d_exact_match`, then `test_us9_photographed_multi_component_agreement`.

### Rework the pre-existing billed/expensive ledger-capture tests (operator-approved 2026-09-01)

- [ ] T052 Rework the ~16 pre-existing `billed`/`expensive` ledger-**capture** tests to the mandatory-client-resolution world (the mechanism move is transparent — they assert on disk outcomes; the mandatory-client rule is the deliberate behavior change): `tests/billed/test_ledger_event_capture_billed.py`, `tests/billed/test_ledger_event_capture_text_billed.py`, `tests/expensive/test_ledger_event_capture_e2e.py`, and the Group B reference-approval tests that now silently gain events. Each needs (1) the `live_morning_tunnel` fixture dependency (T038) and (2) **either** a seeded exact-match Morning client (cheapest — the silent path) **or** a scripted multi-turn resolution detour (`converse_until_ledger_events_captured` + `ClarificationAnswerBank`). **Category A is untouched** — `tests/billed/test_ledger_query_billed.py` (query) and `tests/billed/test_accounting_reconciliation_billed.py` (reconciliation sweep) legitimately make real OpenAI calls and don't exercise the 069 capture path; only `test_morning_question_answers_and_creates_no_ledger_event` there gains a dependency on the recognition call classifying a read-only Morning question as `none` (adjust its assertion if needed, no rewrite). **No test asserts `schema_version`'s value** — if a reworked test still does, remove that assertion (CLAUDE.md).
- [ ] T053 Re-run the reworked billed tests via `scripts/run_multiple_billed_tests.sh` (sound off each result live); request approval and re-run each reworked expensive test one at a time (STOP-on-failure each).

**Checkpoint**: full billed + expensive acceptance green, pre-existing suite reworked and
green → the feature is functionally done.

---

## Phase 12: Polish & Cross-Cutting

- [ ] T054 [P] Update `.github/ARCHITECTURE.md` and the `apps/denidin-app` section of `CLAUDE.md` (Feature 069 paragraph): ledger capture is now a **post-turn recognition call** + a zero-AI **ledgerer**; `capture_ledger_event` / `LEDGER_EVENT_TOOL` / `_call_openai_ledger_followup_api` / the bugfix-018 suppression guard / the protocol-violation machinery are **removed from the main turn**; `query_ledger_events` (read-only) kept; three `[069]` lifecycle breadcrumb lines; the media `בנק` / `הסכם` path (image **and** `.docx`) routes through the conversational pipeline as a synthetic turn; `pdf` → Feature 071; durable client-name cache → Feature 072; **no** schema change, **no** config key, **no** feature flag.
- [ ] T055 [P] Run `python3 -m pylint src/ --fail-under=7.0 --rcfile=.pylintrc` and `python3 -m mypy src/ --config-file=mypy.ini` — no new violations. (Net line count expected **negative** — deletions exceed additions.)
- [ ] T056 [P] Constitution-boundary review (FR-069-010, METHODOLOGY §XXI — manual, not an automated test): on the merged `config/runtime_constitution.md`, confirm the "אימות לקוח לפני רישום אירוע" subsection states when the gate applies, when it does **not** (`חשבונית` by construction, `payer_name`), and that ambiguity → ask; confirm "Resolving a client by name" ↔ the ledger subsection cross-reference **each other**; confirm "Reminder Management" and "Invoice Management" each carry the out-of-scope note; confirm **all** old inline-`capture_ledger_event` guidance is gone. Record the outcome in the PR description.
- [ ] T057 Walk `quickstart.md` end to end against `dev` (**only** after a separate explicit human deploy decision — not part of this task) — the 9 smoke-test steps, incl. step 7 (photo `הסכם`) and step 8 (`.docx` `הסכם` → "מסמך" wording).
- [ ] T058 Move `specs/in-progress/069-mandatory-client-resolution-before-ledger-event/` → `specs/done/069-mandatory-client-resolution-before-ledger-event/` (flat — `cut_release.sh` later sweeps it into a version folder) and fill the spec `Status` line — **only as part of the `haleluya` flow, which is NEVER run without explicit user instruction.**

---

## Dependencies & Execution Order

- **Phase 1 (Setup)** → no dependencies.
- **Phase 2 (Enabler)** → after Setup. **BLOCKS Phases 3–11.** T003a–T007a in parallel (RED); commit; then T003b–T007b (T003b/T004b parallel; T005b after T005a+T006a; T007b after T007a).
- **Phase 3 (US1)**, **Phase 4 (US3)** → after Phase 2; assertion-only, no new production code expected. Parallelizable with each other.
- **Phase 5 (US2)** → after Phase 2; the `חשבונית` verdict path (C8).
- **Phase 6 (US4)** → after Phase 2. **T015 (constitution draft + 👤 approval) blocks T017b and is a soft prerequisite for every later phase's model behavior.**
- **Phase 7 (US5)**, **Phase 8 (US8)** → after Phase 6 (share the T015/T017b guidance; no new code expected). Parallelizable with each other.
- **Phase 9 (US7 incl. 7d / US9)** → after Phase 2; the guidance (T015) must exist for its acceptance behavior. Largest code surface. T023a‖T024a‖T025a, then Task B.
- **Phase 10 (US10)** → after Phase 9 (reuses Step 10 routing + stash builder unchanged, only `source_medium="document"`).
- **T030A `speckit.analyze`** → after Phase 10, before Phase 11.
- **Phase 11 (Acceptance)** → after **all** of Phases 2–10 are GREEN. Fixtures (T031–T034) parallel. Helpers (T036–T038) before the billed/expensive tests. Billed (T039–T047) before expensive (T048a–T051). Pre-existing rework (T052–T053) after the new suite is written. **Every `expensive` run: its own approval + STOP-on-failure.**
- **Phase 12 (Polish)** → after Phase 11. T058 **only** under `haleluya`.

### TDD gate per phase

Every `T###a` (tests) is written **RED and committed before** its `T###b` (impl) and is
**immutable once committed**. Per the 2026-09-01 operator direction there is **no approval
gate** between Task A and Task B for the unit/integration tier. Approval is still required
for: constitution / operator-facing **wording** (T015, and any T0XXb delta — §XIX HARD STOP)
and **every `expensive` run** (T050, T051, T053 — one per test, every time). `billed` runs
freely. Billed/expensive scenarios are **described** here and coded **once**, in Phase 11.

---

## Parallel Opportunities

- T003a ∥ T004a ∥ T005a ∥ T006a ∥ T007a (Phase 2 tests, different files).
- T003b ∥ T004b (Phase 2 impl, different areas of `ai_handler.py` — coordinate on the same file).
- Phase 3 (US1) ∥ Phase 4 (US3) once Phase 2 lands.
- Phase 7 (US5) ∥ Phase 8 (US8) once Phase 6 lands.
- T023a ∥ T024a ∥ T025a (Phase 9 tests).
- T031 ∥ T032 ∥ T033 ∥ T034 (Phase 11 fixtures).
- T039 ∥ T040 ∥ … ∥ T046 (billed test **authoring** — the run, T047, is sequential).
- T048a ∥ … ∥ T049b (expensive test **authoring** — runs are strictly one-at-a-time with per-run approval).

---

## Implementation Strategy

### MVP (highest-value slice)

Phase 1 → Phase 2 (enabler) → **Phase 3 (US1)** → **Phase 6 (US4)** → **Phase 9 (US7
flagship)**. That delivers: the decoupled mechanism, new-client `הסכם` text, and the single
most likely real path (bank-deposit image → resolve → capture with full banking detail).
US7's 7a/7b/7c are the non-negotiable core if the acceptance suite must be trimmed for cost
(`user-stories.md` closing note).

### Incremental delivery

Each phase is an independently demoable increment: decoupled capture (US1) → regression guard
(US3) → Morning create synchronous (US2) → new-client text (US4) → ambiguous text (US5) →
operator-final-say (US8) → image path (US7 incl. 7d / US9) → `docx` path (US10) → full
acceptance proof.

### Not in this feature

`pdf` fee-agreement extraction routing — **Feature 071**
(`specs/backlog/071-pdf-single-call-extraction/`); a durable cross-conversation Morning
client-name cache — **Feature 072** (`specs/backlog/072-morning-client-name-cache/`); the
retroactive August `בנק` client-name backfill — **Feature 065** (069 is forward-only); a
code-side financial-content pre-filter to skip the recognition call — explicitly out of scope
(spec §Out of Scope).

---

## Notes

- **No feature flag, no config key** — deliberate 2026-08-31 user direction (plan.md
  Complexity Tracking). Every path is live on deploy; the acceptance gate is the full
  real-API suite; `merge ≠ redeploy` is the only safety valve and deploy stays a separate
  explicit human step.
- **Constitution wording is UX-impacting** — T015 (and any T016b/T019b/T021b delta) is
  drafted and **👤 user-approved before** the apply task (T017b), and ships in the **same PR**
  as the code (METHODOLOGY §XIX HARD STOP, `haleluya`).
- **Unit/integration test approval waived** (operator direction, 2026-09-01) — Task A is
  still RED-first and immutable-once-committed, but there is **no** Task A → Task B human
  approval gate for the unit/integration tier. The `expensive` per-run approval and the
  constitution-wording (§XIX) gates are **unaffected**. Recorded as a Feature 069 deviation
  in `plan.md` Complexity Tracking.
- **`event_datetime` hard pointer** — always the trigger message's Green API notification
  timestamp (via `verdict["trigger_message_id"]` looked up in the session), never
  `now_local()` / the recognition-call clock. `Message.ledger_event_ids` back-links from the
  **completing** message, not the trigger.
- **`schema_version`** — stays 2, no field added, **no test asserts its value** anywhere.
- **`billed`** tests: run freely, no per-run approval, sound off each result live, never pipe
  through `tail`/`grep`/`head`. **`expensive`** tests: fresh explicit approval every run, one
  at a time, read `logs/test_logs/` first, **STOP at every failure** for a full report +
  fresh user input.
- Commit after each task or logical `a`/`b` pair; feature branch only, never `master`.
