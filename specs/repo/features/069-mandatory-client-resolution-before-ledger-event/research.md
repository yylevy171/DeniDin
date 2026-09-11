# Phase 0 Research: Post-Turn Ledger Capture with Mandatory Client Resolution

**Feature**: 069-mandatory-client-resolution-before-ledger-event
**Date**: 2026-09-01 (re-done after the 2026-09-01 architecture redesign)
**Input**: [spec.md](./spec.md), [user-stories.md](./user-stories.md), [plan.md](./plan.md)

This document resolves every open design question the re-specified spec deferred to
`speckit.plan`, plus the code-level questions the redesign raises. Each item: **Decision →
Rationale → Alternatives rejected**. Human sign-offs are recorded in spec.md §Clarifications
(Sessions 2026-08-30, 2026-08-31, 2026-09-01).

> **Redesign note.** An earlier version of this file (2026-08-31) described a *narrowing* of
> the bugfix-018 MCP-suppression guard and an inline `record_unresolved_ledger_capture`
> function tool. The 2026-09-01 redesign **deletes** the inline `capture_ledger_event`
> mechanism entirely and moves ledger capture to a post-turn recognition step. R3 and R5
> below are rewritten accordingly; R9 is corrected (no new AI call is added to
> `DOCXExtractor`).

---

## R1 — The media ledger path (`בנק` deposit + `הסכם` agreement, image + `docx`): how it gains interactive client resolution

*Scope: `בנק` deposit images, image-based `הסכם` agreements, and `docx` `הסכם` agreements.
`pdf` agreements are **out of scope** — Feature 071 (`PDFExtractor` single-call rewrite).
"Media capture" below reads as "any media-sourced `הסכם`/`בנק`" unless a line is specifically
about banking fields.*

**Context.** Today the image ledger path is fully non-conversational:

```
imageMessage → _process_media_message → WhatsAppHandler.handle_media_message
  → MediaHandler.process_media_message
      → ImageExtractor.extract → _vision_extract (OCR + doc-type JSON)
          → AIHandler.capture_ledger_events_from_text(extracted_text)   # internal text-only classify
          → returns {"ledger_events": [ {capture_ledger_event args}, ... ], ...}
      → Step 10: for each → LedgerEventManager.add_ledger_events_from_call(...)   # persists immediately
      → Step 11: _store_media_turn(...)
  → handle_media_message sends the composed `summary` string
```

No `AIRequest`, no `AIHandler.get_response`, no Morning MCP tools, no operator round-trip —
`resolve_client_name` / `add_client` are structurally unreachable, and the recognized event
is persisted with whatever unreconciled name the OCR produced.

**Decision (human sign-off 2026-08-31; unchanged by the redesign).** When `MediaHandler`
classifies a media item as a `בנק` **or** `הסכם` ledger document, it does **not** call
`add_ledger_events_from_call`. It routes the item into the **conversational `AIHandler`
pipeline** as a synthetic turn — the same structural pattern Feature 030 uses to feed a
shared WhatsApp contact card into `_process_conversational_message` (vCard lines are framed
verbatim into `text_content`; the model reads them and proposes `add_client` exactly as from
typed text).

Concretely:

- `MediaHandler` builds a synthetic conversational turn whose `text_content` is a **framed
  Hebrew block containing the extractor's output verbatim** — the "stash", built by
  `build_ledger_stash_text(extracted_text, analysis, source_type, source_medium)` (see R2 for
  the exact shape). It hands this to the shared conversational path
  (`_process_conversational_message` / `get_response`), with the existing godfather/admin tool
  set (Morning MCP + `query_ledger_events`; **not** `capture_ledger_event` — that tool no
  longer exists on the main turn).
- The model, guided by the constitution (R4), runs `resolve_client_name` and asks whatever
  disambiguation / email+phone questions are needed. That question is the reply to the media
  item.
- The operator's follow-up replies arrive as ordinary `textMessage`s → the same shared path.
  The synthetic turn (with the verbatim stash) is already in session history, so the model
  completes resolution (`add_client` approval via the existing `PendingApprovalManager`) in
  the normal conversational way.
