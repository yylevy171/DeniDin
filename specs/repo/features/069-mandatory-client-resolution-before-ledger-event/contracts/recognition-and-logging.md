# Contracts C1 / C2 / C5 / C6: The recognition call, the ledgerer, and the lifecycle log lines

**Feature 069** | [plan.md](../plan.md) · [data-model.md](../data-model.md) §2/§3/§4 ·
[research.md](../research.md) R3/R5 · FR-069-002/003/004/005/008/012/025/035

> **DESIGN-THREAD ADDENDUM (2026-09-03, decisions 1–12 — full table in tasks.md).** The
> recognition call now: uses a **dedicated prompt file** `config/ledger_recognition_prompt.md`
> (not the constitution); sees a **1-hour window** (`ledger_recognition_context_window_hours`,
> default 1.0) with `[✓ captured as …]` markers and persisted `Message.mcp_calls`; **attaches
> `query_ledger_events`** and runs a bounded chained query loop (cap `MAX_RECOGNITION_QUERY_ROUNDS
> = 3`), always querying the client's history once up front. The ledgerer dates `הסכם`/`בנק`
> from the **completing message** (`_message_epoch`, renamed from `_trigger_epoch`);
> `trigger_message_id` is informational only. Two new deterministic ledgerer steps:
> `_content_fingerprint`/`_is_duplicate_recognized_event` (skip a same-content-same-day
> duplicate) and `_mandatory_field_gaps` (on a gap → **persist anyway**, `[רישום חלקי — חסר:
> …]` into `description`).

> **Redesign (2026-09-01).** This contract replaces the deleted
> `unresolved-capture-logging.md` (C5 = an inline `record_unresolved_ledger_capture` tool)
> and `ledger-capture-suppression.md` (C4 = a "narrowed" MCP-suppression guard). Under the
> redesign there is **no inline ledger-write tool on the main turn** and **no suppression
> guard** — both are gone. Ledger capture is a post-turn recognition call whose output is a
> tri-state verdict; the ledgerer emits the log lines.

## Nature of the contract

Two code seams and their exact shapes:

1. **The recognition call** — `AIHandler.recognize_ledger_event(...)` — one dedicated
   text-only OpenAI call fired **after** the operator reply for a godfather/admin turn is
   finalized and sent. It is the ONLY place prose → `LedgerEvent`-schema mapping happens.
2. **The ledgerer** — `LedgerEventManager.persist_recognized_event(...)` — the mechanical,
   zero-AI consumer of the recognition call's output. Generates ids, dedups, persists,
   updates `Message.ledger_event_ids`, emits the log lines.

Neither surfaces anything to the operator. The recognition call's output is never appended
to the conversation, never sent over WhatsApp, never logged verbatim.

## C1 — the post-turn hook (`denidin.py`)

`denidin.py`'s shared conversational path (`_process_conversational_message`, also reached
by the media synthetic turn per `contracts/media-capture-routing.md`) gains ONE post-turn
step, after the reply has been sent and after any pending-approval attach:

```python
# after _send_ai_response_and_attach(...)
self._run_post_turn_ledger_recognition(session=session, chat_id=chat_id,
                                       sender_phone=sender_phone,
                                       reply_text=ai_response.response_text,
                                       turn_mcp_calls=ai_response.mcp_tool_events)
```

- Runs **only** for a godfather/admin turn (same RBAC predicate that gates
  `query_ledger_events` today).
- Wrapped so any exception is logged and swallowed — **FR-069-006**: a recognition-call
  failure changes 0 bytes of the reply the operator already received.
- `turn_mcp_calls` carries this turn's Morning MCP tool calls **and their results verbatim**
  (FR-069-002) — the `create_*` response the `חשבונית` capture is built from.
- Fires on every such turn (no code-side financial-content pre-filter — explicitly out of
  scope, spec "Out of Scope").

## C2 — `AIHandler.recognize_ledger_event(...)` → tri-state verdict

```python
def recognize_ledger_event(self, *, session, reply_text, turn_mcp_calls,
                           constitution_text) -> dict:
    # returns one of the three shapes in data-model.md §2
```

**Input assembled by the method** (FR-069-002):
- the conversation so far (session messages),
- the reply just sent (`reply_text`),
- this turn's Morning MCP tool calls and their results verbatim (`turn_mcp_calls`),
- the constitution's "Ledger Event Recognition" section (`constitution_text`).

