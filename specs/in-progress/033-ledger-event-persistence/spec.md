# Feature Specification: Ledger Event Persistence

**Feature Branch**: `feature/033-ledger-event-persistence`
**Created**: 2026-07-29
**Status**: Draft
**Input**: User description: "ledger events need to be persisted in their own folder in
the data - outside the sessions, next to memory and media storages"

---

**IMPORTANT**: This spec complies with:
- **CONSTITUTION.md** (§I-III, §V, §XV, §XVII): No env vars, UTC timestamps internally
  (local-time conversion is output-only formatting, not internal storage), feature branch
  workflow, integration tests as E2E, alphabetized/UTF-8 JSON, no monkey-patching.
- **METHODOLOGY.md** (§I, II, VIII, IX, X): Spec-first development, mandatory user stories,
  Terminology Glossary, Technology Choices, Requirement IDs.

**Required Files**: `user-stories.md` (present) ✅ · `spec.md` (this file) · `plan.md` ·
`research.md` · `data-model.md` · `contracts/` · `quickstart.md` · `tasks.md`.

---

## User Stories Reference

Complete Given-When-Then acceptance criteria live in **`user-stories.md`**. Summary:

| # | Title | Priority |
|---|---|---|
| US1 | Text-path event persists to its own permanent file | P1 |
| US2 | Image/media-path event persists the same way, with `message_id` | P1 |
| US3 | Multi-component message → multiple separate event files | P2 |
| US4 | The one historical stray session migrates to the new format | P3 |

## Terminology Glossary

- **`event_id`**: Primary key of a persisted ledger event, format
  `{letter}{DDMMYY}{HHMM}{seq}` (e.g. `A28072614060`) — see Requirements below. Also the
  filename (`data/events/{event_id}.json`).
- **`letter`**: First character of `event_id`. `A` = `source_type=הסכם` (fee agreement),
  `B` = `source_type=בנק` (bank deposit). `H` (`חשבונית`/invoice) exists in the historical
  ledger but is never produced by `capture_ledger_event` — out of scope here (Feature 025).
- **`seq`**: Single-digit (0–9) collision counter, scoped to one `letter`+`DDMMYY`+`HHMM`
  combination, among DeniDin's own previously-persisted events only.
- **`component`**: One fee-component of a multi-part message (e.g. one stage of a
  conditional/sequential fee agreement). Each component is captured as its own
  `capture_ledger_event` call and persisted as its own event file — never aggregated.
- **`agreement`**: The overarching fee arrangement one or more components belong to.
  `agreement_id`/`component_id`/`component_label` ARE populated by this feature (revised
  2026-07-30 — see Clarifications and REQ-DATA-004); `trigger_condition`/split-fee/due-date
  columns remain reserved-null, deferred to the nuances backlog feature.
- **`agreement_label`** / **`component_label`**: New `capture_ledger_event` tool fields
  (2026-07-30). Short, human-readable Hebrew labels — `agreement_label` names the matter as
  a whole, `component_label` names one component — following the style of real historical
  `Events.csv` entries (e.g. `ערעור_לארצי`, `בסיס`). `component_label` is itself a real CSV
  column (`הסכם.רכיב`); `agreement_label` is DeniDin-internal only, consumed solely to build
  `agreement_id` (not a CSV column, not persisted separately).
- **`ledger_event_ids`**: New `Message` field (session data) listing the `event_id`(s)
  captured from that specific message — the reverse link to `message_id` on the event side.
- **`data_root`**: Existing config field (`AppConfiguration.data_root`); this feature adds
  `{data_root}/events/` as a new sibling of `{data_root}/sessions/`, `{data_root}/memory/`,
  `{data_root}/media/`.
- **DEPRECATED: `pending_ledger_events`** (use `data/events/*.json` via `LedgerEventManager`
  instead) — the `Session` field this feature removes.

## Problem Statement

Feature 024 (Ledger Event Recognition) added `SessionManager.add_pending_ledger_event`,
appending captured `capture_ledger_event` records into `Session.pending_ledger_events`
inside `session.json`. Always intended as temporary ("never writes to any ledger file
itself... an external script later reads and merges it"), this has concrete problems found
2026-07-28 while inspecting a live-captured event:

1. **Not actually permanent** — tied to session lifecycle instead of being independent,
   durable records.
2. **Not traceable to its source message** — only `message_timestamp` exists, forcing
   timestamp cross-referencing.
3. **Multi-component messages collapse into one event** — a real message stating 3
   conditional/sequential fee stages (₪8,000 / ₪20,000 / +₪30,000) was captured as ONE
   event with all three amounts crammed into one `amount` string.
4. **The shape doesn't match the real downstream ledger** — the user maintains
   `data/events/Events.csv` (1159 rows, 29 columns), which today's captured shape (16 raw
   tool fields + 3 bookkeeping fields) doesn't correspond to at all.

## Clarifications

### Session 2026-07-29

- Q: Where should ledger events be stored, relative to session data? → A: Their own
  top-level folder under `data_root`, sibling to `sessions/`, `memory/`, `media/` — not
  nested under a session directory (superseding an earlier, now-abandoned handoff plan of
  `sessions/<id>/ledger_events/`). Named `data/events/` (matching where the reference
  `Events.csv` already lives), owned by a new `LedgerEventManager` class (sibling to
  `MemoryManager`/`MediaFileManager`, not a `SessionManager` method).
- Q: File layout? → A: One flat JSON file per event, named by `event_id`:
  `data/events/{event_id}.json` — mirrors `media/`'s existing flat-file-per-item pattern.