- **Capture happens post-turn, once, for every medium** — the same recognition call
  (`AIHandler.recognize_ledger_event`, R3/R5) that runs after every godfather/admin turn runs
  after the media synthetic turn and after the resolution follow-ups. When the event is
  finally complete (client resolved, all mandatory fields present), the recognition call
  returns `complete` with the mapped payload and the ledgerer persists it. There is **no**
  media-specific capture path and **no** new recognition call inside any extractor.
- `MediaHandler` still runs Step 11 (`_store_media_turn`) for the **media artifact + caption**
  so the file stays linked to the session; the synthetic turn's messages are persisted by
  `get_response`'s own `_finalize_response`.

**Wiring detail.** `MediaHandler` has `denidin_context.ai_handler` already
(`media_handler.py:57-61`). The synthetic turn's response needs the interactive-button
attach wiring that lives in `_process_conversational_message` (`denidin.py:~588-595`) and the
post-turn recognition hook. Both are shared by extracting a `denidin.py` helper
(`_run_post_turn_ledger_recognition(...)` + the existing send/attach block) that the typed
path and the media synthetic-turn path both call. Exact call-site split → `contracts/media-capture-routing.md`.

**Rationale.**
- Zero new resolution machinery — `resolve_client_name`, `add_client`,
  `PendingApprovalManager`, the typed-reply / button-tap resolution, and the multi-turn
  session history that carries context across a detour all already exist and are already
  exercised by the `הסכם` text path.
- `הסכם` and `בנק`, typed or media, now resolve clients and get captured through the
  *identical* code path — exactly the spec's "THE SAME PROCESS ALWAYS" intent.
- Payload fidelity is handled by R2 (the verbatim stash + the recognition call's mapping),
  not by this routing choice.

**Alternatives rejected.**
- **A dedicated `PendingLedgerResolutionManager` holding-state flow** (mirroring
  `PendingLocalToolApprovalManager`): a third per-chat pending state to reason about
  (ordering, button-tap dispatch, staleness — all re-implemented), a parallel resolution
  state machine duplicating what `get_response` + history already do, and — with R2's stash
  and the post-turn recognition call — **no** fidelity advantage.
- **Attaching tools directly to the vision call**: already tried and reverted for Feature 024
  (`image_extractor.py:~197-206`) — gpt-4o/-mini produce **zero** extraction text on a turn
  where they also call a tool, breaking the user-facing document summary.

---

## R2 — Full-payload fidelity across the detour (FR-069-020, FR-069-022, SC-004)

**Context.** After a multi-turn resolution detour, the persisted event must match a
hand-authored per-fixture manifest **exhaustively and bidirectionally** (no dropped field,
no hallucinated field), verified in **two hops** for media. Under the redesign the model
never re-emits a `capture_ledger_event` call — the **recognition call** does the prose→schema
mapping — but the fidelity risk is the same: the recognition call sees the whole
conversation, and any extracted field that never made it into the conversation text (or got
paraphrased away) can be silently lost.

**Decision.** Two mechanisms, unchanged in spirit from the 2026-08-31 design:

1. **A verbatim structured stash.** The media synthetic turn's `text_content` embeds every
   extracted field as an explicit, labelled block, e.g.:

   ```
   📸 התקבלה תמונת אסמכתת העברה בנקאית.

   --- טקסט שחולץ מהתמונה (מילה במילה) ---
   <extracted_text verbatim>

   --- פרטים מובנים שחולצו ---
   סכום: 6200
   מטבע: ILS
   תאריך הפקדה: 2026-08-27
   מספר בנק: 12
   מספר סניף: 345
   מספר חשבון: 678901
   שם על האסמכתא (רמז לזיהוי הלקוח בלבד): רונית בר
   מספר אסמכתא/אישור: 4457821
   ```

   Because the block is a persisted user message, it is in history for every subsequent turn
   **and** for the recognition call. The constitution (R4) tells the model to keep these
   values intact through the conversation; the recognition call is instructed to map them
   into the `LedgerEvent` schema **from the stash lines**, not by re-reading OCR prose or
   summarising. `📄` / "מסמך" framing replaces `📸` / "תמונה" for `source_medium="document"`;
   field ordering switches on `source_type` (banking triplet first for `בנק`; one line per
   fee component for `הסכם`). This is Feature 030's contract: transcribe, don't summarise.

2. **The recognition call maps once, deterministically.** It is the single place prose →
   `LedgerEvent` schema mapping happens (amounts → numbers, dates → ISO, fee components →
   `components` array, `source_type` / `event_subtype`, resolved `client_name`, `reference` /
   `reference_hint`). It runs with `LEDGER_EVENT_TOOL`'s schema so the output shape is fixed.

**Test strategy (informs `tasks.md` Acceptance phase — described, not coded, here):**

- **Per-fixture ground-truth manifest** (`fixtures/ledger_069/<name>.manifest.json`),
  committed, enumerating every field a careful human reader identifies with its **normalized
  expected persisted value** (`"8,000 ₪"` → `amount: 8000`; written/relative date → ISO;
  slip `"12-345/678901"` → `bank_number:"12"` / `bank_branch:"345"` / `bank_account:"678901"`;
  each component line; `event_subtype`; `payer_name` when present).
- **Fixtures MUST be deliberately detail-rich** (`user-stories.md` cross-cutting reqs): a
  one-amount `הסכם` fixture makes the assertion vacuous. Minimum: ≥3 components **or** an
  explicit date + subtype for `הסכם`; amount + date + all three banking numbers + a
  reference/confirmation number for each `בנק` slip.
- **Bidirectional assertion helper** (`tests/billed/` + `tests/expensive/` shared util,
  written in the Acceptance phase): given a persisted `LedgerEvent` dict and a manifest,
  assert (a) every manifest field == its expected value; (b) `set(non-null event fields
  relevant to source_type) == set(manifest fields)` — a manifested field left null is a
  **silent drop** (fail); a non-manifested field populated is a **hallucination** (fail).
  `event_id`, `event_datetime`, `captured_at`, `session_id`, `message_id`, `schema_version`,
  `reference_hint` and other provenance/bookkeeping fields are on a fixed ignore-list.
- **Two-hop for media (US7 incl. 7d, US9, US10):**
  - **Hop 1** — assert the extractor's output (`ImageExtractor.extract` / `DOCXExtractor`
    analysis, i.e. the stash values) == the fixture manifest. Isolates OCR/extraction.
  - **Hop 2** — assert the persisted `LedgerEvent` == the stash values (post-detour,
    post-recognition-call). Isolates "the detour or the recognition call dropped a field".
  A one-hop test cannot tell "never extracted" from "extracted then lost".
