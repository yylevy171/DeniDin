# Integration Contracts: Ledger Event Persistence

**Feature**: 033-ledger-event-persistence · Per METHODOLOGY.md §VII format.

---

### `AIHandler` ↔ `LedgerEventManager` Contract

**`AIHandler` MUST**:
- (Revised 2026-07-30, REQ-DATA-006) Call
  `LedgerEventManager.add_ledger_events_from_call(...)` once per resolved
  `capture_ledger_event` call in `_handle_ledger_event_capture` — normally exactly one call
  per turn, since a single call's `components` array now carries all of one agreement's
  components (superseding the original "one `add_ledger_event` call per component, driven
  by the model making N separate tool calls" design — proven unreliable, see spec.md's
  third addendum). The outer loop over resolved calls still exists for the rare case of
  genuinely multiple SEPARATE calls in one turn (e.g. two unrelated clients).
- Pass `session_id`, `whatsapp_chat`, the raw call arguments dict (unmodified — top-level
  agreement fields plus the nested `components` list), `request.message_id`,
  `request.timestamp` (as `message_timestamp`), and `sender`.
- Collect the `event_id`(s) returned (a list, one per persisted component) and pass them to
  the `SessionManager.add_message`/`add_message_with_token_limit` call that stores the
  source user message, as `ledger_event_ids`.
- (Added 2026-08-02, REQ-DATA-008, image path only) `capture_ledger_events_from_text` MUST
  retry its classification call exactly once, with an explicit corrective message, when the
  first response `is_incomplete_capture` — before returning to its caller. The text path
  (tool attached directly to the main conversational call, resolved via
  `_handle_ledger_event_capture`'s follow-up round-trip) does NOT get this retry — it's
  architecturally more complex to retry mid-conversation without disrupting the user's
  actual reply — but is still protected against silent data loss by
  `add_ledger_events_from_call`'s own fallback below, since both paths persist through it.

**`LedgerEventManager` PROVIDES**:
- `add_ledger_events_from_call(session_id, whatsapp_chat, call_arguments, message_id,
  message_timestamp, sender) -> List[str]` (added 2026-07-30, REQ-DATA-006) — the primary
  entry point callers now use. Pops `components` off `call_arguments` (never mutates the
  caller's dict), computes `agreement_id` **once** for the whole call (via
  `build_agreement_id`, using the first component's context — only when
  `source_type=הסכם`), then merges each component with the remaining shared/agreement-level
  fields into the same flat shape `add_ledger_event` already expects, and persists each via
  `add_ledger_event`. Returns the list of persisted `event_id`s in component order (may be
  shorter than the components list if any hit REQ-ID-003's rare exhaustion case — logged
  internally, never raises for that).
- `add_ledger_event(session_id, whatsapp_chat, event, message_id, message_timestamp,
  sender, agreement_id=None) -> Optional[str]` — **unchanged** by the 2026-07-30
  components-array redesign; still the low-level single-event persist primitive
  `add_ledger_events_from_call` calls internally, and still used directly by the migration
  script (which has no `capture_ledger_event` call to flatten — it hand-builds each
  component). The new `event_id` on success, `None` on the REQ-ID-003 exhaustion case
  (logged as ERROR internally; caller doesn't need to inspect why). `agreement_id`: if the
  caller supplies one (batch case), used as-is; if omitted (a standalone, non-batched
  capture), the manager derives a fresh one itself from that single event's own
  `client_name`/`agreement_label`. Ignored entirely when `event["source_type"] == "בנק"`
  (both `agreement_id`/`component_id` always `null` for bank events).
- `build_agreement_id(client_name, agreement_label, message_timestamp) -> str` (added
  2026-07-30) — the pure, stateless function implementing REQ-DATA-004's format
  (`"{MMYY}-{slugify(client_name)}-{slugify(agreement_label)}"`), exposed as a manager
  method (not a private helper) so callers can compute it once per batch without
  duplicating slug logic.
- On success: a file at `data/events/{event_id}.json` matching `data-model.md` exactly,
  written atomically (temp file + rename, matching this app's existing session-write
  pattern) so a crash mid-write never leaves a partial/corrupt event file.
- Deterministic, collision-free `event_id`s scoped to its own `storage_dir` (REQ-ID-002).
- (Added 2026-08-02, REQ-DATA-008) `is_incomplete_capture(call_arguments) -> bool` — pure,
  stateless: `True` when `components` is empty, or `component_count` is present and
  `len(components)` doesn't match it. Shared by `AIHandler.capture_ledger_events_from_text`
  (decides whether to retry the classification call once) and by
  `add_ledger_events_from_call` itself (decides whether it needs its own fallback below) -
  both agree on exactly what "incomplete" means.
- (Added 2026-08-02, REQ-DATA-008) `add_ledger_events_from_call` NEVER silently returns an
  empty list when the call indicated a real event: if `components` is empty (even after any
  upstream retry), it persists exactly ONE fallback `LedgerEvent` from the call's
  agreement-level fields alone, `notes="AI capture returned zero components (even after a
  retry) - needs manual review against the original message/image."`, and logs an ERROR — a
  real, observed billed failure (2026-07-31, the Mor ben-Shaya 6-component test) previously
  persisted nothing and logged nothing. A non-empty but `component_count`-mismatched
  `components` is persisted exactly as given (real data is never dropped) with an ERROR
  logged for human review — no fabrication, no silent drop, either way.

**`LedgerEventManager` EXPECTS**:
- `event` dict has exactly `LEDGER_EVENT_TOOL`'s schema's merged shared+component shape (18
  keys as of 2026-08-02 — `component_count` is popped by `add_ledger_events_from_call`
  before merging and never reaches this flat shape) — no validation of upstream tool-schema
  correctness is this component's job (AIHandler/the model already own that via
  `strict: True` function-calling).
- (Added 2026-07-30, summary.md-derived enhancement; unified same day — see spec.md
  Clarifications) `txn_date` covers two cases sharing one field: an hourly work-log
  component's worked-date (required non-null whenever the AI's raw `hours` text is non-null,
  evaluated before `hours` normalization) and a בנק component's own stated transaction/value
  date (always optional). Both normalized via the same `_normalize_iso_date` helper;
  unparseable/missing-when-required input is dropped with a WARNING, never guessed.