- Q: `event_id` format? → A: Must match `Events.csv`'s existing scheme exactly. Verified by
  direct inspection of all 1159 rows: `{letter}{DDMMYY}{HHMM}{seq}`, letter mapped from
  `source_type`, date/time in **local Asia/Jerusalem time** (message_timestamp is stored
  UTC), `seq` a **single digit only, always** (confirmed: the 2 apparent 2-digit exceptions
  found in an earlier pass are pre-existing historical anomalies, not a rule to replicate).
- Q: How is `seq` collision-checked, given `Events.csv` (1159 pre-existing rows) is not read
  at runtime? → A: Scoped only to DeniDin's own previously-persisted events (scan
  `data/events/*.json`) — safe, since DeniDin's captured dates will always postdate the real
  file's most recent entry.
- Q: 11th component in the same letter+date+minute (all 10 single-digit slots taken)? → A:
  (Revised 2026-07-29 — the original plan added a dedicated user story + AIHandler
  reply-shaping requirement for this; dropped as unnecessary complexity for a
  practically-unreachable edge case, single lawyer's WhatsApp traffic.) Just don't corrupt
  data: log ERROR, write no file, `add_ledger_event` returns `None` instead of an
  `event_id` — same as any other "nothing captured" outcome the caller already has to
  handle. No dedicated user-facing message, no dedicated story/tests beyond this one
  generator-robustness case.
- Q: `סכום` (amount) normalization — captured `amount` is deliberately verbatim/unconverted
  text (no AI currency math, by design)? → A: Code-side only: strip `₪`/`ש"ח`/thousands
  commas, round to signed integer, always NIS. Negative allowed (e.g. a cancellation
  reversing a prior positive amount). Unparseable text → leave `סכום` blank, keep the
  verbatim text in `הערות`, log WARNING — never guess in code either.
- Q: `מזהה_אירוע_מוחלף`/`הפניה` — both real ID references in the actual CSV (verified: 100%
  of 20 non-empty `הפניה` values across the whole file are pure comma-separated event-ID
  lists, never free text)? DeniDin only captures free-text `replaces_hint`/`reference_hint`
  hints, and can't resolve them to real IDs without reading the full historical CSV (out of
  scope). → A: `מזהה_אירוע_מוחלף` = literal `"צריך למצוא"` when `replaces_hint` is non-null
  (that field's definition — correcting/cancelling a specific prior arrangement — is
  unambiguous enough to act on), else blank. `הפניה` stays **blank always** in this feature
  — `reference_hint`'s current definition is too loose to reliably distinguish "references a
  distinct past agreement" from incidental context (proved by the migration data itself:
  captured values were an institution name and a contact's email/phone, not agreement
  references).
- Q: The four `הסכם.*` linkage/label columns (agreement id, component id, component label,
  trigger condition), the two split-fee columns, and due date? → A: (Revised 2026-07-30 —
  see below) `trigger_condition`, the two split-fee columns, and due date remain deferred to
  a new backlog feature ("Ledger Event Capture — Full Schema & Nuances"), reserved
  always-null. `agreement_id`/`component_id`/`component_label`, however, are now populated by
  this feature — see the 2026-07-30 entry immediately below.