**Call shape**: text-only OpenAI call using `LEDGER_EVENT_TOOL`'s JSON schema for the
`event` object (the `capture_ledger_events_from_text` pattern, generalized from "OCR'd media
text" to "full turn context"). One-shot retry on a parse failure / `is_incomplete_capture`,
reusing the existing retry shape. No follow-up round-trip (FR-069-002). Output never shown
to the operator.

**Output** — exactly one of (full field lists in [data-model.md](../data-model.md) §2):

| verdict | when | payload |
|---|---|---|
| `complete` | every mandatory field for the `source_type` is present *this round* (§1 table) — including a `client_name` resolved to an exact Morning name, OR a store-anyway election | `{verdict:"complete", event:{…fully schema-mapped…}, trigger_message_id}` |
| `none` | nothing complete: unresolved client, missing mandatory field, a read-only Morning question, ordinary chatter, a mid-detour turn | `{verdict:"none"}` |
| `declined` | the operator was asked the single closed store-anyway question (FR-069-033, no re-ask) and explicitly answered *don't store* | `{verdict:"declined", source_type, client_name_stated, reason:"declined_by_operator"}` |

**`חשבונית` synchronous capture** (FR-069-012/025): when `turn_mcp_calls` contains a
successful `create_*` call, the `event` is populated from the **real Morning response** in
that tool result — `source_type="חשבונית"`, `event_subtype` = the document type,
`accounting_document_display_number` / `amount` / `txn_date` from the response — never
re-derived from the operator's prose.

**Store-anyway marker** (FR-069-034): on an operator-elected store-anyway — whether the
operator answered *store* to the single closed question or **proactively** asked to store
without the contact details (no "בטוח?" confirmation on the proactive path) — the `complete`
verdict carries `event.client_name` = the operator-stated free text AND the fixed marker
`[לקוח לא אומת במורנינג]` inside `event.description`. The constitution's store-anyway
guidance instructs this; there is no code branch for the marker on the write path.

## C6 — the ledgerer `LedgerEventManager.persist_recognized_event(verdict, session, completing_message_id)`

Zero-AI (FR-069-004). No OpenAI call, no client resolution, no Morning lookup, no ledger
query. Algorithm (full detail in [data-model.md](../data-model.md) §3):

**On `complete`:**
1. `event_datetime` = the **completing message's own persisted local timestamp**, formatted
   `%d/%m/%Y %H:%M` — the ledgerer receives `completing_message_id` as its third positional
   argument (the caller in `denidin.py` passes `session.message_ids[-1]`, i.e. the assistant
   reply that closed the round); `_message_epoch(session, completing_message_id)` looks that
   message up and parses its persisted `Message.timestamp` (an Asia/Jerusalem ISO string
   written at message-persist time). This is the **hard pointer**. Never `now_local()`, never
   the recognition-call clock, and **not** `verdict["trigger_message_id"]` (that id is
   informational only — the audit breadcrumb for which message's economic content triggered
   the event, which for a resolution detour or an amendment is an *earlier* message than the
   completing one — see design-thread decision #10). (Resolved 2026-09-02/2026-09-03: the
   Green API notification epoch is not persisted; the message's processing-time ISO timestamp
   differs from it by sub-second-to-seconds latency, immaterial at minute precision.
   `local_from_timestamp` is therefore not used here — a plain ISO parse is.) Every hardcoded
   acceptance-test `event_datetime` expectation depends on this.
2. `captured_at = now_local()`.
3. Mint `event_id` — source-type prefix (`A`=`הסכם`, `B`=`בנק`; `חשבונית` keeps the existing
   accounting prefix) + `DDMMYY` + `HHMM` + same-minute sequence digit — exactly as
   `add_ledger_events_from_call` does today.
4. `הסכם` only: mint `agreement_id` + per-component `component_id`; explode `event.components`
   into one `record` per component via the existing `merged_event = {**shared, **component}`
   loop (`ledger_event_manager.py:1173`).
5. Denormalize an already-decided `event.reference` id into `_linked_document` display
   fields from the in-memory index (`ledger_event_manager.py:~1060-1077`) — formatting a
   linkage the **conversation** established, not deciding whether to link (does not violate
   FR-069-004).
6. Dedup against `self._index`; for `חשבונית` via `_ensure_accounting_document_cache()`
   keyed on `accounting_document_display_number` (`ledger_event_manager.py:1163-1169`) — so
   Feature 025's next reconciliation sweep tick treats it as a duplicate (FR-069-026; the
   Feature 025 dedup path, described in `plan.md`'s C1–C9 contract table row C8 — no separate
   contract file).
7. Persist immutable JSON (`json.dump(record, f, sort_keys=True, ensure_ascii=False,
   indent=2)` → `.json.tmp` → `.replace()`); `self._index.append(record)`.
8. Append the new `event_id`(s) to the **completing** message's `Message.ledger_event_ids`
   (the turn the event became complete on — **not** `trigger_message_id`).
9. Emit the **recognized** line (before step 7) and the **written** line (after step 7, one
   per persisted event).

**On `declined`:** emit the **declined by operator** line. Persist nothing. No state to
clear (there is no tracker).

**On `none`:** nothing. No INFO line (DEBUG only).

## C6 (logging) — the three lifecycle log lines (FR-069-035)

INFO level, emitted by the ledgerer through the existing app logger. `[069]` prefix. Every
line carries a `now_local()` `time=` field (Israel-local, offset-aware). `type` maps
`בנק`→`deposit`, `הסכם`→`agreement`, `חשבונית`→`invoice`.

