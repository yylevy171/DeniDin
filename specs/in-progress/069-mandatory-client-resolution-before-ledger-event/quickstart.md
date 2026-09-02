# Quickstart: Post-Turn Ledger Capture with Mandatory Client Resolution (Feature 069)

**Phase 1** | [plan.md](./plan.md) · [spec.md](./spec.md) · [contracts/](./contracts/)

## What this feature changes, in two paragraphs

**Mechanism move.** Ledger capture stops being an inline tool the conversational model calls
mid-reply. There is no `capture_ledger_event` tool on the main turn any more, no second
OpenAI round-trip to recover the reply, no MCP-suppression guard, no protocol-violation
machinery. Instead, **after** the operator's reply is finalized and sent, one dedicated
text-only OpenAI call — **the recognition call** — asks a single question: *did a complete
ledger event finish this round, and if so, here is its data mapped to the ledger schema?* A
mechanical, zero-AI **ledgerer** then mints the ids, dedups, persists the immutable JSON, and
links it from the session message. `query_ledger_events` (read/search only) stays on the
main turn — it is the only ledger tool the model may call.

**Mandatory client resolution.** A `הסכם` (fee agreement), `בנק` (bank deposit), or
`חשבונית` (in-conversation Morning document) event is not "complete" — and nothing is
persisted — until every mandatory field for its type is present, including a `client_name`
resolved to an **exact** existing Morning client name (matched, or created via the normal
`add_client` flow). Resolution happens as **ordinary conversation** guided by
`runtime_constitution.md`, using the same "Resolving a client by name" flow Morning document
creation already uses — never a code state machine, never anything the recognition call or
the ledgerer does. An unresolved client just means the recognition call returns "nothing
complete this round" and the conversation continues. The one sanctioned exception is an
explicit operator "store anyway" — either the answer to a **single** closed store-anyway
question DeniDin asks after the operator declines a new client's email + phone (no re-ask),
or a **proactive** operator request to store without those details (honoured directly, no
"are you sure" turn); that event carries `[לקוח לא אומת במורנינג]` in its `description` and
no Morning client is created. Every optional field provided or extracted at any point survives the whole
conversation and reaches the persisted record — the `בנק` banking triplet and every `הסכם`
fee component especially.

## Configuration

**No feature flag and no new config key at all** (2026-08-31 user direction) — the feature
is active as soon as the code is deployed, and it adds **zero** keys to any `config.*.json`.
The only gate before it reaches an environment is the normal explicit human deploy (merging
to `master` never redeploys), backed by a green billed/expensive acceptance run.

## The capture paths

| Path | Entry | How capture happens |
|---|---|---|
| `הסכם` / `בנק` from typed Hebrew text | `textMessage` → `_process_conversational_message` | The model resolves the client as ordinary conversation (contract C4). After the reply is sent, the **post-turn recognition call** reads the whole turn and — if the event is complete — returns it schema-mapped; the ledgerer persists it. |
| `חשבונית` — Morning document created in the conversation | any turn where a `create_*` MCP call succeeds | The recognition call's input includes this turn's `create_*` call **and its result**, so the `חשבונית` event is recognized **synchronously that turn** from the real Morning response. It persists through the same path as Feature 025, so 025's next sweep tick sees the display number as known and does not double-write. |
| `בנק` slip / `הסכם` photo / `הסכם` `.docx` | `imageMessage` / `documentMessage` → `MediaHandler` | **New**: `MediaHandler` stops persisting the recognized capture directly. It routes the extractor output + extracted text into `_process_conversational_message` as a **synthetic turn** (Feature 030 contact-card pattern) whose text is a **verbatim structured stash** of every extracted field (banking triplet first for `בנק`; one line per fee component for `הסכם`; `📸`/"מהתמונה" vs `📄`/"מהמסמך" per `source_medium`). Resolution + the post-turn recognition call then run exactly as for a typed turn. Routing signal = the extractor's **existing** analysis (`ImageExtractor` vision classify; `DOCXExtractor` `document_analysis.document_type`) — **no new AI call is added to any extractor**. `pdf` → **Feature 071**. (contracts C3, C1/C2) |

## Detecting a dropped capture (operational)

No abandonment tracker. The ledgerer emits three INFO breadcrumbs:

```
[069] ledger capture recognized: type=<deposit|agreement|invoice> session=<id> chat=<id> time=<iso>
[069] ledger event written:      type=<deposit|agreement|invoice> event_id=<id> session=<id> chat=<id> time=<iso>
[069] ledger capture declined by operator: type=<deposit|agreement> name=<...> session=<id> reason=declined_by_operator time=<iso>
```

A `recognized` line with **no** matching `written` line for the same `session` = a persist
failure. `grep '\[069\] ledger capture recognized' logs/<env>/denidin.log` then check each
`session` has a `written` follow-up. Reliable for media captures (the recognition call runs
post-turn on every turn); best-effort for typed text abandoned before the event ever became
complete. `none` results produce no INFO line (DEBUG only).

## Manual smoke test (dev)

1. Start dev (`scripts/run_all.sh dev` — **needs explicit approval**).
2. From a godfather WhatsApp number, send a photo of a bank deposit slip whose payer name is
   **not** an exact Morning client.
3. Expect DeniDin to ask which existing client this is, or to create a new one (no ledger
   event yet).
4. Reply `חדש`, provide a full name + email + phone; approve the `add_client` prompt.
5. Expect a normal confirmation. Then check `{data_root}/events/` for a new `בנק` JSON whose
   `client_name` is the newly created Morning name and whose `bank_number` / `bank_branch` /
   `bank_account` / `amount` / `txn_date` match the slip exactly, and whose `event_datetime`
   is the slip **message's** timestamp. The session message for the completing turn has the
   new `event_id` in `ledger_event_ids`.