- Q: (2026-07-30, after the real migration run) Reviewing the migrated files, the user
  flagged `agreement_id`/`component_id` as unacceptable to leave null — real ledger entries
  always carry them, and the historical `Events.csv` already links multi-component captures
  this way. What's the correct design? → A: Inspected all 1159 rows of the real
  `data/events/Events.csv` directly. Confirmed format:
  `agreement_id = "{MMYY}-{slugify(client_name)}-{slugify(agreement_label)}"` (e.g.
  `0726-אתי_אסולין-ערעור_לארצי`), `component_id = "{agreement_id}-{slugify(component_label)}"`
  (e.g. `0726-אתי_אסולין-ערעור_לארצי-בסיס`), `MMYY` from the source message's local
  Asia/Jerusalem date (2-digit month + 2-digit year, matching `event_id`'s date convention).
  Confirmed via real duplicate-`agreement_id` groups (e.g. a genuine 5-row group,
  `0626-גיא_לקן-תביעת_נזיקין_נגד_מדי`) that all components of one multi-component capture
  share **one** `agreement_id`, byte-for-byte identical. The user's hard requirement: this
  identity MUST be guaranteed by construction, never by relying on the AI to repeat the same
  text verbatim across separate `capture_ledger_event` tool calls in one turn (a real risk —
  no strict guarantee of character-for-character repetition across independently-generated
  structured outputs). Design: `capture_ledger_event` gains two new required fields,
  `agreement_label` (short label for the whole matter; only meaningful for `source_type=הסכם`,
  `null` for `בנק`) and `component_label` (short label for just this component — this one IS
  a real CSV column, `הסכם.רכיב`, previously wrongly left in the reserved-null list). Content
  source doesn't matter to the user ("I dont care who supplies it") as long as consistency is
  structural — so `AIHandler._handle_ledger_event_capture` computes `agreement_id` exactly
  **once per batch** (one AI turn producing multiple `capture_ledger_event` calls = one
  batch), from the *first* `הסכם`-typed component's `client_name`/`agreement_label`/
  `message_timestamp`, and passes that identical string into every `add_ledger_event` call
  for the rest of that batch — `LedgerEventManager` never independently re-derives it when a
  caller supplies one. A single (non-batched) capture still gets a real `agreement_id`,
  freshly derived by the manager itself from its own `client_name`/`agreement_label`. `בנק`
  events get `agreement_id`/`component_id` = `null` always (no agreement concept applies —
  unchanged from the original decision). Batches are assumed single-client/single-matter
  (matches every observed real multi-component group in `Events.csv`); a message genuinely
  spanning two unrelated agreements in one turn is not handled specially — out of scope, no
  evidence this occurs in practice.
- Q: The 5 `חשבונית.*` (invoice-linkage) columns? → A: Data model must include them
  (reserved, always null) so a future Morning-reconciliation feature can populate them
  later — no capture logic in this feature.
- Q: Message ↔ event traceability? → A: Two-way. Each event file carries `message_id`
  (new). `Message` gains `ledger_event_ids: List[str]`. Verified via code reading: text path
  (`AIHandler._finalize_response`) already calls `_handle_ledger_event_capture` before
  message-storage, so ids are available at message-creation time. Media path
  (`MediaHandler.process_media_message`) currently stores the message (`_store_media_turn`)
  *before* ledger capture — reordered by this feature to match the text path.
- Q: The one already-captured stray session
  (`dev_data/sessions/4454746c-350a-4fa7-a5ef-fda2c685b0d5`, 3 combined events from the
  2026-07-28 live test)? → A: Migrate now, applying the new per-component-splitting rule
  retroactively (see `user-stories.md` US4): 3+2+1 = 6 files total. `message_id` is `null`
  on all 6 (never recorded by the old path).

### Session 2026-07-30 (second addendum) — `שעות_תאריך` (hours-work-date)

*(Field later renamed — see the fourth addendum below and the revised `REQ-DATA-005`: the
field described as `hours_date`/`שעות_תאריך` throughout this addendum was unified with a
later `transaction_date` field into one field, `txn_date`/`תאריך_ביצוע`, still governed by
`REQ-DATA-005`. This addendum is kept as-written for the historical record of why the field
exists at all — only its name changed, not the decisions below.)

- Q: Real hourly work-log messages (e.g. "ענבר בן סימון תגובה לטיעון משלים אתמול 4 שעות היום
  5 שעות") report hours worked on a day DIFFERENT from the day the message was sent ("אתמול"/
  "היום" relative to message time, or an explicit date). `event_date`/`event_time` are always
  code-derived from `message_timestamp` (when the WhatsApp message arrived) — there was no
  field for "the calendar day the hours were actually worked." Is that gap acceptable? → A:
  No — real gap, confirmed by the user's own real examples. New CSV-mapped column added:
  **`שעות_תאריך`** (`hours_date`, `DD/MM/YYYY | null`) — the actual date the hours were
  worked, independent of `event_date` (which keeps its existing meaning: the date the message
  arrived). This is a genuinely NEW column, not present in the original 29-column
  `Events.csv` — the schema is now 30 CSV-mapped columns. Bumping the real downstream
  `Events.csv` to add this column is a human/bookkeeping decision outside this codebase's
  scope; DeniDin's own files simply carry the field going forward.
- Q: Who resolves "אתמול"/"היום"/an explicit date into an absolute calendar date — code or
  the AI? → A: The AI. `capture_ledger_event` gains a new field `hours_date` (`string | null`,
  ISO-8601 `YYYY-MM-DD`, required non-null whenever `hours` is non-null) — the model already
  has the real current date injected into its instructions every call (see
  `handlers/ai_handler.py`'s `_build_instructions`), so it can reliably resolve relative-date
  Hebrew phrases itself; a code-side parser attempting the same NLP would be far less
  reliable, and the constitution's existing "never let the AI do arithmetic/normalization
  code should own" principle applies to *format normalization*, not date-phrase resolution the
  AI is already positioned to do correctly. Code then normalizes the AI's ISO string to
  `DD/MM/YYYY` (matching `event_date`'s persisted format) before writing — never trusts the
  AI's own formatting verbatim, same `REQ-DATA-001`-style discipline as `amount`. Unparseable/
  missing `hours_date` when `hours` is non-null → leave `שעות_תאריך` blank, log a WARNING
  (never guess) — same fallback shape as amount normalization, no aggregation into `notes`
  since there's no obvious "original text" to preserve (the AI outputs a resolved date, not a
  verbatim phrase).
- Q: Does `שעות_תאריך` apply to `source_type=בנק`? → A: No special-cased nulling needed (no
  bank deposit ever has `hours` populated in practice) — same laissez-faire handling as
  `hours`/`hourly_rate`/`percent`/`percent_base` today, no `agreement_id`-style forced-null
  branch required.

### Session 2026-07-30 (third addendum) — `components` array replaces multi-call reliance

- Q: Real-image E2E testing (two real fee-agreement documents, both with multiple
  genuinely distinct fee components — one with 3, one with 6) consistently produced only
  ONE `capture_ledger_event` call each, with every component after the first dumped into
  free-text `notes` instead of split out, DESPITE `REQ-DATA-004`'s explicit "never
  aggregate" constitution rule. Was this a comprehension/extraction problem? → A: No —
  ruled out through a systematic elimination, in order: (1) sharpened the shared image
  extraction prompt (`prompts/image_analysis.txt`) to require exact per-figure precision
  and explicit `[לא קריא]` marking instead of hallucinating plausible-sounding filler text
  — real, measurable improvement, but the model still made only 1 call. (2) Discovered via
  `client.models.list()` (the real, authoritative account model list — not documentation
  guesswork) that materially newer models were available (`gpt-5.6-luna` among them,
  already the app's `ai_model` default); switched `ai_vision_model` to it for a real,
  direct comparison on the harder of the two documents — extraction became essentially
  perfect (correct client name including a signature previously flagged illegible, all 6
  real figures correct) — but the model STILL made only 1 call, dumping the other 5
  components into `notes`. This conclusively isolated the failure: extraction/comprehension
  was never the bottleneck: the model reliably chooses to make one tool call and describe
  the rest in prose, independent of prompt wording or model strength.
- Q: Given prompting and a stronger model both left the core problem untouched, what's the
  fix? → A: Stop depending on autonomous repeated tool invocation entirely — restructure
  `capture_ledger_event` so ONE call carries a `components` array (structured output),
  since reliably producing correctly-structured output within a single call is a
  fundamentally different (and more reliable) capability than autonomously deciding to
  invoke the same tool multiple times. See `REQ-DATA-006`.
- Q: How was this validated before writing any application code? → A: External,
  standalone scripts (not part of the test suite, not going through the app) — first
  proved the hypothesis against a real, previously-captured extraction text with the
  proposed tool schema (all 6 components correctly split, right amounts, right VAT
  handling per the base+total clarification below); then proved the FULL pipeline
  (image → vision extraction → classification) fresh from the raw image file, using the
  exact real, unmodified `config/runtime_constitution.md` and `prompts/image_analysis.txt`
  content (verified explicitly, not assumed) — both real documents correctly produced
  their real component counts (3 and 6) in one call each. Only after both proved out was
  the schema wired into `LEDGER_EVENT_TOOL`/`LedgerEventManager`/`AIHandler`/`MediaHandler`.
- Q: A base amount and its own VAT-inclusive total for the SAME component (e.g. "20,000 +
  VAT = 23,600") — is that two amounts needing two components? → A: No — this ambiguity
  was found and fixed during the same investigation (both the prompt and the constitution
  originally risked conflating this with genuine multi-component splitting). It's ONE
  component with ONE `amount`: use the VAT-inclusive total when the source states one,
  else the pre-VAT figure — never both, never compute the total yourself. Only split when
  the source genuinely describes separate stages/tracks/conditions, each with its own
  amount.

### Session 2026-07-30 (fourth addendum) — enhancements from `summary.md` (AHLedger build heuristics)

- Q: A retrospective document (`summary.md`) describing the manual heuristics used to build
  the historical `Events.csv`/`Agreements.csv` from raw sources was reviewed against this
  feature's constitution rules and data model — what, if anything, was missing? → A: Four
  gaps, all addressed 2026-07-30: (1) `raw_message_excerpt` for an image-sourced capture was
  allowed to be "a precise description," not a full transcript — tightened to require the
  full verbatim extracted text, closing the same re-audit gap that made the historical
  ledger's provenance hard to re-verify. (2) No stated precedence when a document image and
  its accompanying chat caption conflict — added: the document wins on direct conflicts.
  (3) `בנק` (bank-deposit) events had classification but essentially no extraction guidance —
  added rules for banking-app template variance, the "מ-" (from-) Hebrew-preposition-stripping
  trap on payer names, multi-date screenshots (see REQ-DATA-005), and not silently dropping
  suspected duplicate screenshots. (4) The "ambiguous referent" rule didn't name the specific
  reasoning error that caused the historical ledger's worst provenance failures — being the
  only plausible candidate is not evidence of being the correct one — made explicit.
- Q: `summary.md`'s fee-agreement model has explicit typed events (create/amend/cancel/
  confirm) — does DeniDin need a new field for this? → A: No — `event_subtype` (`יצירה`/
  `עדכון`/`ביטול`/`אישור-מימוש`/`הפקדה`) already covers this exact classification (Feature
  024/033, predates this review). What was missing was making explicit, in both the
  constitution and `data-model.md`, that this field is classification-only: every capture
  produces one new, independent, immutable record regardless of `event_subtype` — an
  `עדכון`/`ביטול` is never applied against a prior record automatically. "Today we only
  support create" at the storage layer, by explicit design choice — actually reconciling an
  `עדכון`/`ביטול` against the specific prior event it targets stays downstream/future-feature
  work, same as it already was for `replaces_hint`/`replaced_event_id`.
- Q: Does the multi-date bank-screenshot heuristic need a new schema field? → A: Yes, one —
  see REQ-DATA-005. The other three gaps were constitution-wording-only (no code/schema
  change needed).
- Q: The new field was initially shipped as a second, separate field (`transaction_date`,
  briefly `REQ-DATA-007`) alongside the existing `hours_date` (`REQ-DATA-005`) — was that
  the right call? → A: No. This was built and reported without first checking whether a new
  field was warranted at all — the user's reaction: "what is transaction_date?!?! I dont
  remember asking for this!" Once asked, the user immediately identified the better design:
  "Seems exactly like hours_date - why not unify them to a single field? call it txn_date."
  The two fields were, in fact, the same concept twice (an AI-resolved calendar date for
  this component's own content, distinct from the message timestamp) — one for an
  hours-worked date, one for a transaction date — with no reason to keep them separate.
  Unified same-day into the single `txn_date` field documented in `REQ-DATA-005` above;
  `REQ-DATA-007` is retired (see the strikethrough entry in Requirements). This is now
  recorded as a standing process lesson (see project memory): approving a *gap* is not the
  same as approving a *new schema field* — a new field is always its own decision point.

### Session 2026-08-02 (fifth addendum) — `components` array silently empty (REQ-DATA-008)

- Q: A real, billed run of the Mor ben-Shaya 6-component test (2026-07-31) produced
  `ledger_events_captured=1` — the model DID call `capture_ledger_event` — but zero
  `LedgerEvent` files were persisted and no error was logged anywhere. What happened? → A:
  Traced directly from the raw request/response logs (not re-run - the user's explicit
  instruction: "dont rerun yet"). Extraction was excellent (verbatim-correct, all 6
  components present in the extracted text). The classification call's own response had
  `output item types=['reasoning', 'function_call']` - no `message` item, so the model
  produced no natural-language explanation for this call at all (its `reasoning` item is
  OpenAI-internal and wasn't requested via `include`, so it isn't retrievable even in
  principle). The only way to reconcile "1 call, 0 persisted, 0 errors" is that the one
  call's `components` array was itself empty - a schema-legal but semantically-invalid
  response, since `LEDGER_EVENT_TOOL`'s `components` field had no `minItems` constraint at
  the time.
- Q: Historical track record for this exact test, pulled from logs rather than asserted? →
  A: 4 real runs (2026-07-30, 16:08-17:13) with the pre-`components`-array-redesign code:
  all persisted exactly 1 component (the old "one call, one component" bug). 1 real run
  (17:40:31) right after the redesign landed: 6/6 correctly persisted - the validated,
  genuinely-passing run this feature's earlier summary referred to. 1 real run (2026-07-31,
  09:46:18, after an unrelated redeploy for the `txn_date` work): 0 persisted, the new
  failure this addendum investigates. So the redesign fix is real (verified, not
  fabricated) but was never proven reliable across repeated runs - a probabilistic
  extraction/classification system needs defense against occasional degenerate output,
  not just a single passing test.
- Q: What's the actual fix, and why not everything considered? → A: Of 7 candidate
  mitigations discussed, 4 were adopted (see REQ-DATA-008) and 3 explicitly rejected:
  (1) `minItems` on the schema - dropped: even if OpenAI's strict mode enforces it (never
  verified), it only forecloses the exact empty-array case the app-code check in (a) below
  already catches after the fact: pure redundancy for a small, unverified efficiency gain.
  (2) Two-phase decomposition (enumerate-then-detail as separate calls) and (3) reasoning-
  effort tuning - both deferred as heavier architecture changes, only worth exploring if
  the adopted fix proves insufficient with more real-world data.
- Q: What was adopted? → A: (a) `component_count`: a new required top-level integer field
  the model must state before generating `components`, checked in code against the actual
  array length - catches a *partial* undercount that an empty-array check alone would miss.
  (b) `is_incomplete_capture()`: a shared helper (empty `components`, OR `component_count`
  present and mismatched) used by both of the below. (c) A retry, in
  `capture_ledger_events_from_text` only (the image-path classification call where this was
  observed) - if the response is incomplete, retry once with an explicit message naming the
  defect, before returning. (d) A last-resort safety net in
  `add_ledger_events_from_call` (the single path both the text and image routes persist
  through, so it protects both even though only the image path retries): if `components` is
  STILL empty, persist one flagged fallback record from the call's agreement-level fields
  (`notes` explains the gap) instead of silently returning nothing - matching this feature's
  existing philosophy that an explicitly incomplete capture is the correct output, never
  silence. A non-empty but count-mismatched `components` is persisted as given (never drop
  real data) with an ERROR logged for human review.

### Session 2026-08-02 (sixth addendum) — payer-phrasing miss + hours normalization (REQ-DATA-009)

- Q: A real run of `test_given_real_hours_message_with_payer_reference_then_payer_name_captured`
  ("רן אורפני\nדרך הראל\nעל אתמול שעתיים\nעל היום שעתיים") captured `payer_name=null`,
  filing "דרך הראל" into `agreement_label` instead - is this a code bug? → A: No - the
  constitution's existing "Payer vs. client" rule only described the *concept*
  (intermediary-routed payment) generically, without naming the actual linguistic trigger
  ("דרך X"/"באמצעות X"/"via X"/"through X") the model needed to recognize the phrasing as
  payer-routing rather than part of the matter description. Fixed by adding the explicit
  trigger phrase to both the constitution bullet and `payer_name`'s own tool-schema
  description - re-tested for real afterward: `payer_name='הראל'` correctly captured on both
  resulting events.
- Q: Should the model ask the user when it hits genuine ambiguity like this, rather than
  silently guessing which field something belongs in? → A: Yes - a new, general principle
  added to Step 2 (not payer-specific): when an ambiguity is material (which field, which of
  two readings, etc.) and a single question would resolve it, prefer asking directly in the
  normal reply over silently guessing or flagging it only in `notes` for a human who might
  not review the ledger export for weeks. The live conversation has something the historical
  ledger's builders never did - the actual person who wrote the message, still there to ask.
  `notes`-flagging and blank-leaving remain the fallback for minor ambiguities or when asking
  isn't practical, not the default whenever a live answer is one message away.
- Q: Fixing payer_name surfaced a second, previously-hidden failure in the SAME test (the
  payer_name assertion had aborted the loop before reaching it) - `hours` stayed the literal
  Hebrew word `'שעתיים'` instead of resolving to a number. Was this ever actually guaranteed
  anywhere? → A: No - traced directly: `hours` had zero code-side normalization (unlike
  `amount`, which `_normalize_amount` already converts) and zero constitution/schema
  instruction telling the model to convert word-forms itself. The test's expectation was
  never backed by any real mechanism.
- **REQ-DATA-009** (added 2026-08-02, user directive: "hours should always be numerical"):
  `LedgerEventManager` MUST gain `_normalize_hours(raw) -> Optional[float]`, the same
  "AI reports verbatim, code converts" discipline REQ-DATA-001 established for `amount` -
  digit-string parsing plus a bounded Hebrew hour-count word dictionary (שעה/שעתיים/שלוש
  שעות/.../שתים עשרה שעות, plus "חצי"/"רבע" and "X וחצי" half-hour forms), deliberately not
  exhaustive (mirrors `_normalize_amount`'s "give up gracefully rather than guess"
  philosophy). Persisted `hours` MUST be numeric or `null` - never the raw word/string.
  Unparseable input: `שעות` left blank, WARNING logged, original text preserved in `notes`
  (identical fallback shape to `amount`). The `hours is not None` check that governs
  `txn_date`'s requiredness (REQ-DATA-005) MUST use the AI's raw `hours` text, evaluated
  before normalization - an hours entry that failed to normalize still needs its `txn_date`.

## Edge Cases

- What happens when `amount` text contains multiple numbers that were NOT already split
  into separate `capture_ledger_event` calls (a message the model should have split per the
  constitution's existing "never aggregate" rule but didn't)? → Out of this feature's scope
  to detect/correct at capture time (that's AI-prompt quality, i.e. nuances-feature/
  constitution-wording territory); this feature's `amount` parser only needs to cleanly
  handle a *single* stated amount per event and blank+log when it can't.
- What happens when `message_timestamp` is `None` (should never happen — `AIRequest`
  auto-fills one — but the existing test `test_add_pending_ledger_event_missing_timestamp`
  covers this not crashing)? → `event_id` generation needs *some* timestamp; if truly
  absent, fall back to `captured_at` (processing time) for the date/time portion only, and
  log a WARNING (this is a defensive fallback, not expected to trigger in practice).
- What happens to `data/events/` across dev/prod/test environments? → Same isolation as
  `sessions/`/`memory/`/`media/` today — one folder per `data_root`, no special-casing.
- Does `LedgerEventManager` need a feature flag? → No — this is a storage-location and
  schema change to already-shipped, always-on behavior (Feature 024's capture is not
  gated behind a flag either), not new user-facing behavior being rolled out gradually.

## Requirements *(mandatory)*

### Functional Requirements

- **REQ-STORE-001**: System MUST provide a `LedgerEventManager` class, sibling to
  `MemoryManager`/`MediaFileManager`, owning `{data_root}/events/` as its storage
  directory (created on init if absent). The path MUST be composed relative to
  `AppConfiguration.data_root` at construction time (`Path(config.data_root) / "events"`),
  exactly matching `MediaFileManager`'s existing pattern — never a hardcoded absolute
  path, and never read from a value baked in earlier than the manager's own
  construction (this is what lets tests safely override `data_root` to an isolated
  root and have it actually take effect — see the safety guard in
  `tests/expensive/test_ledger_event_capture_e2e.py`'s `denidin_app` fixture, which
  asserts this holds on every run).
- **REQ-STORE-002**: System MUST persist each captured ledger event (or each component of a
  multi-component capture) as its own file, `data/events/{event_id}.json`, never grouped
  into a shared file.
- **REQ-STORE-003**: System MUST remove `Session.pending_ledger_events` from the `Session`
  dataclass and `session.json`; `SessionManager` MUST NOT own any ledger-event storage.
- **REQ-ID-001**: `event_id` MUST be generated as `{letter}{DDMMYY}{HHMM}{seq}`, where
  `letter` is `A` for `source_type=הסכם` / `B` for `source_type=בנק`; `DDMMYY`/`HHMM` are
  the source message's local Asia/Jerusalem date/time (converted from the UTC
  `message_timestamp`); `seq` is a single digit 0–9.
- **REQ-ID-002**: `seq` collision-checking MUST be scoped only to DeniDin's own
  previously-persisted files under `data/events/` — MUST NOT read `Events.csv` at runtime.
- **REQ-ID-003**: When all 10 single-digit `seq` values for one `letter`+`DDMMYY`+`HHMM`
  are already taken, the capture attempt MUST NOT write a file or overwrite an existing
  one: an ERROR MUST be logged and `add_ledger_event` MUST return `None` (same shape as
  any other "nothing captured" outcome — no dedicated rejection type, no dedicated
  user-facing behavior; see Clarifications, revised 2026-07-29).
- **REQ-DATA-001**: `amount` MUST be normalized in code (never by the AI) from the
  captured verbatim text to a signed integer NIS value: strip `₪`/`ש"ח`/thousands commas,
  round to the nearest integer, preserve a leading minus sign. If the text can't be
  cleanly parsed to one number, `סכום` MUST be left blank, the original text MUST be kept
  in `הערות`, and a WARNING MUST be logged.
- **REQ-DATA-002**: `מזהה_אירוע_מוחלף` MUST be the literal string `"צריך למצוא"` when
  `replaces_hint` is non-null, else blank. `הפניה` MUST always be blank in this feature
  regardless of `reference_hint`.
- **REQ-DATA-003**: The data model MUST include all 30 `Events.csv`-mapped columns (29
  original + `תאריך_ביצוע` [REQ-DATA-005, added 2026-07-30]) (see `data-model.md`);
  columns not populatable by this feature (`trigger_condition`, `split_partner`,
  `split_percent`, `due_date`, and all 5 `חשבונית.*` fields) MUST be present and always
  `null`, not omitted from the schema. (Revised 2026-07-30:
  `agreement_id`/`component_id`/`component_label` moved out of this always-null list — see
  REQ-DATA-004.)
- **REQ-DATA-004** (added 2026-07-30): For `source_type=הסכם` events, `agreement_id` and
  `component_id` MUST be populated (never null); for `source_type=בנק`, both MUST stay
  `null` (no agreement concept applies). `capture_ledger_event` MUST gain two new required
  fields, `agreement_label` (`str | null` — null only for `בנק`) and `component_label`
  (`str | null` — same nullability; this is the existing `component_label` CSV column).
  `agreement_id` MUST be computed as `"{MMYY}-{slugify(client_name)}-{slugify(agreement_label)}"`
  and `component_id` as `"{agreement_id}-{slugify(component_label)}"`, matching the real
  `Events.csv` convention exactly (verified 2026-07-30 against all 1159 rows). `MMYY` MUST
  be derived from the source message's local Asia/Jerusalem date, 2-digit month + 2-digit
  year (same convention as `event_id`'s date portion). All components of one
  multi-component capture MUST share byte-for-byte the same `agreement_id` — guaranteed
  structurally (computed once, before persisting any component, never depending on the AI
  repeating identical text across separate calls). (Revised 2026-07-30 — see REQ-DATA-006:
  "multi-component capture" now normally means one `capture_ledger_event` call's
  `components` array, not multiple separate calls in one turn.)
- **REQ-DATA-006** (added 2026-07-30, supersedes the "multiple separate calls" mechanism
  REQ-DATA-004 originally assumed): `capture_ledger_event`'s parameters MUST be restructured
  so agreement-level fields (`source_type`, `event_subtype`, `client_name`, `payer_name`,
  `agreement_label`, `replaces_hint`, `reference_hint`, `raw_message_excerpt`) stay
  top-level, and all per-component fields (`description`, `amount`, `percent`,
  `percent_base`, `hours`, `hourly_rate`, `hours_date`, `vat_status`, `notes`,
  `component_label`) move into a required `components` array (>=1 item, even for a
  single-component or `בנק` capture). `LedgerEventManager` MUST gain
  `add_ledger_events_from_call(session_id, whatsapp_chat, call_arguments, message_id,
  message_timestamp, sender) -> List[str]`, which flattens each component with the call's
  shared fields, computes `agreement_id` once for the whole call, and persists each
  component via the existing (unchanged) `add_ledger_event`. See Clarifications
  (2026-07-30, third addendum) for why: relying on the model to make N separate tool calls
  for a multi-stage agreement was tested extensively — real constitution instruction, a
  materially stronger vision+reasoning model, and a sharpened extraction prompt all fully
  fixed extraction *accuracy* on two real test documents, but the model still reliably chose
  to make exactly ONE tool call and describe every component after the first in free-text
  `notes`, regardless. A single call with a structured `components` array was validated
  externally (real API calls, both real documents, this exact schema) before being wired
  into the app, and correctly produced all 3 and all 6 real components respectively, in one
  call each, on the first attempt.
- **REQ-DATA-005** (added 2026-07-30; revised 2026-07-30 same day — unifies what was
  briefly a separate `REQ-DATA-007`/`transaction_date` field into this one, per user
  direction after the two fields were pointed out as duplicative): `capture_ledger_event`
  MUST gain a new component-level field `txn_date` (`string | null`, ISO-8601
  `YYYY-MM-DD`), used for two distinct cases that share one field because both are "the
  AI-resolved actual calendar date this component's own content refers to, when distinct
  from `event_date`/the message's own timestamp": (1) required non-null whenever `hours`
  is non-null — the date the hours were worked; (2) for a `source_type=בנק` component,
  always optional — populated only when the screenshot itself states an explicit
  transaction/value date distinct from other dates visible on screen (e.g. when it was
  forwarded). These two cases are not mutually exclusive triggers on the same field, just
  two different reasons it gets populated. Code MUST normalize this to `DD/MM/YYYY` before
  persisting as `תאריך_ביצוע` (never trust the AI's own string format verbatim, matching
  `REQ-DATA-001`'s amount-normalization discipline, one shared normalization helper for
  both cases). When `hours` is non-null but `txn_date` is missing/unparseable, or when
  `txn_date` is stated but unparseable in the בנק case, `תאריך_ביצוע` MUST be left blank
  and a WARNING MUST be logged (never guess). Never a substitute for `message_timestamp`
  (unaffected — remains the hard pointer per the existing provenance rules) or for
  `event_date`/`event_time` (unaffected — remain derived from `message_timestamp` only).
- ~~**REQ-DATA-007**~~ (added 2026-07-30, superseded the same day — merged into
  `REQ-DATA-005` above once pointed out that a separate `transaction_date` field
  duplicated `hours_date`'s exact shape/purpose; kept here only so the id isn't silently
  reused for something unrelated later).
- **REQ-DATA-008** (added 2026-08-02, real billed incident — see Clarifications' fifth
  addendum): `capture_ledger_event` MUST gain a new required top-level field
  `component_count` (`integer`), stated before `components` in the schema, which the model
  must set to the exact number of entries it is about to list in `components`.
  `LedgerEventManager` MUST provide a shared `is_incomplete_capture(call_arguments) -> bool`
  helper: `True` when `components` is empty, or when `component_count` is present and
  doesn't match `len(components)`. `AIHandler.capture_ledger_events_from_text` (the
  image-path classification call) MUST retry once, with an explicit corrective message
  naming the defect, when its response `is_incomplete_capture`. Regardless of whether a
  caller retried, `LedgerEventManager.add_ledger_events_from_call` MUST NOT silently return
  an empty list when `components` is empty: it MUST persist exactly one fallback
  `LedgerEvent` from the call's agreement-level fields, with `notes` explaining that AI
  capture returned zero components and needs manual review, and MUST log an ERROR. A
  non-empty but `component_count`-mismatched `components` MUST be persisted as given (never
  drop real, partial data) with an ERROR logged for human review. `component_count` itself
  is never persisted (popped before merging into the flat `LedgerEvent` shape) - validation-
  only, not a data-model field.
- **REQ-DATA-009** (added 2026-08-02, user directive: "hours should always be numerical" —
  see Clarifications' sixth addendum): `LedgerEventManager` MUST gain
  `_normalize_hours(raw: Optional[str]) -> Optional[float]`, same "AI reports verbatim, code
  converts" discipline as `REQ-DATA-001`'s `amount` normalization: digit-string parsing (with
  an optional trailing "שעה"/"שעות") plus a bounded Hebrew hour-count word dictionary (שעה
  through שתים עשרה שעות, "חצי"/"רבע", and "X וחצי" half-hour forms) - not exhaustive, gives
  up rather than guesses on anything outside it. Persisted `hours` MUST be numeric or `null`,
  never the raw AI-provided string. Unparseable non-null input: `שעות` left blank, a WARNING
  logged, and the original text appended to `notes` (identical fallback shape to `amount`).
  `txn_date`'s requiredness (`REQ-DATA-005`) MUST be evaluated against the AI's raw `hours`
  text (before normalization), not the normalized value - an hours entry that failed to
  normalize still needs its `txn_date`.
- **REQ-TRACE-001**: `WhatsAppHandler.handle_media_message` MUST thread
  `message.message_id` through to `MediaHandler.process_media_message` (new required
  parameter).
- **REQ-TRACE-002**: `MediaHandler.process_media_message` MUST perform ledger-event
  capture before `_store_media_turn`, so the stored message can carry `ledger_event_ids`
  at creation time.
- **REQ-TRACE-003**: `Message` (session data model) MUST gain
  `ledger_event_ids: List[str] = field(default_factory=list)`, populated with the
  `event_id`(s) of any events captured from that message, at message-creation time.
- **REQ-MIGRATE-001**: The historical session `4454746c-350a-4fa7-a5ef-fda2c685b0d5` MUST
  be migrated: its 3 combined `pending_ledger_events` records MUST become 6 new-format
  files under `data/events/` (component-split per `user-stories.md` US4), written through
  the same `LedgerEventManager.add_ledger_event` code path used by live captures (not a
  separate ad-hoc writer), and `pending_ledger_events` MUST be cleared from that session's
  `session.json`. (Revised 2026-07-30 — supersedes the original "`message_id` null on all
  6" decision): each migrated event's `message_id` MUST be the real `message_id` of its
  source message, found via the session's own `messages/*.json` files (matched by verbatim
  content + closest timestamp) — `null` is not acceptable once the real id is recoverable.
  The 3 source message files MUST also get their `ledger_event_ids` populated with the
  resulting `event_id`(s), for true two-way traceability even on migrated data. Each
  migrated `הסכם` component's `agreement_label`/`component_label` MUST be hand-written by
  whoever runs the migration (same as the existing hand-written `description`/`notes`
  values), matching real `Events.csv` style — not derived mechanically from the full-sentence
  `description` text.
- **REQ-DOC-001**: `media_handler.py`'s `sender_phone` docstring (currently shows a
  bare-digits example, contradicting verified runtime behavior which always carries the
  full JID suffix) MUST be corrected.