```
[069] ledger capture recognized: type=<deposit|agreement|invoice> session=<id> chat=<id> time=<iso>
[069] ledger event written: type=<deposit|agreement|invoice> event_id=<id> session=<id> chat=<id> time=<iso>
[069] ledger capture declined by operator: type=<deposit|agreement> name=<client_name_stated!r> session=<id> reason=declined_by_operator time=<iso>
```

**Abandonment** = a `recognized` line with no matching `written` line for the same session
(a persist failure), OR a media-sourced recognition turn that produced no `recognized` line
across the detour (operator walked away). Detected **operationally** (log inspection), not
in code — there is no abandonment tracker and no abandonment log line (spec Edge Cases,
data-model.md §4). Accepted 2026-08-31.

## C5 — what is deleted from the main turn (folds in the old `ledger-capture-suppression.md` / `unresolved-capture-logging.md`)

| Deleted | Was | Why gone |
|---|---|---|
| `_call_openai_ledger_followup_api` | the second OpenAI round-trip that recovered the operator's real reply after a `capture_ledger_event` function_call | the recognition call never touches the reply — no round-trip needed (FR-069-005) |
| bugfix-018 MCP-suppression guard (`morning_mcp_used_this_turn` → strip `capture_ledger_event`) | stopped a spurious capture when the model read `list_invoices` output back into itself (2026-07-28) | structurally unreachable — no inline capture tool on the main turn (FR-069-005, US3) |
| `protocol_violation = len(ledger_calls) > 1` / `single_call_unparseable` whole-turn rejection | stopped a lost reply / a 400 on truncated tool args when a function_call + a message competed (2026-08-02) | same — no inline capture tool to misfire (FR-069-005, US3) |
| `_handle_ledger_event_capture` | dispatched the inline `capture_ledger_event` function_call | replaced by the recognition call + the ledgerer |
| `LEDGER_EVENT_TOOL` / `capture_ledger_event` attachment to the main conversational turn | the inline write tool | the schema is reused by the recognition call only; the tool is not attached (FR-069-001) |
| an inline `record_unresolved_ledger_capture` / `LEDGER_SKIP_TOOL` tool | never shipped — was a draft in the pre-redesign data-model.md | contradicts FR-069-008 (`query_ledger_events` is the only ledger tool on the main turn); the `declined` verdict covers it |

**Kept:** `query_ledger_events` (read/search) stays attached to the main conversational turn
for godfather/admin — how the model establishes `reference` / `reference_hint` linkage
(FR-069-008/021).

## Tests

- **unit** `test_recognition_call.py`: given a constructed session + `turn_mcp_calls` +
  a stubbed OpenAI response, `recognize_ledger_event` returns the right verdict —
  `complete` with a fully schema-mapped `event` + `trigger_message_id` when mandatory fields
  are present; `none` on a missing mandatory field / unresolved client / a read-only Morning
  question / ordinary chatter; `declined` (with `source_type` + `client_name_stated`) when
  the transcript shows an explicit store-anyway *don't store*; one-shot retry on a parse
  failure; a `create_*` in `turn_mcp_calls` → `source_type="חשבונית"` mapped from the tool
  result, not the prose; output never appended to the session.
- **unit** `test_ledgerer.py`: `persist_recognized_event` on a `complete` verdict →
  `event_datetime` from the **completing message's** persisted timestamp (**not**
  `now_local()`, **not** `trigger_message_id`); `captured_at` = `now_local()`; `event_id`
  prefix + format; `הסכם` → `agreement_id` + per-component `component_id`, one file per
  component; `reference` denormalized into `_linked_document`; `חשבונית` dedup through
  `_ensure_accounting_document_cache`; `Message.ledger_event_ids` updated on the
  **completing** message, not the trigger; no
  OpenAI call, no `resolve_client_name` call, no ledger query (assert via a spy that raises);
  `declined` → nothing persisted; `none` → nothing.
- **unit** `test_ledger_capture_breadcrumbs.py`: exact `[069]` line formats for
  `recognized` / `written` / `declined`; `type` mapping `בנק`→`deposit` /
  `הסכם`→`agreement` / `חשבונית`→`invoice`; `time=` present and offset-aware; `none` → no
  INFO line.
- **unit** `test_main_turn_tools.py`: a godfather/admin conversational turn is built with
  `query_ledger_events` attached and **without** `capture_ledger_event` / `LEDGER_EVENT_TOOL`;
  `_call_openai_ledger_followup_api`, the bugfix-018 guard symbol, and the protocol-violation
  branch are gone (import-level / attribute assertions).
- **integration** `test_ledger_client_resolution_routing.py`: a real `textMessage` webhook
  JSON for an exact-match `הסכם` → router → (OpenAI stubbed: reply, then a `complete`
  recognition verdict) → exactly one `LedgerEvent` file with the resolved name, linked from
  the completing `Message`, no `_call_openai_ledger_followup_api` invocation.
- **billed** (acceptance): US1 (mechanism move), US2 (`חשבונית` synchronous), US3
  (regression guard — 0 spurious events, reply intact). Real OpenAI.
- No unit test asserts `schema_version`'s value (CLAUDE.md rule).