- (Added 2026-08-02, REQ-DATA-009) `hours` is normalized via `_normalize_hours` (digit
  strings plus a bounded Hebrew hour-count word dictionary) - persisted `hours` is always
  numeric or `null`, never the AI's raw string. Unparseable non-null input is dropped with a
  WARNING, original text preserved in `notes` - same fallback shape as `amount`.
- `message_timestamp` is a Unix epoch int or `None` (falls back to processing time per
  spec.md Edge Cases, with a WARNING).

---

### `MediaHandler` ↔ `LedgerEventManager` Contract

Same method contract as above (`MediaHandler` calls the same
`LedgerEventManager.add_ledger_events_from_call`, not a separate path) — no divergent
behavior between text and image capture at the persistence layer (US2's whole point).
`ImageExtractor.capture_ledger_events_from_text` returns a `List[Dict]` (normally 0 or 1
raw call-arguments dicts, each with its own nested `components`) - `MediaHandler` loops
over that list calling `add_ledger_events_from_call` once per call, exactly mirroring
`AIHandler._handle_ledger_event_capture`'s own loop.

**`MediaHandler` MUST additionally**:
- Perform the `add_ledger_events_from_call` call(s) **before** `_store_media_turn`
  (REQ-TRACE-002), so the stored message can carry `ledger_event_ids` at creation time.

---

### `WhatsAppHandler` ↔ `MediaHandler` Contract (amended)

**`WhatsAppHandler` MUST**:
- Pass `message.message_id` (already parsed from the Green API notification) as a new
  `message_id` parameter to `MediaHandler.process_media_message` (REQ-TRACE-001) — this
  parameter does not exist today.

**`MediaHandler` EXPECTS**:
- `message_id` to be a valid string matching the same id used for the stored message record
  (so `LedgerEvent.message_id` and `Message.message_id` agree).

---

### `SessionManager` ↔ `Message` Contract (amended)

**Callers of `add_message`/`add_message_with_token_limit` MUST**:
- Pass `ledger_event_ids: List[str]` (defaulting to `[]`) alongside existing parameters,
  for the message that triggered any capture(s) this turn.

**`SessionManager` PROVIDES**:
- `Message.ledger_event_ids` persisted and reloaded exactly as given, same as every other
  `Message` field — no special-casing.

---

### Migration script ↔ `LedgerEventManager` Contract

**The one-off migration script MUST**:
- Call `LedgerEventManager.add_ledger_event` for each of the 6 reconstructed component
  events (REQ-MIGRATE-001) — MUST NOT write `data/events/*.json` files directly/by hand,
  so migrated files are guaranteed schema-identical to normally-captured ones.
- (Revised 2026-07-30 — supersedes the line below) Pass each component's real `message_id`,
  recovered by matching verbatim content against the session's own `messages/*.json` files
  (never `None` — see `data-model.md`'s migration appendix for the 3 resolved ids).
- ~~Pass `message_id=None` explicitly for all 6 (never recorded by the old capture path).~~
  (superseded 2026-07-30)
- (Added 2026-07-30) For the 3 `הסכם` components sharing one source message, compute
  `agreement_id` once via `LedgerEventManager.build_agreement_id` and pass it identically
  into all 3 `add_ledger_event` calls for that record — same batch rule as the live path.
- (Added 2026-07-30) After all 6 succeed, also patch the 3 source message files'
  `ledger_event_ids` to include the resulting `event_id`(s), for two-way traceability on
  migrated data too.
- (Added 2026-07-30) `notes` text MUST contain only substantive ambiguity content — never
  migration/process commentary about Feature 033 itself.
- After all 6 succeed, clear `pending_ledger_events` from
  `dev_data/sessions/4454746c-350a-4fa7-a5ef-fda2c685b0d5/session.json` (only after
  confirmed success — never clear-then-write).