6. Send a second slip whose payer **is** an exact Morning client → expect no questions and
   no `add_client` (SC-003, US7d), and a `בנק` JSON appears after the reply.
7. Send a **photo of a multi-component fee agreement** (`הסכם`) whose client is **not** an
   exact Morning client → same resolve-then-capture detour; after resolution, check
   `{data_root}/events/` for a `הסכם` JSON whose `client_name` is the resolved Morning name
   and whose every fee component / percentage / subtype / `payer_name` from the photo made it
   into the persisted event (US9, FR-069-022).
8. Send a **`.docx` multi-component fee agreement** → identical detour (only the prompt says
   "מסמך" instead of "תמונה"); check the persisted `הסכם` JSON the same way (US10).
9. Ask DeniDin to create a Morning invoice for an existing client → after it confirms
   creation, check `{data_root}/events/` for a `חשבונית` JSON with the Morning display number
   and amount (US2). Feature 025's next tick writes no second file for that display number.

## Key files

- `src/handlers/ai_handler.py` —
  - **DELETE** `_call_openai_ledger_followup_api`, the bugfix-018 MCP-suppression guard,
    the `>1 call` / unparseable-args protocol-violation machinery,
    `_handle_ledger_event_capture`, and `LEDGER_EVENT_TOOL` / `capture_ledger_event` from
    the main-turn tool list.
  - **KEEP** `query_ledger_events` on the main turn.
  - **ADD** `recognize_ledger_event(...)` — the post-turn recognition call (tri-state
    verdict; generalizes `capture_ledger_events_from_text`).
  - **ADD** `build_ledger_stash_text(extracted_text, analysis, source_type, source_medium)`.
- `src/managers/ledger_event_manager.py` — **ADD** `persist_recognized_event(verdict,
  session, completing_message_id)` — the ledgerer (reuses `add_ledger_events_from_call`;
  `event_datetime` from `trigger_message_id`'s Green API timestamp; emits the breadcrumbs).
  `_ensure_accounting_document_cache()` unchanged.
- `src/handlers/media_handler.py` — on a `בנק` / `הסכם` classification from any extractor,
  route a synthetic conversational turn instead of calling `add_ledger_events_from_call`.
- `src/handlers/extractors/docx_extractor.py`, `image_extractor.py`, `base.py` — **no new AI
  call**; docstring note that ledger recognition is now post-turn for every medium.
- `denidin.py` — `_run_post_turn_ledger_recognition(...)` helper (shared by the typed and
  media entry points); `_send_ai_response_and_attach(...)` helper (send + pending-approval
  attach, extracted so the media path reuses it).
- `config/runtime_constitution.md` — "Ledger Event Recognition" section **rewritten**
  (FR-069-041 — wording approved during `speckit.implement`, §XIX HARD STOP) + bidirectional
  cross-references.
- *(no new module, no `cleanup_service` change, no `config.py` change, no schema change)*

## Tests

- **unit** — `tests/unit/test_recognition_call.py`, `test_ledgerer.py`,
  `test_ledger_capture_breadcrumbs.py`, `test_ai_handler_media_ledger_routing.py`,
  `test_main_turn_tools.py`, updated `test_media_handler.py`.
- **integration** — `tests/integration/test_ledger_client_resolution_routing.py` (real
  webhook JSON → router; OpenAI stubbed; asserts a `בנק` image, a `הסכם` image, **and** a
  `הסכם` `docx` route through the pipeline instead of persisting directly, and the post-turn
  recognition hook fires).
- **acceptance** (written + run once, after all unit/integration green — METHODOLOGY §VI):
  - **billed** `tests/billed/test_e2e_ledger_post_turn_capture.py` — US1 (mechanism move),
    US2 (`חשבונית` synchronous — type-320 combo doc, VAT included, no VAT question),
    US3 (regression guard), US4 (new-client typed `הסכם`), US5 (5a/5b ambiguous),
    US6 (exact-match silent), US8 (single-ask store-anyway + don't-store + proactive
    election), US10 (`docx` `הסכם` — text-only recognition).
  - **expensive** `tests/expensive/test_e2e_media_client_resolution.py` — US7 (7a/7b/7c:
    0 / 1 / 2+ matches → `חדש` → new-client → approval → `בנק` event with full banking
    payload; 7d: exact Morning match → no question, no `add_client`), US9 (photo of a
    multi-component `הסכם`). Each needs its own explicit per-run approval.
- Every event-creating acceptance scenario uses `assert_event_matches_manifest` — the
  exhaustive bidirectional per-fixture manifest check (contract C9), two-hop for media.
- No test asserts `schema_version`'s value (CLAUDE.md rule).

## Out of scope (do not touch)

- Any hard code-level rejection of an unresolved capture (enforcement is constitution
  guidance + the acceptance suite).
- `payer_name` resolution — stays free text.
- Retroactive backfill of existing `LedgerEvent` files — Feature 065 owns the August 2026
  `בנק` cleanup.
- Any `LedgerEvent` schema field or `CURRENT_SCHEMA_VERSION` bump — the store-anyway marker
  is text in the existing `description`.
- `pdf` agreement extraction routing — **Feature 071**
  (`specs/backlog/071-pdf-single-call-extraction/`). Photo `הסכם` (US9) and `docx` `הסכם`
  (US10) **are** in scope.
- A durable cross-conversation Morning client-name cache — **Feature 072**
  (`specs/backlog/072-morning-client-name-cache/`). 069 makes one `resolve_client_name` call
  per recognized event, conversation-scoped cache only.
- `apps/morning-mcp-app` — no change (`resolve_client_name` / `add_client` / `create_*`
  already exist).
