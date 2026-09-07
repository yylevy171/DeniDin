# Feature Specification: Post-Turn Ledger Capture with Mandatory Client Resolution

**Feature Branch**: `feature/069-mandatory-client-resolution-before-ledger-event`
**Feature ID**: 069-mandatory-client-resolution-before-ledger-event
**Priority**: P2
**Created**: 2026-08-30
**Status**: Re-specified 2026-09-01 (architecture redesign). `speckit.clarify` / `speckit.plan` / `speckit.tasks` / `speckit.analyze` complete. Acceptance scenarios re-locked 2026-09-02 (US2 → Morning combo doc type 320 + VAT-included; US3 → in-conversation combo-doc create yields one `חשבונית` event; US7 → +7d exact-match; institution-slip story removed; single-ask + proactive store-anyway). Next: `speckit.implement`.

**Input** — User direction (2026-08-30 objective, materially redesigned 2026-09-01):

> **Original objective (2026-08-30):** unite the client name across domains. Morning is the
> source of truth. Whenever the ledger creates an event — an agreement, a deposit, or a
> Morning doc — the client MUST resolve to an EXISTING Morning client name, via the same
> resolve / disambiguate / create-new flow Morning document creation already uses, without
> losing the original goal.

> **Redesign (2026-09-01):** "the whole mechanism is wrong. ledger capturing yes or no
> should come LAST, not first. Like a finally code block." Ledger capture becomes a
> post-turn step, external to message handling — "more like a logging mechanism which is
> external to the actual message handling and processing." "capture ledger is stupid - it
> writes the data that was given. the client resolve is part of the preceding conversation,
> meaning that until a client is resolved no 'complete event' is achieved, so inherently no
> ledger capture is triggered." "the ledgerer is not completely dumb, it still needs to
> generate some id's, update the session message, etc. - it just doesn't have to go back and
> resolve anything." "scope - include: mechanism move + morning 'creates' + mandatory client
> for agreements, deposits, and morning docs."

**Compliance**: CONSTITUTION.md §I–III, §V, §XVII (no env vars, Israel-local timestamps,
integration tests as real E2E, no mocking of internal components, no monkey-patching),
§XVIII (no silent one-shot external handshake / no degraded write). METHODOLOGY.md §I, II,
VI, VIII, IX, X, XIX, XXI (spec-first, mandatory user stories, TDD-as-acceptance, glossary,
technology choices, requirement IDs, UX-wording approval gate, tool-boundary constitution
rules). Ledger `CURRENT_SCHEMA_VERSION` is **not** bumped by this feature (stays 2) — see
CLAUDE.md "LEDGER SCHEMA VERSION BUMPS ARE HUMAN-ONLY".

---

## Overview

This feature makes two intertwined changes, plus one scope extension:

1. **Mechanism move — ledger capture becomes a post-turn recognition step.** Today the
   conversational model is handed a `capture_ledger_event` local tool on every
   godfather/admin text turn; it emits a `function_call`; code then makes a *second* OpenAI
   round-trip to recover the operator's actual reply, guarded by a suppression check and a
   protocol-violation check. All of that is removed. Instead, **after** the operator reply
   is finalized and sent, one dedicated text-only OpenAI call ("the recognition call") asks
   a single question — *did a complete ledger event finish this round? if so, here is its
   data, mapped to the ledger schema* — and a mechanical code-side "ledgerer" persists what
   it returns. The recognition call's output is never shown to the operator and triggers no
   follow-up round-trip. This is the existing `capture_ledger_events_from_text` pattern
   (already used for OCR'd media text) generalized to every turn's full context.

2. **Mandatory client resolution — an event is not "complete" until its client resolves.**
   A `הסכם` (fee agreement), `בנק` (bank deposit), or `חשבונית` (Morning document) event
   has a per-type set of **mandatory fields** that MUST all be present before the event is
   "complete" and therefore before anything is persisted. `client_name` — resolved to an
   **exact** existing Morning client name — is mandatory for all three. Resolution is
   **ordinary conversation** driven by constitution guidance, using the same
   resolve / disambiguate / create-new flow Morning document creation already uses — never a
   code state machine, never anything the recognition call or the ledgerer does. An
   unresolved client simply means the event is not yet complete, so the recognition call
   emits nothing and the conversation continues. **Optional fields** that the operator
   provided (or that were extracted from an image/document) at any point MUST be retained
   through the whole conversation so that, when the event does complete, every one of them
   reaches the persisted record.

3. **Morning "creates" are in scope.** A `create_*` Morning MCP call that succeeds inside a
   conversation is itself a complete event — its client is resolved by construction (Morning
   would not have created the document otherwise) — and is captured **synchronously** by the
   recognition call this turn. Today those turns are suppressed and only Feature 025's
   background reconciliation sweep catches the document later, from Morning's side. Feature
   025's sweep is **still required** for documents created directly in Morning (by hand, or
   by Morning automation) and MUST dedup against what this feature writes synchronously.

---

## Clarifications

### Session 2026-08-30 (`speckit.specify`) — retained where still valid

- Q: What counts as "resolved"? → A: an **exact** Morning client-name match (post-`add_client`
  if newly created). Not a fuzzy threshold; not a per-event operator confirmation on an
  already-exact match.
- Q: No-match / multiple-match behavior? → A: ask the operator; "create new" is always an
  explicit inline choice. No silent auto-pick.
- Q: Retroactive? → A: forward-only. Feature 065 owns the August 2026 `בנק` backfill.
- Q: For a `בנק` deposit, whose name must resolve? → A: the paying client. The slip
  account-holder / institution text is a hint only.
- Q: Enforcement location? → A: `runtime_constitution.md` guidance + the acceptance suite.
  **No** hard code-level rejection of an unresolved capture.

### Session 2026-08-31 (`speckit.clarify` / `speckit.plan`) — retained where still valid

