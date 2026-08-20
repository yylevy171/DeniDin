# User Stories: Ledger Event Querying via AI

**Feature Branch**: `feature/044-ledger-event-querying`
**Depends on**: Feature 033 (`specs/done/v0.2.0/033-ledger-event-persistence/`) — this feature reads
the `{data_root}/events/*.json` records that 033 already writes; it adds no new event fields
and does not change capture behavior.

---

### User Story 1 - Answer a question about a specific client/agreement from the ledger (Priority: P1)

A godfather/admin asks DeniDin, in natural language (Hebrew or English), about a past fee
agreement or ledger event — e.g. "כמה סוכם עם הסתדרות על צו מניעה?" ("how much was agreed
with Histadrut re the restraining order?") — without re-pasting the original agreement message.

**Why this priority**: This is the core value of the feature — today DeniDin can *write*
ledger events (Feature 033) but has no way to *read* them back in conversation; the only way
to answer this question today is a human manually opening the JSON files (as happened in the
investigation that motivated this feature). Without this story the feature delivers nothing.

**Independent Test**: With at least one ledger event already captured for a given client, ask
DeniDin (as godfather/admin) a natural-language question that only that event can answer, in
a fresh session with no prior mention of the agreement, and confirm the reply is correct and
sourced from the matching event(s).

**Acceptance Scenarios**:

1. **Given** a captured ledger event for client "הסתדרות" / agreement "צו מניעה" with amount
   ₪40,000, **When** a godfather asks "כמה סוכם עם הסתדרות על צו מניעה?" in a session that has
   never mentioned this agreement, **Then** DeniDin's reply states the ₪40,000 figure, sourced
   from the query tool's result, not from session/session-memory context.
2. **Given** no ledger event exists for the client/matter named in the question, **When** the
   godfather asks about it, **Then** DeniDin replies that it found no matching ledger record,
   rather than fabricating an answer.
3. **Given** the two-events-for-one-correction case seen in production (`A05082620170.json` /
   `A05082620180.json` — a same-session VAT correction that produced a second event instead of
   superseding the first, per Feature 040's future fix), **When** asked about that agreement
   today (before Feature 040 ships), **Then** the query tool returns both matching events and
   DeniDin does not need to silently pick one — it may surface the discrepancy or use the more
   recent `captured_at`, but must not merge or drop either event's data silently.

---

### User Story 2 - Answer a date-ranged or multi-event summary question (Priority: P2)

A godfather/admin asks a question that reasonably matches more than one ledger event — e.g.
"אילו הסכמים נסגרו החודש?" ("which agreements were closed this month?") or "מה יש לנו פתוח מול
לקוח X?" ("what's outstanding with client X?").

**Why this priority**: Extends US1 from a single-event lookup to the realistic case of
multiple matches, which is where "don't send the whole ledger as context" actually matters —
a single-event answer could almost be brute-forced by dumping everything, but a multi-event
summary cannot scale that way once the ledger grows toward the expected "a few thousand
events" ceiling.

**Independent Test**: With several ledger events captured across different clients/dates,
ask a question whose correct answer requires aggregating/filtering more than one event, and
confirm the reply reflects all and only the matching events.

**Acceptance Scenarios**:

1. **Given** 5 ledger events for client X across the last 3 months and 10 events for other
   clients, **When** asked "what has client X agreed to recently?", **Then** the reply
   reflects exactly client X's 5 events, not the other 10.
2. **Given** a query whose filters match far more events than are reasonable to reason about
   in one reply (see Open Questions — exact threshold TBD), **When** the godfather asks a
   maximally broad question (e.g. "list every ledger event ever"), **Then** DeniDin does not
   silently truncate without saying so — it either narrows/asks a follow-up question or states
   that the result was capped, per whatever behavior is decided in clarification.

---

### User Story 3 - Ledger querying is denied to unauthorized roles (Priority: P2)

A client-role (non-godfather/admin) user asks a ledger question.

**Why this priority**: Ledger events contain financial agreement terms; this is a regression
guard ensuring the new read path doesn't accidentally bypass the RBAC boundary that already
gates ledger *writes* (`capture_ledger_event`) and the Morning MCP tools.

**Independent Test**: As a client-role user, ask a ledger question that a godfather could
answer via US1, and confirm the query tool is not invoked / DeniDin does not disclose
ledger data the user isn't authorized to see.

**Acceptance Scenarios**:

1. **Given** a client-role user in a 1:1 chat, **When** they ask about another client's fee
   agreement, **Then** DeniDin does not call the query tool (RBAC gate mirrors existing tool
   attachment logic) and does not disclose the agreement's terms.

---

### Edge Cases

- The in-memory ledger index has not finished loading yet (e.g. a query arrives in the small
  window right after process startup, before startup recovery completes) — the tool must fail
  gracefully (e.g. "not ready yet" or falling back to an on-disk read), not crash the turn.
- A ledger event is captured by one conversation while a query from a different, concurrent
  conversation is in flight — the query must not return a torn/partial read, per Feature 034's
  general reliability bar, but does not need to guarantee the brand-new event is included if
  the race is exact.
- Malformed/corrupted event JSON on disk (should not normally happen, but Feature 033's
  persistence is filesystem-based, not transactional) — the index load must skip and log a
  corrupt file rather than fail the entire index / entire app startup.
