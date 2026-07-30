# User Stories: Ledger Event Recognition

**Feature**: 024-ledger-event-recognition
**Format**: Given-When-Then (Gherkin/BDD), per METHODOLOGY.md §I.
**Status**: Reconstructed retroactively, 2026-07-30 — see spec.md's "Provenance" section for
exactly how this was sourced and why it's a faithful reconstruction, not a guess.

---

## User Story 1 — A godfather/admin states a new fee agreement by text (Priority: P1)

A godfather/admin sends a WhatsApp text message stating a new fee arrangement with a client
("X 5,000₪ כתב הגנה"). DeniDin should recognize this as a ledger-worthy event, extract its
fields, and record it for later bookkeeping review — without that recognition replacing the
user's normal conversational reply.

**Why this priority**: The core capability the whole feature exists for.

**Independent Test**: Send a real text message stating a new fee agreement to a
godfather-role session; verify `capture_ledger_event` is called with `source_type=הסכם`,
`event_subtype=יצירה`, and the correct client/amount/VAT fields, AND that the user still
receives their normal conversational reply in the same turn.

**Acceptance Scenarios**:

1. **Given** a godfather sends "רונית כהן - הצעת שכר טרחה לכתב הגנה: 9,000 ₪ כולל מעמ",
   **When** the model classifies the message, **Then** `capture_ledger_event` is called with
   `source_type=הסכם`, `client_name` containing "רונית כהן", `amount` verbatim "9,000 ₪" (no
   currency conversion or math performed by the model), and `vat_status=כולל`.
2. **Given** the same turn, **When** the tool call completes, **Then** the user still
   receives an ordinary reply in Hebrew restating the key captured fields (client, amount,
   VAT status) so they can verify/correct the capture at a glance.
3. **Given** an ordinary conversational message with no money/engagement content ("מה קורה?
   מוכנה לפגישה של מחר?"), **When** processed, **Then** `capture_ledger_event` is NOT called
   — a missed capture is explicitly preferred over a false one (constitution Step 1).

---

## User Story 2 — A bank-deposit confirmation or fee-agreement document arrives as an image (Priority: P1)

A godfather/admin sends a photo of a bank-transfer confirmation, or a photo/scan of a signed
fee-agreement letter. The same recognition must work via the image pipeline
(`ImageExtractor`), not just plain text.

**Why this priority**: Equal priority to US1 — the constitution treats text and image as two
sources of the same mechanism; a real fee agreement is as likely to arrive as a photographed
document as a typed message.

**Independent Test**: Send a real bank-transfer-confirmation image; verify
`capture_ledger_event` is called with `source_type=בנק`, `event_subtype=הפקדה`, and the
correct amount.

**Acceptance Scenarios**:

1. **Given** a bank-transfer confirmation screenshot showing a real deposit, **When** the
   vision model processes it, **Then** `capture_ledger_event` is called with
   `source_type=בנק`, `event_subtype=הפקדה` (always, for bank events), and `amount` matching
   the screenshot verbatim.
2. **Given** a signed fee-agreement document image, **When** processed, **Then**
   `capture_ledger_event` is called with `source_type=הסכם` and fields matching the
   document's real content, with `raw_message_excerpt` containing a precise description of
   the image content (the "hard pointer" for later verification — same requirement as the
   text path).
3. **Given** an image with no ledger-worthy content (a personal photo, an unrelated
   document), **When** processed, **Then** `capture_ledger_event` is NOT called.

---

## User Story 3 — A single message with multiple distinct ledger-worthy entries produces multiple captures (Priority: P1)

A message states more than one ledger-worthy entry in one turn (e.g. two separate hourly
work-log mentions, "3 שעות היום" and a separate unrelated deposit mention). The model must
call `capture_ledger_event` once per distinct entry, never aggregating them into one call —
and the follow-up round-trip that gets the model's actual reply must resolve ALL of them, not
just the first (a real bug found and fixed this session, per the commit message: unresolved
calls beyond the first caused OpenAI to reject the whole follow-up with "No tool output found
for function call ...").

**Why this priority**: Without this, multi-entry messages either lose data (only first entry
captured) or crash the turn entirely (unresolved follow-up calls rejected by the API) —
directly blocking US1/US2 from being reliable.

**Independent Test**: Send a message with 2 distinct hourly work-log mentions for the same
client on different days; verify 2 separate `capture_ledger_event` calls are made AND
resolved, and the user still receives a real reply (not a crashed/empty turn).

**Acceptance Scenarios**:

1. **Given** a message with 2 distinct ledger-worthy mentions, **When** the model responds
   with 2 `capture_ledger_event` calls in one turn, **Then** both are resolved in the same
   follow-up round-trip (not just the first), and the user receives one real reply covering
   both.
2. **Given** the same scenario, **When** inspected, **Then** the two captures are never
   merged/summed into one combined event — hourly work-log entries are explicitly first-class
   events, one per occurrence, even for the same client on the same day.

---

## User Story 4 — Morning-MCP-sourced data does not produce false-positive captures (Priority: P2)

A godfather/admin asks DeniDin to list or summarize their existing invoices (via the Morning
MCP remote tool). The model, reading its own `list_invoices`/`get_invoice_details` tool
output back, must not mistake pre-existing Morning documents for new fee-agreement text
stated in the chat — and even if it tries to, the turn must not end in a completely empty
reply (a real bug found this session: the follow-up round retriggered
`capture_ledger_event` instead of finally answering, silently losing the user's reply
entirely).

**Why this priority**: Found live, mid-session, as a real defect blocking normal Morning MCP
usage for godfather/admin users — high severity despite being discovered incidentally rather
than planned upfront.

**Independent Test**: Ask a godfather session "list all my invoices" for a client with
existing Morning documents; verify no `capture_ledger_event` call is persisted for
Morning-sourced content, and the user receives a real, non-empty reply.

**Acceptance Scenarios**:

1. **Given** a turn where Morning MCP was used as the data source (a real `mcp_call` item is
   present in the response), **When** the model also emits `capture_ledger_event` call(s),
   **Then** those captures are suppressed — not persisted to the ledger.
2. **Given** the same turn, **When** the follow-up round-trip is built, **Then** the ledger
   tool is stripped from that round's available tools (so the model cannot repeat the same
   mistake), forcing it to produce its actual text reply instead.
3. **Given** this suppression, **When** the turn completes, **Then** the user still receives
   their real answer (e.g. the actual invoice list) — never a blank/lost reply.

**Note**: genuinely capturing Morning-sourced ledger events (as opposed to suppressing
false-positives from them) is explicitly out of scope — tracked as its own follow-on feature,
`specs/backlog/025-morning-sourced-ledger-events/`.

---

## Explicitly Out of Scope (per the shipped constitution text and HANDOFF.md)

- Writing to any ledger file directly — the model/tool call only records a candidate; a
  human/script reviews and merges it later (this scope stayed true through Feature 026,
  which changed *where* the candidate is stored, not this principle).
- Resolving `replaces_hint`/corrections to a real prior event ID — the model has no access to
  the full historical ledger, so `replaces_hint` stays free text for downstream resolution
  (later formalized as the `"צריך למצוא"` placeholder mechanism in Feature 026, REQ-DATA-002).
- Genuinely capturing Morning-sourced ledger events (see US4's note above) — `specs/backlog/025-...`.
- Assigning the final ledger ID (`A`/`B`/`H` + `DDMMYY` + `HHMM` + sequence digit) — always
  code-computed downstream, never by the model (later formalized as `event_id` generation in
  Feature 026, REQ-ID-001).