- Ambiguous operator reply during disambiguation ("כן", something fitting neither branch):
  re-ask **once** as an explicit closed choice; never infer; capture nothing until clear.
- Operator can't/won't give a new client's email + phone: the model asks, **once** (no
  re-ask), the distinct closed question *"should I store this event without full client
  details, or not?"* — capture nothing until answered. The operator may also **proactively**
  elect store-anyway up front, in which case DeniDin honours it directly with **no**
  "are you sure?" confirmation. `store` → event persisted with the operator-stated name as
  free-text `client_name` + a fixed `[לקוח לא אומת במורנינג]` marker inside `description`; no
  Morning client created. `don't store` → nothing persisted; one INFO "declined by operator"
  log line. (Single-ask + proactive election locked 2026-09-02, superseding the earlier
  re-ask-once phrasing.)
- Payload fidelity: every acceptance scenario ending in a persisted `LedgerEvent` asserts
  **complete** fidelity against a committed per-fixture ground-truth manifest — exhaustive
  and exact, not a spot-checked subset; for media, verified in two hops (extraction, then
  post-detour persistence).
- Store-anyway marker: **no** new `LedgerEvent` field, **no** `CURRENT_SCHEMA_VERSION` bump
  — text inside the existing `description` field.
- **No feature flag, no new config key** (operator direction) — the feature ships
  unconditionally. Recorded as a deliberate departure from CLAUDE.md's "feature flags for
  new behavior" convention in `plan.md` Complexity Tracking.

### Session 2026-09-01 (architecture redesign — `speckit.specify` redone)

- Q: The whole entangled inline-tool mechanism (`_call_openai_ledger_followup_api`, the
  bugfix-018 MCP-suppression guard, the `>1 call` / unparseable-args protocol-violation
  machinery)? → A: **Deleted.** Ledger capture moves to a post-reply recognition call +
  a mechanical ledgerer. The two incidents the suppression guard protected against
  (2026-07-28 spurious capture from reading `list_invoices` output back; 2026-08-02
  field-filling reply misclassified mid-approval) are **structurally impossible** once there
  is no inline `capture_ledger_event` tool on the main turn.
- Q: Does the recognition step make its own OpenAI call? → A: **Yes.** One text-only call
  per godfather/admin turn, fired after the reply is sent. It is the **only** place
  prose → ledger-schema mapping happens (amounts to numbers, dates to ISO, fee components
  split into the `components` array, `source_type`/`event_subtype` chosen, `client_name` =
  the exact Morning name resolved earlier in the conversation, `reference`/`reference_hint`
  if a link was established via `query_ledger_events`). Its input includes this turn's
  Morning MCP tool calls **and their results** verbatim, so a `create_*` is recognized from
  the real Morning response, not re-derived from prose. Output never shown to the operator;
  no follow-up round-trip.
- Q: Where does partial / in-flight event state live before "complete" is decided? → A:
  **Nowhere new.** The in-flight event *is* the conversation. The session already persists
  every message and this turn's tool results; the recognition call assembles the complete
  picture from that context when it fires. No dedicated tracker, no sweep, no abandonment
  bookkeeping.
- Q: Per-type mandatory fields? → A (operator):
  - **`הסכם`**: `client_name` (resolved), event date, `description`, **and** (at least one
    fee component **OR** a number of hours). Per component: **either** `amount` > 0 **or**
    `percent`.
  - **`בנק`**: `client_name` (resolved), `txn_date`, `amount`, `description`, `vat_status`
    (always `כולל` unless the operator explicitly states otherwise — already code-enforced).
  - **`חשבונית`** (in-conversation create): `client_name` (resolved — guaranteed by the
    successful `create_*` call), `txn_date`, `event_subtype` (**= the document type — there
    is no `accounting_document_type` field**, verified in `ledger_event_manager.py`),
    `amount`, `accounting_document_display_number`.
  - **Generated-mandatory (produced by the ledgerer, not the AI or the conversation)**:
    `event_id`, `event_datetime`, `captured_at` — and, where applicable, `agreement_id` and
    `component_id` (exact generation responsibilities confirmed against current code in
    `speckit.plan`).
- Q: Optional-but-retained fields per type? → A (operator): everything else that maps to a
  `LedgerEvent` field, **except** the mandatory and conditional-mandatory ones above and
  except `agreement_id` (generated, never operator-provided). Notably `payer_name`
  (`הסכם`-only), per-component `trigger_condition` / `percent` / `percent_base` / `hours` /
  `hourly_rate`, `bank_number` / `bank_branch` / `bank_account` (`בנק`),
  `accounting_document_status` / `_status_code` / `_status_label` / `_payment_method`
  (`חשבונית`), and `reference` / `reference_hint` (all types — see next).
- Q: Where do `reference` / `reference_hint` and other linkage ids (supporting a later
  cancel/modify of an agreement, dup-detection for a deposit, a linked Morning document)
  come from now that there is no inline create tool? → A: **Determined in conversation by
  the AI**, which retains the ability to **search** ledger events (`query_ledger_events`
  stays attached to the main turn) but from now on **never creates** them inline. Both
  `reference` and `reference_hint` are **retain-if-provided for all source types** — if the
  AI established a link during the conversation, the recognition call carries it into the
  persisted event.
- Q: Recognition signal shape — dedicated post-reply call vs. structured output on the main
  turn? → A: **dedicated post-reply call.** Lowest blast radius; the reply is never
  entangled with the ledger schema; mirrors the existing `capture_ledger_events_from_text`.
- Q: Exact-match without a Morning call? → A: not possible without a cache. One
  `resolve_client_name` call per recognized event (a no-approval read tool), cached only for
  the current conversation. A durable cross-conversation cache is split out as **Feature
  072** (`specs/backlog/072-morning-client-name-cache/`).