- **Store-anyway (US8, scenarios 2 and 6):** same exhaustive manifest match on all fields *except* `client_name`
  (operator free-text), *plus* an assertion that the marker phrase (R6) is a substring of
  `description`.

**Rationale.** Fidelity risk is inherent to "a model conveys the payload across a
conversation". The verbatim stash converts the model's job from *recall* to *transcription*;
the recognition call's fixed schema converts mapping from *ad-hoc* to *deterministic*; the
two-hop manifest assertion *proves* it per scenario.

**Alternatives rejected.**
- **Dispatch a structured payload out-of-band after resolution, bypassing the recognition
  call** — reintroduces the R1-rejected holding-state machine.
- **A post-capture reconciliation pass** that re-reads the image and patches dropped fields —
  a second vision call per deposit, and "patch an immutable event" is a Feature-033
  anti-pattern.

---

## R3 — The bugfix-018 MCP-suppression guard, the follow-up API, and the protocol-violation machinery: all DELETED

**Context (why the guard existed).** `_handle_ledger_event_capture` (bugfix-018) *suppressed*
a ledger capture on any turn where Morning MCP was used (`mcp_call` / `mcp_approval_request`
present), so that:

- **2026-07-28** — the model reading `list_invoices` output back to the operator would not
  *also* spuriously fire `capture_ledger_event` and lose its real reply behind the follow-up
  round-trip.
- **2026-08-02** — a two-word field-filling reply ("עבור ייעוץ") mid-`create_combo_document`
  approval would not be misclassified as a spurious capture.

