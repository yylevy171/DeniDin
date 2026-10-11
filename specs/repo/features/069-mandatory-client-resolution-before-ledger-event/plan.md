# Implementation Plan: Post-Turn Ledger Capture with Mandatory Client Resolution

**Branch**: `feature/069-mandatory-client-resolution-before-ledger-event` | **Date**: 2026-09-01
**Spec**: [spec.md](./spec.md) | **Stories**: [user-stories.md](./user-stories.md) | **Phase 0**: [research.md](./research.md)

**Compliance**: CONSTITUTION.md §I (no env vars), §V (real E2E integration tests, no mocking
of internal components), §XVII (no monkey-patching), §XVIII (no silent degraded write on a
failed external handshake). METHODOLOGY.md §II (template), §IV (phased), §VI
(TDD-as-acceptance), §VI.b (unit/integration RED-first + immutable — Task A→B approval gate
Feature-069-waived, see Complexity Tracking), §VII (Integration Contracts — mandatory here,
multi-component), §XIX (UX-impacting → approval), §XXI (tool-boundary constitution rules).
Ledger `CURRENT_SCHEMA_VERSION` is **not** bumped (stays 2) — CLAUDE.md "LEDGER SCHEMA
VERSION BUMPS ARE HUMAN-ONLY".

> **DESIGN-THREAD ADDENDUM (2026-09-03, decisions 1–12 — see tasks.md for the full table).**
> After this plan was written, an extended design thread refined the recognition mechanism:
> a **1-hour context window** with a new config key `ledger_recognition_context_window_hours`
> (the feature's only config key — supersedes "no config keys" in Complexity Tracking);
> **completing-message dating** for `הסכם`/`בנק` (not the economic-content message);
> `Message.mcp_calls` **persisted**; the recognition call **attaches `query_ledger_events`**
> and always pulls the client's ledger history once up front (bounded loop, cap 3);
> **content-fingerprint dedup** + a **completeness re-check (persist-flagged-incomplete)** in
> the ledgerer; and the recognition prompt moved to its **own file**
> `config/ledger_recognition_prompt.md` (`_load_recognition_prompt()`), leaving the
> constitution with only the conversational side. All of this landed in the Phase 2–8 code on
> 2026-09-03 (full unit+integration suite green).

---

## Summary

Two intertwined changes plus one scope extension (spec §Overview):

### 1. Mechanism move — inline tool → post-turn recognition step

**Today**: every godfather/admin text turn is handed a `capture_ledger_event` local tool
(`LEDGER_EVENT_TOOL`, via `_assemble_tools` → `_build_ledger_event_tool`). The model emits a
`function_call`; `_handle_ledger_event_capture` (`ai_handler.py:~2114`) runs a bugfix-018
MCP-suppression check and a `>1 call` / unparseable-args protocol-violation check, persists
via `add_ledger_events_from_call`, and then makes a **second** OpenAI round-trip
(`_call_openai_ledger_followup_api`, `ai_handler.py:~3199`) just to recover the operator's
real reply.

**After**: all of that is deleted. Ledger capture runs **once, after the operator reply is
finalized and sent**, as:

- **The recognition call** — one dedicated **text-only** OpenAI call per godfather/admin
  turn (the `capture_ledger_events_from_text` pattern, `ai_handler.py:~3321`, generalized
  from "OCR'd media text" to "the whole turn context"). Input: the conversation so far + the
  reply just sent + **this turn's Morning MCP tool calls and their results verbatim** + the
  constitution's ledger section. It uses `LEDGER_EVENT_TOOL`'s **schema** (for the shape of a
  mapped event) but is **not** a tool the conversational model elects. Output is **never**
  shown to the operator; **no** follow-up round-trip. It returns a **tri-state verdict**:
  - **`complete`** — a complete ledger event finished *this round*; payload returned already
    mapped to the `LedgerEvent` schema (normalized amounts, ISO dates, fee components split
    into the `components` array, `source_type` / `event_subtype`, the exact resolved
    `client_name`, `reference` / `reference_hint` if established via `query_ledger_events`),
    plus the **`trigger_message_id`** — the session message that first introduced the event's
    core economic content.
  - **`none`** — no complete event this round. Nothing persisted, no log line (DEBUG only).
  - **`declined`** — the operator was offered store-anyway and explicitly refused; carries
    `source_type`, the operator-stated name, and `reason`.
- **The ledgerer** — mechanical, **zero-AI** consumer of the verdict. On `complete`: mints
  `event_id` / `captured_at` (+ `agreement_id` / `component_id` where applicable), resolves
  `event_datetime` from the session by looking up `trigger_message_id`'s Green API
  notification timestamp (**the "hard pointer" — never `now_local()`, never the
  recognition-call clock**), dedups, persists the immutable JSON via the existing
  `add_ledger_events_from_call` path, appends to the in-memory index, updates
  `Message.ledger_event_ids` on the **completing** message, and emits the INFO
  "recognized" + "written" breadcrumbs. On `declined`: emits the INFO "declined by operator"
  breadcrumb, persists nothing. It never resolves a client, calls Morning, or queries the
  ledger. (It **may** denormalize an already-decided `reference` id into `_linked_document`
  display fields from its own in-memory index — that is formatting of a linkage the
  *conversation* decided, not resolution; see research.md R3.)

**Deleted**: `_call_openai_ledger_followup_api`; the bugfix-018 MCP-suppression guard
(`morning_mcp_used_this_turn`); the `protocol_violation = len(ledger_calls) > 1` /
`single_call_unparseable` whole-turn rejection machinery; `LEDGER_EVENT_TOOL` /
`capture_ledger_event` attachment to the main conversational turn.
**Kept on the main turn**: `query_ledger_events` (read/search only — FR-069-008).

The two incidents the suppression guard existed for (2026-07-28 spurious capture from
reading `list_invoices` output back; 2026-08-02 field-filling reply misclassified
mid-`create_combo_document` approval) become **structurally impossible** — there is no inline
`capture_ledger_event` on the main turn to misfire, and the reply is produced independently
of recognition. US3 is the proof.

### 2. Mandatory client resolution — an event is not "complete" until its client resolves

Per-type **mandatory fields** (spec §Clarifications 2026-09-01, operator-locked) must all be
present before the recognition call may return `complete`:

| type | mandatory (must be present) | conditional | generated by the ledgerer |
|---|---|---|---|
| `הסכם` | resolved `client_name` (or store-anyway); event date; `description`; ≥1 fee component **OR** a number of hours | per component: `amount` > 0 **OR** `percent` | `event_id`, `event_datetime`, `captured_at`, `agreement_id`, `component_id` |
| `בנק` | resolved `client_name` (or store-anyway); `txn_date`; `amount`; `description`; `vat_status` (`כולל` unless operator states otherwise — code-enforced `ledger_event_manager.py:1052`) | — | `event_id`, `event_datetime`, `captured_at` |
| `חשבונית` (in-conversation create) | `client_name` (resolved by construction); `txn_date`; `event_subtype` (= document type — **no `accounting_document_type` field**, verified `ledger_event_manager.py:1084`); `amount`; `accounting_document_display_number` — all from the real Morning response | — | `event_id`, `event_datetime`, `captured_at` |

**Retain-if-provided** (must survive the whole conversation and reach the record): everything
else that maps to a `LedgerEvent` field **except** the mandatory / conditional ones and
**except** `agreement_id` — notably `payer_name` (`הסכם`-only), per-component
`trigger_condition` / `percent` / `percent_base` / `hours` / `hourly_rate`, `bank_number` /
`bank_branch` / `bank_account` (`בנק`), `accounting_document_status` / `_status_code` /
`_status_label` / `_payment_method` (`חשבונית`), and `reference` / `reference_hint` (all
types).

Client resolution is **ordinary conversation** driven by `runtime_constitution.md` guidance,
using the existing "Resolving a client by name" flow (exact match → silent; 1 candidate →
name it + offer create-new; 2+ → list + offer create-new; no match → full name + email +
phone → `add_client` approval). It is **never** a code state machine and **never** anything
the recognition call or the ledgerer does. An unresolved client ⇒ event not complete ⇒
recognition call returns `none` ⇒ conversation continues. One `resolve_client_name` call per
recognized event, conversation-scoped cache only (Feature 072 is the durable cache).

**Store-anyway** (the only sanctioned unresolved write): operator declines a new client's
email + phone → a **single** distinct closed "store without full client details, or not?"
question (no re-ask for email/phone first) → *store* → persisted with the operator-stated
free-text `client_name` + a fixed `[לקוח לא אומת במורנינג]` marker inside `description` (no
new field, no schema bump, no Morning client created); *don't store* → `declined` verdict,
nothing persisted, one INFO line. The operator may also **proactively** elect store-anyway up
front, which DeniDin honours directly with no "are you sure" confirmation turn.

### 3. Morning "creates" in scope

A `create_*` Morning MCP call that succeeds in a conversation is a complete `חשבונית` event
(client resolved by construction). The recognition call — whose input includes the `create_*`
call **and its result** — recognizes it **synchronously that turn**, reading the real Morning
response. It persists through the same `add_ledger_events_from_call` →
`_ensure_accounting_document_cache()` path, so the `accounting_document_display_number` lands
in Feature 025's in-memory tri-state dedup cache (`ledger_event_manager.py:1163-1169`) and
025's next sweep tick skips it. Feature 025's sweep stays required and unchanged for
documents created **outside** a conversation. 069's `חשבונית` capture has no config gate and
no backfill dependency (forward-only, conversation-sourced).

### Cross-cutting

- **No `LedgerEvent` schema change, no `CURRENT_SCHEMA_VERSION` bump** (human decision
  2026-08-31 — stays 2). The store-anyway marker is text in the existing `description`.
- **No feature flag, no new config key** (explicit user direction 2026-08-31) — the feature
  ships unconditionally. Recorded in Complexity Tracking.
- **Observability is pure logging** — three INFO breadcrumb lines emitted by the ledgerer
  ("recognized" / "written" / "declined by operator"). No tracker, no sweep, no config, no
  new module.
- **Media path** — `MediaHandler` stops persisting recognized captures directly; it routes
  the extractor output + extracted text into the conversational `AIHandler` pipeline as a
  synthetic turn (Feature 030 contact-card pattern) with a transient verbatim "stash", and
  the same post-turn recognition call runs. Covers `בנק` slips, photographed `הסכם`, and
  `docx` `הסכם`. **No** new recognition call is added to `DOCXExtractor` — recognition
  happens once, post-turn, for every medium (spec Assumption 8). `pdf` is Feature 071.

---

## Technical Context

**Language/Version**: Python 3.11 (`apps/denidin-app`)
**Primary Dependencies**: OpenAI Responses API (`openai`), Green API bot library, FastMCP
(remote, via ngrok tunnel — not imported), `pytest`. **No new libraries.**
**Storage**: existing — one immutable JSON file per event under `{data_root}/events/`
(`LedgerEventManager`); ChromaDB / session JSON unchanged. **No new persisted or in-memory
state.** The recognition-call output and the media-ledger stash are both transient (spec
§Key Entities). No feature flag, no new config key (2026-08-31).
**Testing**: `pytest`; unit (`tests/unit/`), integration (`tests/integration/`, real Green
API webhook JSON → router), acceptance (`tests/billed/` text-only real OpenAI + real Morning
sandbox; `tests/expensive/` vision). `scripts/run_single_test.sh` /
`scripts/run_multiple_billed_tests.sh`.
**Target Platform**: Linux container (dev/prod), macOS host for tests.
**Project Type**: single app (`apps/denidin-app`) + sibling `apps/morning-mcp-app` reached
only over HTTP. **No `morning-mcp-app` change** — `resolve_client_name` / `add_client` /
`create_*` already exist there.
**Performance Goals**: each godfather/admin turn now makes **one** text-only recognition call
after the reply (replacing today's inline `capture_ledger_event` function-call turn **and**
its `_call_openai_ledger_followup_api` second round-trip — net **fewer** OpenAI calls on a
capturing turn, one extra cheap text-only call on a non-capturing turn). The deposit media
path swaps one internal classify call for one `get_response` round-trip (comparable). A
code-side pre-filter to skip the recognition call on turns with no financial content is a
possible later optimization, explicitly out of scope (spec §Out of Scope).
**Constraints**: FR-069-006 / SC-009 (reply always produced, fully decoupled — a forced
recognition-call failure changes 0 bytes of the reply); FR-069-004 (ledgerer makes no
OpenAI call, no client/Morning/ledger lookup); CONSTITUTION §XVIII (tunnel down during
resolution → tell the operator, capture nothing).
**Scale/Scope**: single-operator-per-chat; a handful of `הסכם` / `בנק` / `חשבונית` events
per day.

**NEEDS CLARIFICATION**: none. All spec deferrals resolved in research.md. The design
decisions this plan locks (below) were all derivable from operator-locked FRs; none needs a
fresh operator decision, **except** the `runtime_constitution.md` wording (FR-069-041 /
METHODOLOGY §XIX — HARD STOP, drafted + approved in `speckit.implement`).

### Design decisions locked by this plan (derived from operator-locked FRs)

1. **Recognition-call verdict is tri-state** — `complete` / `none` / `declined`. The only
   shape consistent with FR-069-003 (complete → mapped event), FR-069-035 (three distinct
   log outcomes), and FR-069-008 (no inline ledger tool → the "declined by operator" signal
   cannot come from a `record_unresolved_ledger_capture` function tool; it must come from the
   recognition call). **There is no inline `record_unresolved_ledger_capture` tool.**
2. **`event_datetime` "hard pointer"** — the recognition call returns `trigger_message_id`
   (the session message that first introduced the event's core economic content); the
   ledgerer looks that message up in the session and uses its Green API notification
   timestamp for `event_datetime`. Never `now_local()`, never the recognition-call time,
   even after a multi-turn detour. This is what every hardcoded acceptance-test expectation
   (`event_datetime == local_from_timestamp(expected_event_timestamp).strftime("%d/%m/%Y %H:%M")`)
   depends on.
3. **`Message.ledger_event_ids` back-link** — the ledgerer appends the new `event_id` to the
   **completing** message's `ledger_event_ids` (the turn on which the event became complete),
   not the trigger message. (The trigger message is only the `event_datetime` source.)
4. **`event_id` prefix map unchanged** — `A` = `הסכם`, `B` = `בנק`; `event_id` format =
   source-type letter + `DDMMYY` + `HHMM` + a same-minute sequence digit. The ledgerer still
   mints it (from `event_datetime` + a same-minute counter), exactly as
   `add_ledger_events_from_call` does today.
5. **`_linked_document` denormalization stays in the ledgerer** — `ledger_event_manager.py`
   ~1060-1077 resolves an already-supplied `reference` id into `_linked_document` display
   fields from the in-memory index. This is denormalization of a linkage the *conversation*
   established (FR-069-021), not "resolution", so it does not violate FR-069-004's "MUST NOT
   query the ledger" (which targets *deciding* a linkage). It runs unchanged.
6. **Media routing classification signal** — `MediaHandler` decides "ledger-relevant, route
   into the pipeline" from the extractor's **existing** document analysis: `ImageExtractor`'s
   vision classification `source_type` (`בנק` / `הסכם`) for images; `DOCXExtractor`'s
   `document_analysis.document_type` for `docx` (always `הסכם` or unknown per `bugfix-028`).
   **No new AI call is added to any extractor.** A non-ledger classification leaves the
   existing media-summary path untouched.
7. **The recognition call fires for the media synthetic turn exactly as for a typed turn** —
   there is one post-turn recognition hook, in the shared conversational path, not a
   media-specific one.

---

## Constitution Check

*GATE: must pass before Phase 0 (passed — research.md written) and re-checked after Phase 1
design (see end of this section).*

| Gate | Verdict | Note |
|---|---|---|
| **No environment variables** (CONSTITUTION §I) | ✅ PASS | This feature adds **no** config keys at all. |
| **Israel-local timestamps** (`now_local()`) | ✅ PASS | Every INFO breadcrumb (`recognized` / `written` / `declined`) carries a `now_local()` `time=` field. `event_datetime` is the **triggering message's Green API timestamp** (via `local_from_timestamp`), never `now_local()` — a deliberate, tested constraint (design decision 2). `captured_at` = `now_local()`. |
| **Git workflow** (feature branch + merge commit) | ✅ PASS | `feature/069-...` already the branch. |
| **No monkey-patching** (§XVII) | ✅ PASS | New `AIHandler` method for the recognition call; new ledgerer path in `LedgerEventManager` / a thin `denidin.py` hook; breadcrumbs are plain `logger.info(...)`. Removing the inline tool + follow-up API is deletion, not patching. |
| **`pathlib.Path`** | ✅ PASS | No new path string-building; fixtures use `Path`. |
| **Feature flag, default false, byte-identical when off** (METHODOLOGY) | ⚠️ **DEVIATION** — see Complexity Tracking | Explicit user direction 2026-08-31: "no need for feature flag". Ships unconditionally; no toggle, no byte-identical-when-off path. Safeguards: merge ≠ redeploy; full billed/expensive acceptance suite green before done; `speckit.tasks` sequences delivery. |
| **ZERO MOCKING of internal components** (§V) | ✅ PASS | Acceptance tests: real webhook JSON → real router/handlers/managers → real OpenAI + real Morning sandbox. Only OpenAI + Green API mocked, and only in unit tests. |
| **Integration tests never set feature flags** (§V) | ✅ PASS (n/a) | No flag exists; integration/acceptance tests set nothing, run against `config.test.json`. |
| **Tests immutable once approved** (§VI.b) | ⚠️ **DEVIATION** — see Complexity Tracking | Operator direction 2026-09-01: *"unit and integration tests I don't need to approve."* Unit/integration Task A stays RED-first and **immutable once committed**; the §VI.b Task A→B human-approval gate is waived **for that tier only**. Retained: constitution / operator-facing wording §XIX approval, and every `expensive` acceptance run's own approval. Billed/expensive acceptance tests still written + run once, together, after all unit/integration green (§VI). |
| **New tool-bearing feature ⇒ explicit constitution boundaries + bidirectional xrefs** (§XXI) | ✅ PASS (planned) | FR-069-041: the rewritten "Ledger Event Recognition" section states when the gate applies / does not / ambiguity→ask, bidirectional xref with "Resolving a client by name", out-of-scope notes in "Reminder Management" / "Invoice Management". Note this feature **removes** a tool (`capture_ledger_event`) from the main turn and keeps one (`query_ledger_events`, read-only) — the boundary work is mostly deletion of old inline-tool guidance. Drafted & approved in `speckit.implement`. |
| **Ledger `CURRENT_SCHEMA_VERSION` human-only** (CLAUDE.md) | ✅ PASS | Human decided **not** to bump; no `LedgerEvent` field added; no test asserts `schema_version`. |
| **UX-impacting change ⇒ approval before implementing** (§XIX) | ✅ PASS (planned) | Constitution wording + any new operator-facing strings approved by the user during `speckit.implement`. FR-069-041 is a HARD STOP. |
| **No silent degraded write on failed external handshake** (§XVIII) | ✅ PASS | Tunnel down during resolution → operator told "couldn't verify the client, try again"; the event never completes; **zero** events persisted; consistent with existing MCP-unavailable behavior. |
| **Retry policy** (retry once on 5xx/timeout, never 4xx) | ✅ PASS | The recognition call reuses `capture_ledger_events_from_text`'s existing retry shape (one-shot retry on `is_incomplete_capture`). `resolve_client_name` / `add_client` / `get_response` retry behavior unchanged. |

**Post-Phase-1 re-check**: the design in `data-model.md` + `contracts/` adds **no** new
persisted schema, **no** new config key, **no** in-memory state, **one** new `AIHandler`
method (the recognition call), **one** ledgerer path (mostly reusing
`add_ledger_events_from_call`), three INFO-log-line formats, and **deletes** substantial
inline-tool machinery. No new gate is tripped; **two** deviations, both by explicit operator
direction and both recorded in Complexity Tracking — (1) no feature flag (2026-08-31),
(2) no §VI.b approval gate on the unit/integration test tier (2026-09-01). **PASS.**

---

## Project Structure

### Documentation (this feature)

```text
specs/in-progress/069-mandatory-client-resolution-before-ledger-event/
├── spec.md                        # re-specified 2026-09-01 (authoritative)
├── user-stories.md                # regenerated 2026-09-01 (BLOCKING gate satisfied)
├── plan.md                        # this file
├── research.md                    # Phase 0 — all deferrals resolved
├── data-model.md                  # Phase 1
├── quickstart.md                  # Phase 1
├── contracts/                     # Phase 1
│   ├── recognition-and-logging.md          # NEW — recognition-call tri-state verdict shape
│   │                                       #   + the ledgerer + 3 INFO breadcrumb lines
│   ├── media-capture-routing.md            # MediaHandler → conversational-pipeline synthetic-turn
│   │                                       #   contract (בנק + הסכם images + docx); the stash
│   ├── client-resolution-gate.md           # constitution-guidance contract (what the model must do)
│   └── payload-fidelity-manifest.md        # FR-069-022 fixture-manifest + two-hop assertion contract
│   # DELETED: ledger-capture-suppression.md (the guard is removed, not narrowed)
│   # DELETED/folded: unresolved-capture-logging.md → recognition-and-logging.md
├── checklists/
│   └── requirements.md            # regenerated 2026-09-01
└── tasks.md                       # Phase 2 — speckit.tasks
```

### Source Code (`apps/denidin-app/`)

```text
apps/denidin-app/
├── config/
│   └── runtime_constitution.md              # "Ledger Event Recognition" section REWRITTEN
│                                             #   (FR-069-041 — §XIX HARD STOP, operator-approved):
│                                             #   post-turn recognition step (not inline);
│                                             #   per-type mandatory-field contract + "complete event";
│                                             #   mandatory client resolution via "Resolving a client
│                                             #   by name"; store-anyway exception + marker phrase;
│                                             #   when the gate does NOT apply. Bidirectional xref with
│                                             #   "Resolving a client by name"; out-of-scope notes in
│                                             #   "Reminder Management" & "Invoice Management".
│                                             #   REMOVE old inline-tool guidance (call capture_ledger_event
│                                             #   N times, components-array workaround).
│                                             # (NO config.*.json change — zero new keys)
├── src/
│   ├── handlers/
│   │   ├── ai_handler.py                    # - DELETE _call_openai_ledger_followup_api
│   │   │                                     # - DELETE bugfix-018 MCP-suppression guard
│   │   │                                     #   (morning_mcp_used_this_turn)
│   │   │                                     # - DELETE protocol_violation (len>1 / unparseable-args)
│   │   │                                     #   whole-turn rejection machinery
│   │   │                                     # - DELETE _handle_ledger_event_capture inline path
│   │   │                                     # - DELETE LEDGER_EVENT_TOOL / capture_ledger_event from
│   │   │                                     #   _assemble_tools for the main conversational turn
│   │   │                                     # ~ KEEP query_ledger_events on the main turn (FR-069-008)
│   │   │                                     # + recognize_ledger_event(...) — the post-turn recognition
│   │   │                                     #   call (generalizes capture_ledger_events_from_text):
│   │   │                                     #   builds input from session + reply + this turn's MCP
│   │   │                                     #   calls/results + constitution ledger section; returns a
│   │   │                                     #   tri-state verdict; output never surfaced
│   │   │                                     # + build_ledger_stash_text(extracted_text, analysis,
│   │   │                                     #   source_type, source_medium) — verbatim structured stash
│   │   │                                     #   for the media synthetic turn (📸/"תמונה" vs 📄/"מסמך")
│   │   ├── whatsapp_handler.py              # (no change — send_response unchanged)
│   │   └── extractors/
│   │       ├── image_extractor.py           # (no change — vision classify stays the routing signal)
│   │       ├── docx_extractor.py            # (no new AI call — document_analysis.document_type is the
│   │       │                                 #   routing signal; docstring note that recognition is now
│   │       │                                 #   post-turn, not in the extractor)
│   │       └── base.py                       # ~ comment: ledger recognition is post-turn for all media
│   ├── managers/
│   │   └── ledger_event_manager.py          # + persist_recognized_event(verdict, session,
│   │   │                                     #   completing_message_id) — THE LEDGERER: mint event_id/
│   │   │                                     #   captured_at (+ agreement_id/component_id), resolve
│   │   │                                     #   event_datetime from the verdict's trigger_message_id
│   │   │                                     #   Green API ts (completing_message_id gets the back-link),
│   │   │                                     #   dedup, persist (reuse add_ledger_events_from_call),
│   │   │                                     #   append index, update Message.ledger_event_ids on the
│   │   │                                     #   completing message, emit recognized/written breadcrumbs.
│   │   │                                     #   NO OpenAI, NO client/Morning/ledger lookup.
│   │   │                                     # ~ _ensure_accounting_document_cache() unchanged (FR-069-025)
│   │   └── (no new manager)
│   └── (NO new module, NO cleanup_service change, NO config.py change, NO new scheduler)
└── denidin.py                                # _process_conversational_message: after
                                              #   WhatsAppHandler.send_response(), call the post-turn
                                              #   recognition hook (recognize_ledger_event → ledgerer).
                                              #   The media path (WhatsAppHandler.handle_media_message →
                                              #   MediaHandler) routes a בנק/הסכם classification into
                                              #   _process_conversational_message as a synthetic turn
                                              #   (Feature 030 pattern) carrying the stash — so the SAME
                                              #   post-turn hook covers it. Extract a _run_post_turn_
                                              #   ledger_recognition(session_id, chat_id, ...) helper so
                                              #   both entry points share one call site.

apps/denidin-app/src/handlers/media_handler.py # ~ on a בנק/הסכם classification from ANY extractor
                                              #   (image or docx): STOP calling add_ledger_events_from_call
                                              #   directly; instead route extractor output + extracted
                                              #   text into the conversational pipeline as a synthetic
                                              #   turn (build_ledger_stash_text for text_content).
                                              #   Non-ledger media: unchanged summary path.

tests/
├── unit/
│   ├── test_recognition_call.py                     # NEW — recognize_ledger_event: tri-state verdict,
│   │                                                 #   input assembly (incl. MCP calls+results),
│   │                                                 #   output never surfaced, mapped-schema shape
│   ├── test_ledgerer.py                             # NEW — persist_recognized_event: event_id/
│   │                                                 #   event_datetime (hard pointer from
│   │                                                 #   trigger_message_id) / captured_at / agreement_id
│   │                                                 #   / component_id; dedup; Message.ledger_event_ids
│   │                                                 #   on the completing message; declined → no write;
│   │                                                 #   NO OpenAI / NO Morning / NO ledger lookup
│   ├── test_ledger_capture_breadcrumbs.py           # NEW — recognized / written / declined INFO line
│   │                                                 #   shape + pairing
│   ├── test_ai_handler_media_ledger_routing.py      # NEW — build_ledger_stash_text (בנק + הסכם,
│   │                                                 #   source_medium image + document); MediaHandler
│   │                                                 #   routes (not direct persist)
│   ├── test_main_turn_tools.py                      # NEW — capture_ledger_event / LEDGER_EVENT_TOOL
│   │                                                 #   NOT in the main-turn tool list;
│   │                                                 #   query_ledger_events IS
│   └── test_media_handler.py                        # ~ deposit / agreement recognition now routes
├── integration/
│   └── test_ledger_client_resolution_routing.py     # NEW — webhook JSON → router → (mocked OpenAI):
│                                                     #   a בנק image, a הסכם image, AND a הסכם docx no
│                                                     #   longer persist directly — route through the
│                                                     #   pipeline; the post-turn recognition hook fires
├── billed/
│   └── test_e2e_ledger_069_{text,morning_create,docx}_billed.py  # NEW (Acceptance, split) — US1..US6,US8 / US2 / US10
│                                                     #   (incl. sc.5), US6, US8, US10 (docx)
├── expensive/
│   └── test_e2e_media_client_resolution.py          # NEW (Acceptance) — US7 (7a/7b/7c/7d), US9
└── fixtures/ledger_069/
    ├── agreement_new_client.txt      + .manifest.json         # US4
    ├── agreement_ambiguous.txt       + .manifest.json         # US5
    ├── agreement_doc_multi.docx      + .manifest.json         # US10
    ├── agreement_photo_multi.png     + .manifest.json         # US9
    ├── deposit_zero_matches.png      + .manifest.json         # US7 7a
    ├── deposit_one_partial.png       + .manifest.json         # US7 7b
    ├── deposit_two_plus.png          + .manifest.json         # US7 7c
    └── deposit_exact_match.png       + .manifest.json         # US7 7d
```

**Structure Decision**: single-app change inside `apps/denidin-app/src/`, in `handlers/` and
`managers/ledger_event_manager.py`. **No new module.** The net line count is expected to be
**negative** — the deleted inline-tool machinery (follow-up API, suppression guard,
protocol-violation checks, `_handle_ledger_event_capture`) is larger than the recognition
call + ledgerer added. No new package, no `morning-mcp-app` change, no new service/scheduler,
no `cleanup_service` change, no `config.py` / `config.*.json` change.

---

## Integration Contracts (METHODOLOGY §VII — mandatory, multi-component)

Full contracts in [`contracts/`](./contracts/). Summary of the component interactions this
feature creates, changes, or removes:

| # | Producer → Consumer | Contract | File |
|---|---|---|---|
| **C1** | `denidin.py` post-turn hook → `AIHandler.recognize_ledger_event` | After the operator reply is sent, the hook passes `{session_id, chat_id, reply_text, this_turn_mcp_calls_with_results, turn_message_id}`; `recognize_ledger_event` makes ONE text-only OpenAI call (conversation + reply + MCP calls/results + constitution ledger section), returns a **tri-state verdict** (`complete` {mapped `LedgerEvent` payload + `trigger_message_id`} \| `none` \| `declined` {`source_type`, stated name, `reason`}). Output is never surfaced to the operator; no follow-up round-trip. | `recognition-and-logging.md` |
| **C2** | `AIHandler.recognize_ledger_event` → `LedgerEventManager.persist_recognized_event` (the ledgerer) | On `complete`: mint `event_id` / `captured_at` (+ `agreement_id` / `component_id`); resolve `event_datetime` from `trigger_message_id`'s Green API notification timestamp (the hard pointer); dedup; persist via `add_ledger_events_from_call`; append the in-memory index; append `event_id` to the **completing** message's `Message.ledger_event_ids`; emit INFO "recognized" + "written". On `declined`: emit INFO "declined by operator", persist nothing. **No** OpenAI call, **no** client / Morning / ledger lookup (an already-decided `reference` id may be denormalized into `_linked_document` from the in-memory index — not a lookup of *whether* to link). | `recognition-and-logging.md` |
| **C3** | `MediaHandler` → conversational pipeline (`_process_conversational_message` synthetic turn) | On a `בנק` **or** `הסכם` classification from **any** extractor (image via `ImageExtractor` vision classify; `docx` via `DOCXExtractor` `document_analysis.document_type`), `MediaHandler` STOPS calling `add_ledger_events_from_call` and instead injects a synthetic conversational turn whose `text_content` is `build_ledger_stash_text(extracted_text, analysis, source_type, source_medium)` — a verbatim structured stash (banking triplet first for `בנק`; one line per fee component for `הסכם`; `📸`/"תמונה" vs `📄`/"מסמך" framing per `source_medium`). Resolution, `add_client` (via `PendingApprovalManager`), and the post-turn recognition hook then all run on the shared path. | `media-capture-routing.md` |
| **C4** | `runtime_constitution.md` → the model (every `הסכם` / `בנק` turn, and the recognition call) | The rewritten "Ledger Event Recognition" section: post-turn recognition (not inline); per-type mandatory-field contract + "complete event"; mandatory client resolution via "Resolving a client by name" (exact→silent, 1 candidate→name+offer-new, 2+→list+offer-new, no match→full name+email+phone→`add_client`); ambiguity → re-ask once as a closed choice; store-anyway only after the operator declines email/phone (a **single** closed question, no re-ask) or proactively requests it (honoured with no "are you sure" turn); copy the stash verbatim; marker phrase into `description` on store-anyway; when the gate does NOT apply (`payer_name`; `חשבונית` client resolved by construction). Bidirectional xref with "Resolving a client by name"; out-of-scope notes in "Reminder Management" / "Invoice Management". §XIX HARD STOP. | `client-resolution-gate.md` |
| **C5** | main conversational turn tool list | `capture_ledger_event` / `LEDGER_EVENT_TOOL` is **removed** from `_assemble_tools` for the main turn. `query_ledger_events` (read/search) **stays**. The bugfix-018 suppression guard, `_call_openai_ledger_followup_api`, and the `>1 call` / unparseable-args protocol-violation machinery are **deleted** — the behaviors they protected hold by construction (no inline tool to misfire) and are covered by US3. | `recognition-and-logging.md` |
| **C6** | ledgerer → app log | Three INFO breadcrumb lines, no state: "recognized" (source type, session id, chat id, `now_local()` time) the moment the recognition call returns `complete`; "written" (same + `event_id`) after a successful persist; "declined by operator" (source type, operator-stated name, reason) on a `declined` verdict. A "recognized" with no matching "written" / "declined" = a dropped capture, detectable by log inspection. No tracker, no sweep, no config. | `recognition-and-logging.md` |
| **C7** | `AIHandler.get_response` ↔ `PendingApprovalManager` | **Unchanged.** The `add_client` approval turn during a resolution detour uses the existing MCP pending-approval flow (typed reply + button tap, `_resolve_pending_approval`). Feature 069 adds no new pending-approval type. | *(this table row only — no dedicated contract file; existing flow)* |
| **C8** | `LedgerEventManager.persist_recognized_event` → Feature 025 dedup | 069's synchronous `חשבונית` write goes through `add_ledger_events_from_call` → `_ensure_accounting_document_cache()`, keyed on `accounting_document_display_number` (`ledger_event_manager.py:1163-1169`), so Feature 025's next reconciliation tick treats it as a duplicate and writes 0 additional files. Feature 025's sweep is otherwise unchanged. | *(this table row only — no dedicated contract file; cross-ref `recognition-and-logging.md` C6 step 6)* |
| **C9** | test fixture → acceptance test | Each `הסכם` / `בנק` fixture ships a committed `*.manifest.json`; the assertion helper does the exhaustive bidirectional match + (media) two-hop. Fixtures are detail-rich (≥3 components / explicit date / subtype for `הסכם`; amount + date + full banking triplet + reference for `בנק`). | `payload-fidelity-manifest.md` |

---

## Phase plan (delivery order — feeds `speckit.tasks`)

Per METHODOLOGY §VI: each story = Task A (unit/integration tests, RED — **Task A→B approval
gate Feature-069-waived**, tests still RED-first + immutable once committed) → Task B (impl,
GREEN). Billed/expensive acceptance tests are **described** in `tasks.md`'s Acceptance phase
in user-experience terms and written + run **once, together, at the end** (§VI).

- **Phase 1 — Mechanism move (the enabler slice, C1 / C2 / C5 / C6).** Delete
  `_call_openai_ledger_followup_api`, the bugfix-018 suppression guard, the
  protocol-violation machinery, `_handle_ledger_event_capture`, and `LEDGER_EVENT_TOOL` from
  the main turn (keep `query_ledger_events`). Add `AIHandler.recognize_ledger_event` (the
  tri-state recognition call), `LedgerEventManager.persist_recognized_event` (the ledgerer,
  reusing `add_ledger_events_from_call`), the three INFO breadcrumbs, and the `denidin.py`
  post-turn hook. Unit: `test_main_turn_tools.py`, `test_recognition_call.py`,
  `test_ledgerer.py`, `test_ledger_capture_breadcrumbs.py`. *(no story — enabler; delivers
  US1 and US3 behaviour once green)*
- **Phase 2 — US1 (mechanism move / decoupling, exact-match).** End-to-end proof that the
  decoupled path captures a complete `הסכם` for an exact-match client with no second reply
  round-trip and no inline tool. Also lands US6's silent-exact-match behaviour.
- **Phase 3 — US3 (regression guard).** `list_invoices` turn + short field-filling reply
  mid-`create_combo_document` approval → reply intact, 0 spurious events. Mostly assertions
  over Phase 1's deletions; no new production code expected.
- **Phase 4 — US2 (Morning "create" captured synchronously, C8).** The recognition call
  input includes this turn's `create_*` call + result; `חשבונית` persisted synchronously;
  Feature 025 dedup verified. `persist_recognized_event` routes a `חשבונית` verdict through
  `add_ledger_events_from_call` unchanged.
- **Phase 5 — US4 (FLAGSHIP: new-client `הסכם`, text) + constitution guidance C4 drafted +
  approved (§XIX HARD STOP).** The full resolution detour (full name + email + phone →
  `add_client` approval) as ordinary conversation; recognition returns `none` until the
  client is created and the agreement is complete, then `complete` with every component /
  date / subtype / `payer_name` and `event_datetime` = the original agreement message's
  timestamp.
- **Phase 6 — US5 (ambiguous `הסכם`, text)** incl. scenario 5 (ambiguous reply → re-ask once
  as a closed choice, C4 / research.md R7) and 5a/5b (1 vs 2+ candidates).
- **Phase 7 — US8 (won't provide email/phone).** The **single** closed
  store-anyway/don't-store question (no re-ask for email/phone first) **plus** a proactive
  store-anyway election up front (honoured with no "are you sure" turn); store-anyway marker
  phrase in `description` (no schema change); the `declined` verdict path + its INFO
  breadcrumb.
- **Phase 8 — US7 (FLAGSHIP deposit image, 7a/7b/7c/7d) + US9 (photographed multi-component
  `הסכם`).** `MediaHandler` routing (media-type-agnostic) for `בנק` **and** `הסכם` images
  (C3); `build_ledger_stash_text` (source-type- and source-medium-aware); `denidin.py`
  synthetic-turn wiring; integration test `test_ledger_client_resolution_routing.py` (one
  `בנק` image case, one `הסכם` image case). 7d is the silent exact-Morning-match path off a
  slip — no disambiguation question, no `add_client`.
- **Phase 8b — US10 (`docx` multi-component `הסכם`).** `MediaHandler` routes a
  `DOCXExtractor` `document_type == הסכם` classification through the **same** Phase 8 routing
  and stash builder (only `source_medium="document"`); **no** new AI call in `DOCXExtractor`;
  `base.py` / docstring note; extend `test_ledger_client_resolution_routing.py` with a `docx`
  case. Recognition is text-only (`config.ai_model`) → US10 acceptance is `billed`.
- **`speckit.analyze`** (cross-artifact consistency) between Phase 8b and the Acceptance
  phase — in `tasks.md` numbering, a dedicated task (`T030A`) between the last story phase
  and the Acceptance phase.
- **Acceptance phase.** Fixtures + manifests (C9, detail-rich per `user-stories.md`,
  including `agreement_doc_multi.docx`), the bidirectional / two-hop assertion helper, then
  write **and run**: `tests/billed/test_e2e_ledger_069_*_billed.py` (US1, US2, US3, US4,
  US5 incl. sc.5, US6, US8, **US10**) and — each with its own explicit per-run approval —
  `tests/expensive/test_e2e_media_client_resolution.py` (US7 7a/7b/7c/7d, US9). The ~16
  pre-existing billed/expensive ledger-capture tests are reworked here (operator-approved
  2026-09-01): add the `live_morning_tunnel` fixture dependency + either a seeded exact-match
  Morning client (cheapest — US6/silent path) or a scripted resolution detour
  (`converse_until_ledger_events_captured` + `ClarificationAnswerBank`).

---

## Complexity Tracking

| Deviation | Why it's accepted | Simpler alternative rejected because |
|---|---|---|
| **No feature flag** — the feature ships unconditionally, with no `config.feature_flags` toggle and no byte-identical-when-disabled code path (CLAUDE.md's "feature flags for new behavior" convention). | **Explicit user direction, 2026-08-31** ("no need for feature flag"). The changed surface is contained — the net change is a **deletion** of inline-tool machinery plus one recognition call, one ledgerer path, three INFO breadcrumb log lines, and constitution guidance; no new module, no config key — and every path is covered by the mandatory billed/expensive acceptance suite before the feature is "done". Merge ≠ redeploy, so nothing reaches an environment without a separate explicit human deploy. | A flag would add a `config.feature_flags` entry, an OFF-path guard that keeps the *old* entangled inline-tool mechanism alive alongside the new one, and doubled unit-test matrices — cost the user judged not worth it for a feature whose acceptance gate is a full real-API E2E suite anyway, and whose whole point is to *remove* the old mechanism. |
| **No §VI.b approval gate on the unit/integration test tier** — Task A (tests) is written RED-first and is immutable once committed, but the human sign-off checkpoint between Task A and Task B is skipped for unit + integration tests (METHODOLOGY §VI.b mandates it). | **Explicit operator direction, 2026-09-01** ("unit and integration tests I don't need to approve"). RED-first ordering and test-immutability-once-committed are retained, so the anti-gaming intent of §VI.b (tests can't be quietly rewritten to fit the implementation) still holds. The gates that carry real UX / cost risk are **kept**: constitution and operator-facing wording still needs §XIX approval before the dependent task (FR-069-041 is a HARD STOP), and every `expensive` acceptance run still needs its own fresh approval. | Keeping the gate would mean the operator reviews every RED unit/integration test file for this feature before implementation — friction the operator explicitly declined for a feature whose real proof is the billed/expensive acceptance suite they *do* gate. A global METHODOLOGY §VI.b amendment is out of scope here; this deviation is Feature-069-scoped. |

No other deviation. No new project, no new pattern, no new persistence, no new scheduler, no
new config key, no new in-memory state.