- Q: Feature 025 dedup for in-conversation Morning creates? → A: 069's synchronous
  `חשבונית` write goes through the same persist path (`add_ledger_events_from_call` →
  `_ensure_accounting_document_cache()`), which keys on `accounting_document_display_number`
  (verified `ledger_event_manager.py:1163-1169`), so Feature 025's next sweep tick sees the
  display number as already known and skips it.
- Q: prod backfill gate for the synchronous `חשבונית` capture? → A: **none.** 069's
  synchronous capture only fires for documents DeniDin itself creates in a conversation,
  going forward — exactly the non-gap case. The historical gap (documents Morning already
  held) stays Feature 025's problem, still gated by `accounting_ledger_update_freq=0` in
  prod. 069's `חשבונית` capture ships active in prod with no config gate and no backfill
  dependency.

---

## Terminology Glossary

- **The recognition call** — one dedicated text-only OpenAI call made **after** the operator
  reply is finalized and sent, on every godfather/admin turn. Input: the conversation so
  far + the reply just sent + this turn's Morning MCP tool calls and results + the
  constitution's ledger section. Single job: decide whether a **complete** ledger event
  finished *this round*, and if so emit it already mapped to the `LedgerEvent` schema. Its
  output is never shown to the operator and produces no follow-up round-trip. Not a tool the
  conversational model elects — a separate, code-initiated extraction.
- **The ledgerer** — the mechanical, **zero-AI** code that consumes the recognition call's
  output: mints `event_id` / `event_datetime` / `captured_at` (and `agreement_id` /
  `component_id` where applicable), dedups, persists the immutable JSON, appends to the
  in-memory index, and updates `Message.ledger_event_ids` on the session. It never resolves
  a client, looks anything up in Morning or the ledger, or maps prose to fields.
- **Complete event** — a would-be `LedgerEvent` for which **every mandatory field of its
  `source_type`** (§Clarifications 2026-09-01) is present, including a `client_name`
  resolved to an exact Morning client name (or the store-anyway exception elected). Only a
  complete event is recognized and persisted. Completeness is a property of the
  **conversation**, read afresh by the recognition call each turn — not a stored state.
- **Resolved client / resolution** — a `client_name` that **exactly** matches a client
  currently stored in Morning (Green Invoice), reached either by matching an existing
  Morning client (confirmed via `resolve_client_name`) or by creating one via the existing
  `add_client` flow and then using that stored name verbatim. A fuzzy score, a "close
  enough" string, or an unconfirmed candidate is **not** resolved. Resolution is always a
  **sub-step**; the terminal step is persisting the ledger event.
- **The detour** — the client-resolution sub-conversation between DeniDin recognizing that
  an event is being described and that event becoming complete. May span several turns
  (relaying `resolve_client_name` candidates, disambiguation, requesting a new client's
  email + phone, the `add_client` approval turn). It is **ordinary conversation** — no
  dedicated pending state beyond the approval gates that already exist.
- **Store-anyway (unresolved capture)** — the single sanctioned exception to Morning
  resolution: after the operator declines to provide a new client's email + phone and then
  explicitly answers *store* to a **single** closed "store without full client details, or
  not?" question (no re-ask first) — or proactively asks to store without the contact
  details, which DeniDin honours directly with no "are you sure?" confirmation. The event is
  persisted with the operator-stated name as free-text `client_name` **plus a fixed
  `[לקוח לא אומת במורנינג]` marker inside `description`**; no Morning client is created; no
  new schema field, no `CURRENT_SCHEMA_VERSION` bump. Never a default, never inferred, never
  volunteered before the operator has declined the contact details or asked for it.
- **Slip name** — the account-holder / institution / "העברה מ-X" text OCR'd from a
  bank-deposit image. A *hint* toward the paying client, never the client identity itself.
- **Ledger event** — a structured `LedgerEvent` record (Feature 033), one immutable JSON
  file under `{data_root}/events/`. `source_type` values in scope: `הסכם` (fee agreement,
  incl. hours-log entries), `בנק` (bank deposit), and — new for this feature —
  in-conversation `חשבונית` (Morning document just created via a `create_*` MCP call).
- **Operator** — the godfather/admin WhatsApp user whose turn is being processed. Ledger
  capture, `query_ledger_events`, and the Morning client tools are already RBAC-gated to
  these roles.

## Technology Choices

No new technology, libraries, storage, or external services.

- **Recognition call** — reuses the `capture_ledger_events_from_text` pattern already in
  `AIHandler` (a separate text-only classification call over already-available text, using
  `LEDGER_EVENT_TOOL`'s schema + the constitution, whose output is never shown to the
  operator, with no follow-up round-trip). This feature generalizes it from "OCR'd media
  text only" to "every godfather/admin turn's full context (conversation + this turn's
  Morning MCP tool results)".
- **Removed** — `_call_openai_ledger_followup_api`, the bugfix-018 MCP-suppression guard
  (`morning_mcp_used_this_turn` → strip `capture_ledger_event` from follow-up tools), and
  the `protocol_violation = len(ledger_calls) > 1` / `single_call_unparseable` whole-turn
  rejection machinery. `LEDGER_EVENT_TOOL` is no longer attached to the main conversational
  turn as a callable tool.
- **Kept on the main turn** — `query_ledger_events` (read/search): how the conversational
  model establishes `reference` / `reference_hint` linkage.
- **Client resolution** — the existing "Resolving a client by name" constitution
  architecture (2026-08-12) and the Morning MCP `resolve_client_name` / `add_client` tools
  (with their `PendingApprovalManager` approval gates, Features 022/047), reused as-is. One
  `resolve_client_name` call per recognized event, conversation-scoped caching only, until
  Feature 072.