The guard, plus `_call_openai_ledger_followup_api` (a second OpenAI round-trip to recover the
operator's real reply after an inline capture) and the `protocol_violation = len(ledger_calls) > 1`
/ `single_call_unparseable` whole-turn rejection, are **all artefacts of the inline
`capture_ledger_event` tool being entangled with the reply-producing turn**.

**Decision (2026-09-01 redesign, operator-locked — FR-069-005).** **Delete all of it.**
`capture_ledger_event` / `LEDGER_EVENT_TOOL` is removed from the main conversational turn.
There is no inline capture tool to misfire, so:

- The 2026-07-28 shape is structurally impossible — reading `list_invoices` output back is
  just a normal reply; the post-turn recognition call sees a read-only Morning question and
  returns `none`.
- The 2026-08-02 shape is structurally impossible — a field-filling reply mid-approval is
  just a normal turn; the recognition call sees an incomplete event and returns `none`.
- The reply is always produced by the main turn, independently of recognition — a forced
  recognition-call failure changes **zero bytes** of the reply (SC-009). No follow-up
  round-trip is needed because the recognition call never touches the reply.

**`query_ledger_events` stays** on the main turn (read/search only — FR-069-008). It never
created or mutated events, so none of the deleted machinery applied to it.

**This is US3.** The acceptance test drives both historical shapes and asserts: reply intact,
0 spurious events, and (structural assertion) no `capture_ledger_event` / `LEDGER_EVENT_TOOL`
in the main-turn tool list.

**Rationale.** The guard was a workaround for a mechanism the redesign removes. Keeping a
narrowed guard (the 2026-08-31 plan) would be maintaining a defence against a misfire that
can no longer happen, on a tool that no longer exists.

**Alternatives rejected.**
- **Narrow the suppression to document-mutating MCP calls** (the 2026-08-31 decision) —
  obsolete: there is no same-turn `capture_ledger_event` to suppress.
- **Keep `_call_openai_ledger_followup_api` for the media path** — the media path now routes
  through `get_response` like any turn and is captured post-turn; it needs no follow-up.

---

## R4 — Where the gate lives: constitution guidance, not code (FR-069-010, FR-069-040, FR-069-041)

**Decision.** No hard rejection is added to `LedgerEventManager` or the ledgerer for an
unresolved `client_name` (explicit user decision, 2026-08-30, reaffirmed in the redesign).
An unresolved client simply means the recognition call does not see a *complete* event and
returns `none`. Enforcement is:

1. **`runtime_constitution.md` guidance** — the "Ledger Event Recognition" section is
   **rewritten** (FR-069-041 — §XIX HARD STOP, drafted + approved during `speckit.implement`)
   to state:
   - **Recognition is post-turn, not an inline tool.** Remove all guidance aimed at the old
     inline `capture_ledger_event` tool (call it N times, the components-array workaround,
     the one-call-per-turn rule). The conversational model's only ledger tool is
     `query_ledger_events` (read/search).
   - **Per-type mandatory-field contract + "complete event" definition** (the tables in
     spec.md §Clarifications 2026-09-01 / plan.md §Summary): an event is complete only when
     every mandatory field for its type is present; the recognition step is what decides
     "complete".
   - **Mandatory client resolution** — before an `הסכם` / `בנק` / `חשבונית` event can be
     complete, the client MUST be resolved to an **exact** Morning name, following the
     *identical* steps as "Resolving a client by name" (exact → silent; one non-exact
     candidate → name it + offer create-new; 2+ → list + offer create-new; none →
     full name + email + phone → `add_client` → its own approval). A client resolved earlier
     in the same conversation is reused, no re-ask.
   - **Resolution is a sub-step, never the goal** — the terminal step is always the ledger
     event being captured with the resolved name **and every other extracted field** (keep
     the structured stash values intact — R2). Wording explicitly *not* "ends in create new
     client" (operator correction, 2026-08-31).
   - **Does NOT apply to**: `payer_name` (stays free text, FR-069-013 — `payer_name` may
     differ from `client_name`); `חשבונית` client (resolved by construction from the
     `create_*` call).
   - **Ambiguity is resolved by asking, never guessing** — re-ask once as a closed choice
     (R7); a bare "כן" / unrelated reply is never a branch selection.
   - **Store-anyway** (R6): only after the operator has been re-asked for email+phone and
     declined *again*, ask the distinct closed question "store without full client details,
     or not?"; never volunteer it earlier.
2. **Bidirectional cross-reference** (METHODOLOGY §XXI): "Resolving a client by name" gets a
   pointer that it also governs `הסכם` / `בנק` / `חשבונית` ledger captures; "Ledger Event
   Recognition" points back; "Reminder Management" and "Invoice Management" each get a
   one-line "ledger recognition is post-turn and out of scope for this section" note. Mirror
   the existing "a mid-flow disambiguation / email-phone answer is not itself a new ledger
   recognition" pattern (verify the existing wording still covers this cleanly and extend if
   not).