### Key Entities

- **`LedgerEvent`**: A persisted ledger event/component — see `data-model.md` for the full
  29-CSV-column + DeniDin-internal field list and population rules per field.
- **`Message`** (existing, extended): Gains `ledger_event_ids`.
- **`Session`** (existing, reduced): Loses `pending_ledger_events`.

## Technology Choices

**Technology Choice: Flat JSON files, one per event, under `data/events/`**
- **Decision Date**: 2026-07-29
- **Rationale**: Matches this app's existing convention exactly — `MediaFileManager`
  already uses one-flat-file-per-item under `{data_root}/media/`; no new dependency,
  no schema migration tooling, trivial for the described downstream "external
  script/human reads and merges into `Events.csv`" consumer to read/delete individual
  records.
- **Alternatives Considered**:
  - Single append-only JSONL log (`data/events/events.jsonl`) — fewer files, but harder
    for the external consumer to edit/remove one event, and needs more care for
    concurrent-write safety.
  - Writing directly into `Events.csv` — rejected outright per this session's explicit
    instruction to assume that file is not present/writable at runtime; it is a
    separately human/script-curated master file.
  - SQLite — real dependency and migration-tooling overhead for ~single-digit events per
    day at current usage; not justified.
- **Migration Path**: If per-file volume ever becomes a real concern, a future feature can
  batch-consolidate `data/events/*.json` into an indexed store without changing the
  `LedgerEventManager` public interface (`add_ledger_event` callers wouldn't need to change).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Zero ledger events exist in any `session.json` after this feature ships —
  100% of newly captured events (text or image path) land under `data/events/`.
- **SC-002**: Every file under `data/events/` contains all 30 `Events.csv`-mapped keys
  (29 original + `שעות_תאריך`, added 2026-07-30) (never a partial/missing key), verified by
  the unit test suite.
- **SC-003**: No two files under `data/events/` ever share an `event_id` (collision rate:
  0%); the >10-per-minute case is always rejected explicitly, never silently overwritten.
- **SC-004**: 100% of ledger events, including the 6 migrated ones (revised 2026-07-30 —
  originally scoped to exclude migrated events), have a non-null `message_id`.
- **SC-005**: The historical stray session has zero remaining `pending_ledger_events` and
  exactly 6 corresponding files under `data/events/`.
- **SC-006** (added 2026-07-30): 100% of `source_type=הסכם` events have non-null
  `agreement_id`/`component_id`; 100% of `source_type=בנק` events have both `null`. Every
  group of events sharing one real-world agreement (captured in one AI turn) shares
  byte-for-byte the same `agreement_id`.
- **SC-007** (added 2026-07-30): 100% of events with a non-null `hours` field have a non-null
  `שעות_תאריך` in `DD/MM/YYYY` format, correctly resolved from relative date phrases
  ("אתמול"/"היום"/etc.) rather than always equalling `event_date`.