- **Media ledger path** — `MediaHandler`'s one-shot "extractor classification →
  `LedgerEventManager.add_ledger_events_from_call` directly" path (for any recognized
  `source_type`, no conversation / Morning tools / operator round-trip) is replaced by
  routing the extractor output + extracted text through the conversational `AIHandler`
  pipeline as a synthetic turn — the Feature 030 contact-card pattern — so client resolution
  and the post-turn recognition call run on the same machinery every typed turn uses. This
  covers `בנק` deposit slips, photographed `הסכם` agreements, and `docx` `הסכם` agreements.
  `pdf` fee agreements stay out of scope (see Feature 071 — `PDFExtractor` needs a
  single-call-extraction rewrite for reasons unrelated to this feature). The extractor's
  structured fields ride into that conversation's context verbatim (a transient "stash") so
  the recognition call copies exact values across a multi-turn detour rather than recalling
  them from prose.
- **`CURRENT_SCHEMA_VERSION`** — stays 2. No `LedgerEvent` field added. The store-anyway
  marker is text in the existing `description` field.

---

## User Scenarios & Testing *(mandatory)*

Full Given-When-Then acceptance criteria, routing/dispatch notes, and per-story test
requirements are in **`user-stories.md`** (separate file — spec approval is BLOCKED without
it). Quick reference:

| # | Story | Priority | Tier |
|---|-------|----------|------|
| **US1** | **Mechanism move / decoupling.** A godfather turn that describes a complete fee agreement with an exact-match client: the operator gets the normal conversational reply, and — decoupled, after the reply — the `הסכם` event is recognized and persisted by the post-turn recognition call. No second reply round-trip, no inline tool. | **P1** | billed |
| **US2** | **Morning "create" captured synchronously.** Operator asks DeniDin to create a Morning **combo document** ("חשבונית מס/קבלה", type **320** — a paid invoice+receipt, **not** the unpaid type-305 plain tax invoice); `create_combo_document` succeeds; the post-turn recognition call captures the `חשבונית` event **this turn** from the real Morning response, with `vat_status` recording VAT as **included** and **no** VAT clarifying question anywhere in the transcript (type-320 carries VAT by definition; Morning enforces amount/VAT consistency on it). Feature 025's next reconciliation tick sees the display number as known and does **not** double-write. | **P1** | billed |
| **US3** | **Regression guard — no spurious capture / lost reply mid-MCP-flow.** Two shapes: (A) a turn that calls a Morning read tool (`list_invoices`) and reads the result back; (B) a short field-filling reply ("עבור ייעוץ") mid a **legitimate** `create_combo_document` approval flow. The reply is delivered intact and **no** ledger event is spuriously captured on the partial/read-back turn — and, for Shape B, the combo-document flow still completes normally and yields exactly **1** `חשבונית` event once the document is created (identical to US2). (The 2026-07-28 / 2026-08-02 incidents, now structurally impossible.) | **P1** | billed |
| **US4** | **FLAGSHIP — new-client fee agreement.** Typed `הסכם` naming a client with **no** Morning match → DeniDin runs the resolution detour (ask full name + email + phone → `add_client` approval) → on completion the `הסכם` event is persisted with the resolved Morning name **and every fee component / date / subtype / payer_name from the original text**. | **P1** | billed |
| **US5** | **Ambiguous client name on a fee agreement** — one partial match, or 2+ partial matches: DeniDin lists candidate(s) **and** offers "create new"; captures nothing until the operator picks; then persists with the chosen resolved name. Covers **5a** 1 partial match, **5b** 2+ partial matches. | **P1** | billed |
| **US6** | **Exact-match client resolves silently** — a source naming a client that already exactly matches Morning: **no** extra operator question, no measurable increase in turns-to-capture. (Anti-over-prompt guard.) | **P2** | billed |
| **US7** | **Bank-deposit image, client resolution.** Deposit slip image → DeniDin routes it into the conversational pipeline → (for a non-exact name) resolution detour → `בנק` event persisted with the resolved client **+ `amount`, `txn_date`, and `bank_number` / `bank_branch` / `bank_account` from the slip**. Covers **7a** 0 matches, **7b** 1 partial match, **7c** 2+ partial matches, **7d** exact match (no question, no new client — image analog of US6). | **P1** | expensive |
| **US8** | **Operator won't provide email/phone** — DeniDin asks the explicit closed choice **once** (no re-ask): **store-anyway** (free-text name + `[לקוח לא אומת במורנינג]` in `description`, no client created, all other fields still manifest-exact) or **don't-store** (INFO "declined by operator" log line, nothing persisted). Also covers the operator **proactively** electing store-anyway with no "are you sure?" confirmation. | **P3** | billed |
| **US9** | **Photographed multi-component fee agreement** (`הסכם` **image**), non-exact client → same resolution detour → `הסכם` event captured with **every fee component** from the page + the resolved client (two-hop fidelity). | **P2** | expensive |
| **US10** | **`docx` multi-component fee agreement** (`הסכם` **document**), non-exact client → routed into the conversational pipeline → same resolution detour → `הסכם` event captured with **every fee component** + the resolved client (two-hop fidelity). | **P2** | billed |

**US7 is the single most likely real-world path and MUST have end-to-end acceptance coverage
for all three match-count variations 7a/7b/7c** (user, 2026-08-30); **7d** (exact match) is
the silent-path guard on the image side.

### Edge Cases