3. **The acceptance test suite** (billed/expensive, US1–US10) is the real backstop.

**Rationale.** Matches the codebase's established pattern (Ledger Event Recognition, Reminder
Management, Invoice Management are all constitution-guided, not code-gated) and the user's
explicit call. A hard code gate would be *wrong* for store-anyway (a legitimate unresolved
write) and for the tunnel-down case (nothing to reject — the model just can't resolve, and
CONSTITUTION §XVIII says: tell the operator, capture nothing).

**No feature flag** (2026-08-31 decision) — see R8.

---

## R5 — The recognition call's tri-state verdict + lifecycle breadcrumb logging (FR-069-035)

**Context.** FR-069-035 wants a durable record whenever a `הסכם` / `בנק` capture is
recognized, whenever one is written, and whenever the operator explicitly declines
store-anyway. An earlier design (a `PendingLedgerResolutionTracker` swept hourly by
`SessionCleanupThread` + a TTL config knob) was dropped 2026-08-31 as overkill for what is a
log line. The 2026-08-31 replacement used an inline `record_unresolved_ledger_capture`
function tool for the "declined" signal — **that contradicts the redesign's FR-069-008** ("`query_ledger_events`
… is the only ledger tool the conversational model may call").

**Decision (2026-09-01 redesign).** The recognition call returns a **tri-state verdict**, and
the ledgerer emits the breadcrumbs. No inline tool, no new state, no config, no module, no
sweep.

- **`recognize_ledger_event(...)` return shape** (transient — spec §Key Entities):
  - **`complete`** — `{verdict: "complete", event: {<LedgerEvent-schema-mapped fields>},
    trigger_message_id: <session message id>}`. `event` carries the resolved `client_name`,
    normalized amounts/dates, the `components` array for `הסכם`, `source_type` /
    `event_subtype`, and `reference` / `reference_hint` if established in conversation via
    `query_ledger_events`.
  - **`none`** — `{verdict: "none"}`. Nothing this round. No log line (DEBUG only).
  - **`declined`** — `{verdict: "declined", source_type: "<הסכם|בנק>", client_name_stated:
    "<operator free text>", reason: "declined_by_operator"}`. Emitted when the conversation
    shows the operator was offered store-anyway and explicitly refused.
- **The ledgerer's breadcrumbs** (`logger.info`, `now_local()` `time=` field):
  - On `complete`, before persist:
    `ledger capture recognized: type=<deposit|agreement> session=<id> chat=<id> time=<ISO>`
  - After a successful persist, one line per event:
    `ledger event written: type=<deposit|agreement> event_id=<id> session=<id> chat=<id> time=<ISO>`
  - On `declined`:
    `ledger capture declined by operator: type=<...> name=<client_name_stated!r> session=<id> reason=declined_by_operator time=<ISO>`
  - Exact line prefix/format is pinned in `data-model.md §3` / `contracts/recognition-and-logging.md`.

**Abandonment detection is operational, not coded.** A `recognized` line with no matching
`written` or `declined` line for the same `session` is a dropped capture — grep the log. On
the media path recognition is reliably logged (the recognition call runs post-turn every
turn). On the pure-text path a `הסכם` abandoned before it ever became complete leaves no
`recognized` line — accepted (user, 2026-08-31); a pre-recognition signal could be added
later if the gap ever matters.

**Rationale.** The tri-state verdict is the only shape consistent with FR-069-003 (complete →
mapped event), FR-069-035 (three distinct outcomes), and FR-069-008 (no inline ledger tool
for the "declined" signal). The breadcrumb pair gives free abandonment visibility on the path
where the multi-turn detour actually happens, at the cost of ~3 `logger.info` lines and no
new state/config/module/sweep.

**Alternatives rejected.**
- **`record_unresolved_ledger_capture` inline function tool** (2026-08-31 design) —
  contradicts FR-069-008; the redesign removes all inline ledger tools except the read-only
  `query_ledger_events`.
- **`PendingLedgerResolutionTracker` + hourly sweep + TTL config** — disproportionate; a
  module + config field + sweep pass to detect one edge.
- **Fold "declined" into the recognition call as a silent `none`** — loses the positive audit
  line FR-069-035 explicitly wants for an operator decline.