- **Operator abandons the detour** (never resolves the client / never answers a closed
  question): the event never becomes complete, so the recognition call never emits it and
  nothing is persisted — by design, not an error path. There is no partial record and no
  abandonment log line; the conversation simply moved on. (Consistent with "a missed
  capture is cheaper than a false one".)
- **Operator declines email/phone for a new client**: DeniDin asks the closed "store without
  full client details, or not?" question **once** (no re-ask first). The operator may also
  proactively elect store-anyway, honoured directly with no "are you sure?" confirmation.
  *Store* → event persisted with the free-text name + `[לקוח לא אומת במורנינג]` marker in
  `description` + all other fields manifest-exact. *Don't store* → nothing persisted, one
  INFO "declined by operator" line.
- **Ambiguous reply during disambiguation** (bare "כן", unrelated text): DeniDin re-asks
  once as an explicit closed choice; a second still-ambiguous reply is abandonment (nothing
  persisted).
- **Multiple ledger events in one message** (e.g. two separate agreements): each event's
  client resolves independently; the recognition call emits an event the moment *that*
  event's own client is resolved and its mandatory fields are complete — so one message can
  produce a partial set of captures across several turns plus an outstanding question.
- **Correction to an arrangement already resolved earlier in the same conversation**
  (captured as a fresh event, e.g. `יצירה`): the previously-resolved exact name is reused;
  no second `resolve_client_name` call.
- **`הסכם` with a distinct `payer_name`** (an insurer / union routing payment): only
  `client_name` must resolve to Morning. `payer_name` stays free text, not gated.
- **Morning MCP tunnel unavailable** when a deposit/agreement needs resolution: resolution
  cannot complete → the event never becomes complete → nothing is captured with a guessed
  name; the operator is told the client could not be verified and to retry (CONSTITUTION
  §XVIII — no silent degraded write).
- **`create_*` succeeds but the reply / recognition call then fails**: the Morning document
  exists but no `חשבונית` event is written this turn. Feature 025's reconciliation sweep is
  the backstop — it will pick the document up on a later tick (this is exactly the case 025
  still exists for). No double-write risk because 069 wrote nothing.
- **Group chat**: resolution questions are asked in the same chat the event came from; RBAC
  is already resolved to the most-permissive member (Feature 039) and is unchanged.
- **Slip names the debited account of an unrelated party** (the audit's actual failure):
  slip name is a hint only; if it does not tie to a real Morning client the operator is
  asked; the raw slip string is never persisted as `client_name`.

## Requirements *(mandatory)*

### Functional Requirements — mechanism move

- **FR-069-001**: Ledger capture MUST occur as a **post-turn step**, after the operator
  reply for that turn has been finalized and sent — never as a tool the conversational model
  invokes during reply generation. The `capture_ledger_event` / `LEDGER_EVENT_TOOL` local
  tool MUST NOT be attached to the main conversational turn.
- **FR-069-002**: The post-turn step MUST run exactly one dedicated text-only OpenAI call
  (the recognition call) per godfather/admin turn, whose input is the conversation so far,
  the reply just sent, this turn's Morning MCP tool calls **and their results** verbatim,
  and the constitution's ledger section. Its output MUST NOT be shown to the operator and
  MUST NOT trigger a follow-up OpenAI round-trip.
- **FR-069-003**: The recognition call MUST answer a single question — *did a complete
  ledger event finish this round?* — and, when yes, return that event's data **already
  mapped to the `LedgerEvent` schema** (normalized amounts, ISO dates, fee components split
  into the components array, `source_type` / `event_subtype`, the resolved `client_name`,
  and any `reference` / `reference_hint` established in the conversation). When no, it
  returns nothing and nothing is persisted.
- **FR-069-004**: The "ledgerer" code path that consumes the recognition call's output MUST
  make **no** OpenAI call and MUST NOT resolve a client, query Morning, or query the ledger.
  It is limited to: generating `event_id` / `event_datetime` / `captured_at` (and
  `agreement_id` / `component_id` where applicable), deduplication, persisting the immutable
  JSON, appending to the in-memory index, and updating `Message.ledger_event_ids`.
- **FR-069-005**: `_call_openai_ledger_followup_api`, the bugfix-018 MCP-suppression guard,
  and the `>1 call` / unparseable-args whole-turn protocol-violation machinery MUST be
  removed. The behaviors they protected (no spurious capture from a model reading Morning
  read-tool output back into itself; no lost reply when a function_call and a message
  compete; no 400 on truncated tool args) MUST instead hold by construction — there is no
  inline ledger tool on the main turn to misfire — and MUST be covered by acceptance
  scenario US3.
- **FR-069-006**: The operator's normal conversational reply MUST always be produced and is
  fully decoupled from ledger capture — a recognition-call failure, a Morning-tunnel outage
  during resolution, or a "no complete event" result MUST never affect the reply the
  operator receives.
- **FR-069-007**: No dedicated persistent or in-memory structure is introduced to hold
  in-flight / partial event state. The recognition call derives completeness from the
  session and this turn's tool results each time it runs.
- **FR-069-008**: `query_ledger_events` (read/search) remains attached to the main
  conversational turn for godfather/admin. It is the only ledger tool the conversational
  model may call; it never creates or mutates events.

### Functional Requirements — mandatory client resolution & the "complete event" contract

- **FR-069-010**: A `הסכם` event MUST NOT be persisted until its mandatory fields are all
  present: `client_name` resolved to an exact Morning client (matched or newly created via
  `add_client`) **or** the store-anyway exception (FR-069-033) elected; event date;
  `description`; and at least one fee component OR a number of hours. Per component: `amount`
  > 0 OR `percent`. This applies regardless of where the client name came from — the
  triggering message, an image, a `docx`, or earlier in the same conversation.
- **FR-069-011**: A `בנק` event MUST NOT be persisted until its mandatory fields are all
  present: `client_name` resolved to an exact Morning client (or store-anyway elected);
  `txn_date`; `amount`; `description`; `vat_status` (defaulted to `כולל`, code-enforced,
  unless the operator explicitly states otherwise). The slip name is a hint only.
- **FR-069-012**: A `חשבונית` event (in-conversation Morning-document creation) MUST be
  persisted synchronously by the recognition call on the turn a `create_*` Morning MCP call
  succeeds. Its mandatory fields — `client_name` (resolved by construction), `txn_date`,
  `event_subtype` (the document type; there is no `accounting_document_type` field),
  `amount`, `accounting_document_display_number` — are taken from the real Morning response,
  not re-derived from prose.
- **FR-069-013**: Client resolution for ledger events MUST follow the **same** flow already
  defined for Morning document creation ("Resolving a client by name",
  `runtime_constitution.md`), driven as ordinary conversation by constitution guidance —
  never a code state machine, never anything the recognition call or the ledgerer performs:
  - exact Morning match → use that name verbatim, no operator question;
  - exactly one non-exact candidate → tell the operator the candidate **and** offer to
    create a new client; wait for their choice;
  - two or more candidates → list them **and** offer to create new; wait for their choice;
  - no match → the new-client sub-step (FR-069-014).
  A client already resolved earlier in the same conversation is reused as-is (no second
  `resolve_client_name` call).
- **FR-069-014**: The new-client sub-step: DeniDin asks the operator for the client's **full
  name** (message/slip text is a hint only), **email**, and **phone** — all three required —
  then runs `add_client` (its own approval turn), then uses the stored Morning name verbatim.
  No partial/degraded Morning client record and no placeholder `client_name` is ever written.
- **FR-069-015**: Exactly one `resolve_client_name` call is made per recognized event
  (a no-approval Morning read tool), cached only for the current conversation. A durable
  cross-conversation cache is out of scope (Feature 072).
- **FR-069-016**: When one message yields multiple ledger events, each event's `client_name`
  resolves independently; the recognition call emits an event as soon as that event's own
  mandatory fields (including its client) are complete, regardless of sibling events still
  pending.
- **FR-069-017**: `הסכם` `payer_name` is NOT subject to the resolution gate and remains free
  text.
- **FR-069-018**: If, during disambiguation, the operator's reply fits neither an offered
  candidate nor "create new" (bare "כן", an unrelated sentence), DeniDin MUST re-ask
  **once** as an explicit closed choice listing the options; MUST NOT infer a branch;
  captures nothing until the reply clearly selects. A second still-ambiguous reply is
  abandonment (nothing persisted).
- **FR-069-019**: *(Withdrawn 2026-09-02 — folded into FR-069-013's generic zero-match /
  ambiguous resolution flow and the "slip names the debited account of an unrelated party"
  edge case. A `בנק` slip that does not clearly name a resolvable client is just the no-match
  / hint-only path: the slip name is a hint, DeniDin asks who the client is, and captures
  nothing until it resolves — no separate institution-specific requirement or user story.)*

### Functional Requirements — field retention & fidelity

- **FR-069-020**: Every optional field the operator provided, or that was extracted from an
  image/document, at **any** point in the conversation MUST be retained until the event
  completes and MUST reach the persisted record. The resolution detour (which may span
  several turns) MUST NOT cause any provided/extracted field to be lost — the `בנק` banking
  triplet and every `הסכם` fee component especially.
- **FR-069-021**: `reference` and `reference_hint` are retain-if-provided for **all**
  source types. They are established **in conversation** by the AI (which may
  `query_ledger_events` to find the related prior event); the recognition call carries what
  the conversation established into the persisted event. The ledgerer does **not** resolve
  or look up a reference.
- **FR-069-022** *(full-payload fidelity — CRITICAL, deliberately non-trivial to verify)*:
  Every acceptance scenario that ends in a persisted `LedgerEvent` MUST assert **complete**
  payload fidelity against a committed per-fixture ground-truth manifest:
  - each fixture ships a manifest listing the full set of fields a careful reader would
    identify in it, each with its expected *normalized* persisted value;
  - the test asserts the persisted event matches the manifest **exhaustively and exactly**:
    (a) every manifested field equals its expected value; (b) the *set* of populated event
    fields equals the manifest's set — no manifested field left empty (silent drop), no
    unmanifested field spuriously filled (hallucination). A subset / "contains" assertion is
    NOT sufficient;
  - for image and `docx` sources, fidelity is verified in **two hops** — the extractor
    output equals the source manifest, **and** the persisted event equals the extractor
    output — so a value lost *during the resolution detour* is distinguishable from one
    never extracted;
  - this applies to the store-anyway capture (FR-069-033) too: everything except a
    Morning-resolved `client_name` must still be present and manifest-exact.

### Functional Requirements — Morning "creates" & Feature 025

- **FR-069-025**: 069's synchronous `חשבונית` write MUST go through the existing persist
  path (`add_ledger_events_from_call` → `_ensure_accounting_document_cache()`), so the
  `accounting_document_display_number` it records is visible to Feature 025's in-memory
  tri-state dedup cache.
- **FR-069-026**: Feature 025's reconciliation sweep MUST treat a document already captured
  synchronously by 069 as a **duplicate** (skip, no second file) on its next tick, keyed on
  `accounting_document_display_number`.
- **FR-069-027**: Feature 025's sweep remains required and unchanged for Morning documents
  created **outside** a DeniDin conversation (by hand in Morning, or by Morning automation).
  This feature does not remove or gate it.
- **FR-069-028**: 069's synchronous `חשבונית` capture has **no** config gate and **no**
  backfill dependency — it is forward-only and conversation-sourced, so it introduces no
  historical gap. It ships active in `dev` and `prod`. (Feature 025's `prod`
  `accounting_ledger_update_freq=0` backfill gate is unaffected and still owns the
  pre-existing-documents gap.)

### Functional Requirements — store-anyway & logging

- **FR-069-033**: When client resolution cannot complete because the operator does not
  provide a new client's email + phone, DeniDin MUST ask, **once** (no re-ask first), as a
  **distinct closed question**, *"should I store this event without full client details, or
  not?"*. Nothing is persisted until answered. The operator MAY instead **proactively** ask
  to store without the contact details; DeniDin MUST honour that directly, with **no**
  "are you sure?" / "בטוח?" confirmation turn. DeniDin MUST NOT volunteer store-anyway before
  the operator has either declined the contact details or proactively asked for it.
- **FR-069-034**: If the operator answers FR-069-033's question with *store* — or proactively
  elected store-anyway per FR-069-033 — the event IS persisted: `client_name` = the
  operator-stated name as free text, **plus a fixed `[לקוח לא אומת במורנינג]` marker inside
  the existing `description` field** (no new schema field, no `CURRENT_SCHEMA_VERSION` bump).
  No Morning client is created. All other provided/extracted fields are persisted per
  FR-069-020. This is the only sanctioned way a ledger event is written with an unresolved
  client.
- **FR-069-035**: If the operator answers *don't store* — or the event otherwise never
  completes — **no** ledger event is persisted for that recognition. App-log traceability:
  - the recognition call emitting a complete event → one INFO **"recognized"** line
    (source type, session id, chat id, Israel-local timestamp);
  - a successful persist → one INFO **"written"** line (same fields + the persisted
    `event_id`);
  - an explicit *don't store* → one INFO **"declined by operator"** line (source type,
    stated name, reason);
  - a "no complete event this round" result → no line (or DEBUG only).
  No extra WhatsApp message beyond the normal conversation. Exact line formats:
  `data-model.md §3` / `contracts/recognition-and-logging.md`.

### Functional Requirements — constitution & enforcement

- **FR-069-040**: The enforcement mechanism is `runtime_constitution.md` guidance plus the
  acceptance suite. There is **NO** hard code-level rejection in `LedgerEventManager` /
  `AIHandler` of a capture whose `client_name` is unresolved.
- **FR-069-041**: `runtime_constitution.md`'s "Ledger Event Recognition" section MUST be
  rewritten for the new architecture (**UX-wording — METHODOLOGY §XIX HARD STOP for operator
  approval before implementing**): it must state (a) that ledger capture is a post-turn
  recognition step, not something the conversational model does inline; (b) the per-type
  mandatory-field contract and the "complete event" definition; (c) the mandatory
  client-resolution rule and that it is resolved by ordinary conversation using the
  "Resolving a client by name" flow; (d) the store-anyway exception and its exact marker
  phrase; (e) when the gate does NOT apply (`payer_name`; ambiguity resolved by asking not
  guessing). It MUST cross-reference **bidirectionally** with "Resolving a client by name",
  and out-of-scope notes MUST be added to the "Reminder Management" and "Invoice Management"
  sections, per METHODOLOGY §XXI. Guidance aimed at the old inline tool (calling
  `capture_ledger_event` N times, the components-array workaround) MUST be removed.
- **FR-069-042**: The feature is forward-only. Existing `LedgerEvent` files are NOT migrated
  or re-resolved (Feature 065 owns the August 2026 `בנק` backfill).
- **FR-069-043**: Future event-creating flows — Bit/PayBox transfers (Feature 066), the
  screenshot→action flow (2026-08-29 item 1) — inherit this design by construction: they
  produce conversation, and the same post-turn recognition call + mandatory-field contract
  apply. This spec does not implement them; it requires only that the constitution guidance
  be written to cover any `הסכם` / `בנק` / `חשבונית` recognition regardless of entry point.

### Functional Requirements — media routing

- **FR-069-045**: `MediaHandler` MUST stop persisting recognized ledger captures directly
  (`add_ledger_events_from_call` straight from one-shot extractor classification). Instead,
  for a media source classified as a ledger-relevant document — `בנק` deposit slip,
  photographed `הסכם` agreement, or `docx` `הסכם` agreement — it MUST route the extractor
  output + extracted text into the conversational `AIHandler` pipeline as a synthetic turn
  (the Feature 030 contact-card pattern), so client resolution and the post-turn recognition
  call run on the same machinery as a typed turn.
- **FR-069-046**: The extractor's structured fields (amount / deposit date / bank triplet /
  slip name for `בנק`; every fee component / date / subtype / `payer_name` for `הסכם`) MUST
  be carried verbatim into that synthetic conversation's context as a transient stash, so
  the recognition call copies exact values across the resolution detour (FR-069-020 /
  FR-069-022). The stash lives only for that conversation; it is never written to disk.
- **FR-069-047**: `pdf` fee agreements are **out of scope** — `PDFExtractor` needs a
  single-call-extraction rewrite tracked as **Feature 071**
  (`specs/backlog/071-pdf-single-call-extraction/`), which will route PDF into this same
  path once landed. Per `bugfix-028`, a `docx` (like a `pdf`) is always `הסכם` or unknown,
  never `בנק`.

### Key Entities

- **LedgerEvent** (existing, Feature 033) — **persisted schema unchanged by this feature.**
  The change is *how* one is produced (post-turn recognition call → mechanical ledgerer,
  not an inline tool + follow-up round-trip) and a *precondition* for writing one (all
  mandatory fields for the `source_type` present, including a resolved Morning
  `client_name`, unless store-anyway was elected — in which case the
  `[לקוח לא אומת במורנינג]` marker is text in the existing `description` field).
- **Morning client** (existing, Green Invoice) — source of truth for client identity.
  Reached via `resolve_client_name` / `add_client`.
- **Recognition-call output** (new, transient — not persisted) — the schema-mapped event
  data the recognition call returns for a complete event, consumed once by the ledgerer.
- **Media-ledger extraction stash** (new, transient — not persisted) — the structured
  fields an extractor read from a media source, carried verbatim into the synthetic
  conversational turn `MediaHandler` now routes media captures through. Lives only for that
  conversation.