---

## R6 — The "client not resolved in Morning" marker (FR-069-033) — NO new field, NO schema bump

**Decision (human sign-off, 2026-08-31; unchanged).** The store-anyway marker is **free text
in the persisted event's existing `description` field** — a fixed Hebrew phrase the
constitution specifies: **`"[לקוח לא אומת במורנינג]"`** (bracketed so a test can assert it as
a stable substring and a human skimming the event file sees it).

- **No new `LedgerEvent` field.** The persisted `record` dict
  (`ledger_event_manager.py:~1079-1145`) is unchanged.
- **No `CURRENT_SCHEMA_VERSION` bump.** Stays **2**; `SCHEMA_VERSION_HISTORY` untouched;
  `_verify_schema_version_history()` unaffected (CLAUDE.md "LEDGER SCHEMA VERSION BUMPS ARE
  HUMAN-ONLY" — the human's decision here is explicitly *not to bump*).
- **No test asserts `schema_version`'s value** (CLAUDE.md, unchanged rule).
- Under the redesign the phrase is written **by the recognition call** into the `event`
  payload's `description` (the constitution's store-anyway guidance instructs it), alongside
  the operator's free-text `client_name`. The ledgerer persists `description` verbatim — no
  code change on the persistence side.

**Rationale.** The marker is human-and-test-readable provenance, not queryable structured
data (nothing filters events by resolution status — Feature 065 owns the retro audit).
`description` already exists, is already free text, is already on every event.

**Alternatives rejected.** A new `client_resolution` enum field (with or without a bump) —
still a schema change, still forces the bump conversation, no consumer needs it.

---

## R7 — Ambiguous disambiguation reply (FR-069-018)

**Decision.** Pure constitution guidance, no code. In the rewritten "Ledger Event
Recognition" section: *if, during client disambiguation, the operator's reply matches neither
an offered candidate nor "create new" (a bare "כן", an unrelated sentence), re-ask **once**
as an explicit closed choice that re-lists the candidates and the create-new option; the
recognition call returns `none`; infer nothing. A second still-ambiguous reply is abandonment
(→ nothing captured).* Cite the constitution's existing "Short/ambiguous replies always
answer the most recently pending question in the SAME context" rule — don't re-derive it.

**Rationale.** A conversational-judgment rule — exactly what the constitution is for. No
deterministic code path fits "reply fits neither branch".

---

## R8 — No feature flag; no new config; test config

**Decision (2026-08-31, explicit user direction: "no need for feature flag"; unchanged by the
redesign).**
- **No `config.feature_flags` toggle.** The feature ships unconditionally: the deletion of
  the inline mechanism, the recognition call + ledgerer, the `MediaHandler` routing, the
  constitution guidance, and the breadcrumb logging are all live the moment the code is
  deployed. There is no "OFF path" to keep byte-identical.
- **No new config field.** This feature adds **zero** keys to any `config.*.json`
  (`config.accounting_ledger_update_freq` — Feature 025 — is untouched; the synchronous
  `חשבונית` capture has no gate).
- Deliberate, human-authorized departure from CLAUDE.md's "feature flags for new behavior"
  convention. Recorded as a Complexity-Tracking / Constitution-Check deviation in plan.md.
- **Safeguards that remain:** merge ≠ redeploy (deploy is a separate explicit human step);
  the full billed/expensive acceptance suite (US1–US10) must be green before "done";
  `speckit.tasks` sequences delivery slice by slice.
- **Tests:** unit tests exercise the new paths directly (no flag to set). Integration and
  acceptance tests run against `config.test.json` and set nothing.

**Rationale.** Per the user's call. CONSTITUTION §V's "integration tests test default
production behavior" is trivially satisfied — there is only one behavior and no config
surface.

---

## R9 — The extractor classify call: routing signal only; NO new AI call in `DOCXExtractor`

**Decision.** The media path's "is this ledger-relevant?" decision reuses each extractor's
**existing** document analysis — **no new OpenAI call is added to any extractor** (spec
Assumption 8, correcting the 2026-08-31 draft which had `DOCXExtractor` gain a
`capture_ledger_events_from_text` call):

- **Image** — `ImageExtractor` already runs `capture_ledger_events_from_text` on its OCR
  text. A non-empty `ledger_events` list of any `source_type` (`בנק` **or** `הסכם`) is what
  tells `MediaHandler` to route through the conversational pipeline (R1) instead of persisting
  directly. Its args (amount, banking triplet, fee components) plus
  `analysis_result["extracted_text"]` seed R2's stash. **Unchanged.**
- **`docx`** — `DOCXExtractor` produces `document_analysis` with a `document_type`
  (python-docx paragraphs + table cells + an optional text-only analysis via `config.ai_model`
  it *already* makes). `MediaHandler` routes when `document_type` indicates a fee agreement.
  Per `bugfix-028` a `docx` is **always** `הסכם` or unknown, never `בנק`. `DOCXExtractor`'s
  docstring / `base.py` comment gets a note that ledger recognition is now post-turn (in the
  recognition call), not in the extractor. **No `capture_ledger_events_from_text` call is
  added.** Acceptance: US10, one **`billed`** scenario (recognition is text-only), two-hop
  manifest.
- **Recognition itself** — happens **once, post-turn**, for every medium, in
  `AIHandler.recognize_ledger_event`. The extractor output only decides *routing*; the
  recognition call decides *capture*.

A `pdf` agreement is **out of scope** — `PDFExtractor` rasterizes each page and runs a
per-page vision call, discarding `page_result["ledger_events"]` (`pdf_extractor.py:~140-150`).
A proper fix needs a single-call-extraction rewrite → **Feature 071**
(`specs/backlog/071-pdf-single-call-extraction/`). Once 071 lands, PDF routes through this
same machinery with no further 069-side work.

**Rationale.** The redesign's core principle is "recognition happens once, post-turn, for
every medium". Adding a recognition call to `DOCXExtractor` would violate that and duplicate
work the post-turn call already does. The extractor's existing analysis is enough to decide
routing.

---

## Constitution / METHODOLOGY compliance notes (feeds the Constitution Check in plan.md)

| Rule | Status |
|---|---|
| No env vars (CONSTITUTION §I) | ✅ n/a — this feature adds **no** config keys |
| Israel-local time (`now_local()`) | ✅ every new INFO breadcrumb carries a `now_local()` `time=` field; `event_datetime` is the **triggering message's** Green API timestamp (design decision, tested), `captured_at` = `now_local()` |
| No monkey-patching (§XVII) | ✅ one new `AIHandler` method (recognition call) + one ledgerer path in `LedgerEventManager` + a thin `denidin.py` hook; DI throughout; **no new manager/module**; breadcrumbs are plain `logger.info`. Removing the inline mechanism is deletion, not patching. |
| `pathlib.Path` | ✅ no new path handling of note; fixtures use `Path` |
| Feature flag, default false, byte-identical off (METHODOLOGY) | ⚠️ **Deviation** — no flag, by explicit user direction (R8). Recorded in plan.md Complexity Tracking. |
| Tests immutable once approved; §VI.b Task A→B gate | ⚠️ **Deviation** — §VI.b Task A→B approval gate waived for the unit/integration tier (operator direction 2026-09-01); RED-first + immutable-once-committed retained; §XIX wording approval + every `expensive` run's approval kept. Recorded in plan.md Complexity Tracking. |
| ZERO MOCKING of internal components (§V) | ✅ acceptance tests are real E2E (Green API webhook JSON → router → real OpenAI + real Morning sandbox); only OpenAI / Green API are mocked, and only in unit tests |
| Integration tests never set flags | ✅ R8 — no flag exists to set |
| New tool-bearing feature ⇒ constitution boundaries + bidirectional xrefs (§XXI) | ✅ R4 — the rewritten "Ledger Event Recognition" section + bidirectional xrefs; note the feature **removes** `capture_ledger_event` from the main turn and keeps read-only `query_ledger_events` |
| Schema version human-only (CLAUDE.md) | ✅ R6 — human decided NOT to bump; no field added; no test asserts the value |
| UX-impacting change ⇒ approval before implementing (§XIX) | ✅ constitution wording + operator-facing strings approved during `speckit.implement`, not planning (FR-069-041 HARD STOP) |
| No silent degraded write on failed external handshake (§XVIII) | ✅ tunnel down during resolution → operator told, event never completes, zero events persisted |

**Two Constitution deviations, both operator-authorized, both in plan.md Complexity Tracking.**