## Success Criteria *(mandatory)*

- **SC-001**: Across the acceptance suite, **100%** of newly captured `הסכם` / `בנק` /
  `חשבונית` events either (a) have a `client_name` that exactly matches an existing Morning
  client at capture time, or (b) carry the `[לקוח לא אומת במורנינג]` marker in `description`
  from an operator-elected store-anyway. **0** captures with a raw-OCR fragment, institution
  name, or debited-account-holder name as `client_name` without that marker.
- **SC-002**: Whenever a captured event's client was new, a corresponding Morning client
  record provably exists (created via `add_client`) before the event file is written.
- **SC-003**: For a source naming a client that already exactly matches Morning, **no**
  additional operator question is asked — no measurable increase in turns-to-capture versus
  today.
- **SC-004**: After a resolution detour of one or more turns, the originally-recognized
  event is persisted with **every** provided/extracted detail in **every** acceptance
  scenario that ends in a persisted event — verified by exhaustive manifest match
  (FR-069-022), not a subset check. Target: **0** manifested fields dropped, **0**
  unmanifested fields hallucinated, suite-wide.
- **SC-005**: When an event never completes (abandon, "don't store", tunnel down), **0**
  ledger events are persisted for that recognition. An explicit "don't store" leaves one
  INFO "declined by operator" line; a recognized complete event that is then written leaves
  a "recognized" + "written" pair.
- **SC-006**: When the operator explicitly elects store-anyway, exactly **1** ledger event
  is persisted, carrying the operator-stated name as free-text `client_name` **and** the
  `[לקוח לא אומת במורנינג]` marker — and **no** Morning client was created.
- **SC-007**: The 2026-07-28 and 2026-08-02 incident shapes (US3) produce **0** spurious
  ledger events and deliver the operator's reply intact, with the inline
  `capture_ledger_event` tool absent from the main turn.
- **SC-008**: A Morning document created in a DeniDin conversation produces exactly **1**
  `חשבונית` ledger event (written synchronously that turn), and Feature 025's next
  reconciliation tick writes **0** additional files for that display number.
- **SC-009**: The operator's conversational reply is produced in **100%** of turns
  regardless of recognition-call outcome — a forced recognition-call failure in a test
  changes **0** bytes of the reply the operator receives.

## Assumptions

1. The existing "Resolving a client by name" constitution architecture and the
   `resolve_client_name` / `add_client` Morning MCP tools (with their `PendingApprovalManager`
   approval gates) are correct and reused as-is. This feature adds a *trigger condition* and
   moves *where* capture happens — not a new resolution mechanism.
2. "Resolved" means an **exact** Morning client-name match (after `add_client` if newly
   created) — not a fuzzy threshold, not a per-event operator confirmation on an exact match.
3. A `create_*` Morning MCP call that returns success has, by construction, resolved its
   client to a real Morning client — so an in-conversation `חשבונית` event's client is
   resolved without a separate `resolve_client_name` call.
4. `חשבונית` events created **outside** a conversation stay Feature 025's responsibility;
   069 only needs its synchronous writes to be dedup-visible to 025.
5. Ledger capture, `query_ledger_events`, and the Morning client tools are already
   RBAC-gated to godfather/admin; this feature does not touch RBAC.
6. Forward-only. Feature 065 owns the August 2026 `בנק` backfill.
7. The `capture_ledger_events_from_text` pattern (separate text-only classification call,
   output never shown to the operator, no follow-up) is sound and is the basis for the
   generalized recognition call.
8. `docx` `הסכם` agreements route into the conversational pipeline via `MediaHandler` (no
   new recognition call added to `DOCXExtractor` — recognition now happens once, post-turn,
   for every medium). `pdf` agreements wait for Feature 071.

## Dependencies

- **Feature 033** (`LedgerEventManager`, the persist path) — the write path being moved and
  gated.
- **Feature 024** (Ledger Event Recognition constitution rules) — the section being
  rewritten.
- **Feature 025** (Morning-sourced ledger events / reconciliation sweep) — must dedup
  against 069's synchronous `חשבונית` writes; stays the backstop for out-of-conversation
  documents.
- **Feature 022/047** (`PendingApprovalManager`, approval buttons) — the `add_client`
  approval UX reused during the detour.
- **Feature 030** (contact-card synthetic-turn routing) — the pattern `MediaHandler` now
  uses for media ledger captures.
- **Feature 039** (group RBAC resolution) — unchanged; resolution questions asked in the
  originating chat.
- **Morning MCP integration** — `resolve_client_name` / `add_client` / `create_*` over the
  ngrok tunnel.
- **Feature 065** (August ledger audit apply) — owns the retroactive `בנק` cleanup this
  feature deliberately does not duplicate.
- **Feature 072** (Morning client-name cache) — the durable optimization 069 ships without.
- Interacts with (does not implement): **Feature 066** (Bit/PayBox), 2026-08-29 item 1
  (screenshot→action).

## Out of Scope

- Any hard code-level rejection of unresolved captures.
- Retroactive migration / re-resolution of existing `LedgerEvent` files.
- Morning documents created outside a DeniDin conversation (Feature 025's sweep owns those;
  069 only guarantees dedup compatibility).
- Changes to `payer_name` handling.
- Any change to the persisted `LedgerEvent` schema or a `CURRENT_SCHEMA_VERSION` bump. The
  store-anyway marker is text in the existing `description` field.
- `pdf` fee-agreement extraction routing — **Feature 071**.
- A durable cross-conversation Morning client-name cache — **Feature 072**.
- Implementing Feature 066 or the screenshot→action flow.
- A code-side pre-filter that skips the recognition call on turns with no financial content
  (possible later optimization; not required here).

## References

- `specs/in-progress/069-.../spec.md` (this file), `user-stories.md`
- Feature 065 — August ledger audit (the motivating data)
- Feature 025 — `specs/done/v0.5.2/025-morning-sourced-ledger-events/`
- Feature 071 — `specs/backlog/071-pdf-single-call-extraction/`
- Feature 072 — `specs/backlog/072-morning-client-name-cache/`
- `config/runtime_constitution.md` — "Resolving a client by name", "Ledger Event Recognition"
- `apps/denidin-app/src/handlers/ai_handler.py` — `capture_ledger_events_from_text`
  (the pattern), `_handle_ledger_event_capture` / `_call_openai_ledger_followup_api` /
  the bugfix-018 guard (being removed)
- `apps/denidin-app/src/managers/ledger_event_manager.py` — `add_ledger_events_from_call`,
  `_ensure_accounting_document_cache` (dedup key = `accounting_document_display_number`)
- `.github/METHODOLOGY.md` §XIX (UX-wording approval gate), §XXI (tool boundaries)
