# User Stories: Optimize the Runtime Constitution (Feature 073)

**Status**: Draft — for `speckit.clarify`. Given-When-Then, end-to-end.

This feature has **no new external entry point** — no router change, no new webhook type, no new
tool. Every user story is "the assistant behaves exactly as before, but its instruction prompt is
smaller." The stories are framed around the observable behaviours that must not regress, plus the
maintainability outcome.

---

## User Story 1 — Invoicing behaviour is unchanged (Priority: P1)

A godfather/admin manages invoices in natural Hebrew exactly as today; the compressed constitution
must not change a single refusal, clarifying question, tool choice, approval prompt, or the
"never double-count linked documents" guard.

**Why P1**: the Invoice Management section is ~45% of the file — the biggest compression target and
the biggest regression risk.

**Independent Test**: run the existing invoicing `billed`/`sanity` tests (`test_morning_*`,
`test_invoice_*`, the sanity gate) against the compressed file with no test edits → all green.

**Acceptance Scenarios**:

1. **Given** the compressed constitution is loaded, **When** a godfather sends a natural-language
   invoice request that today triggers a clarifying question ("which client?", "the invoice or a
   new one?"), **Then** the same clarifying question is asked, in the same spirit.
2. **Given** a linked credit-note / receipt scenario (bugfix-014), **When** the user asks for a
   financial total, **Then** the assistant still does not double-count the linked documents.
3. **Given** a client-not-found / ambiguous-client situation, **When** the model would act,
   **Then** it still refuses and asks rather than guessing.
4. **Given** the same 20+ invoicing scenarios in the current `billed` suite, **When** each is
   replayed, **Then** the outcome matches the pre-change outcome.

---

## User Story 2 — Ledger capture & querying behaviour is unchanged (Priority: P1)

`capture_ledger_event` classification (הסכם / בנק / neither) and `query_ledger_events` (fuzzy
criteria, ambiguous names, OR/NOT/threshold reasoning, arithmetic-is-your-job, cache-over-Morning
fallback) behave identically after the Ledger sections are compressed.

**Why P1**: the two Ledger sections are ~40% of the file combined.

**Independent Test**: the ledger `billed`/`expensive`/`sanity` tests
(`test_ledger_event_capture_e2e`, `test_ledger_query_*`, `test_group_b_reference_approval_e2e`)
pass unchanged.

**Acceptance Scenarios**:

1. **Given** a live message that today classifies as a fee agreement, **When** processed, **Then**
   it still classifies as `הסכם` and proposes the same tool call.
2. **Given** a bank-deposit image/message, **When** processed, **Then** same `בנק` classification
   and extraction.
3. **Given** an "Invoice Management action", **When** the classifier runs, **Then** it is still
   automatically "Neither" (the existing cross-boundary rule).
4. **Given** a query with an ambiguous name and an OR condition, **When** asked, **Then** the model
   returns candidates and does the OR/threshold reasoning itself, as today.
5. **Given** a zero-match ledger query for a `הסכם`/`בנק` event vs. a Morning-backed event,
   **When** asked, **Then** the model reports "not found" for the former but falls back to the
   Morning tool for the latter — the "cache over Morning" rule survives.

---

## User Story 3 — Reminder & group-etiquette boundaries are unchanged (Priority: P2)

The reminder tool-family negative scoping ("when these tools do NOT apply", ambiguous short
replies answer the pending question in the same context) and the group `[[NO_REPLY]]` etiquette
survive compression / relocation.

**Why P2**: smaller sections, but METHODOLOGY §XXI makes these boundaries load-bearing — an
ambiguous confused turn must still not misfire into a reminder tool.

**Independent Test**: reminder `billed` tests + the group-etiquette `billed` tests pass unchanged;
a confused-mid-flow scenario still does not invent a reminder call.

**Acceptance Scenarios**:

1. **Given** a Morning client-management flow that goes ambiguous mid-turn, **When** the model
   responds, **Then** it does not reach for a reminder tool (the §XXI incident).
2. **Given** a bare "כן" / "לא" / a name, **When** received, **Then** it answers the most recently
   pending question in the same context — not a reinterpretation into another tool domain.
3. **Given** a group message clearly addressed to someone else, **When** received, **Then** the
   assistant still replies `[[NO_REPLY]]`.

---

## User Story 4 — The file has a standing size budget (Priority: P2)

A maintainer can see the constitution's token count against a budget and is warned before it
silently balloons again.

**Why P2**: prevents the regression that created this feature (13 months of additive-only edits).

**Independent Test**: run the size check on the compressed file → under budget, exit clean; add a
padding paragraph in a scratch copy → the check flags it.

**Acceptance Scenarios**:

1. **Given** the compressed constitution, **When** the size check runs, **Then** it reports the
   `o200k_base` token count and confirms it is within budget.
2. **Given** an edit that pushes the file over budget, **When** the check runs, **Then** it flags
   (non-blocking) with the current count, the budget, and the overage.
3. **Given** CLAUDE.md, **When** a developer reads the constitution note, **Then** it states the
   real current token count and the budget (not the stale "~4.0K").

---

## Out of scope for these stories

- Any change to tool schemas' *behaviour*, RBAC, `_build_instructions` assembly order, the
  RECALLED MEMORIES block placement, or splitting the file.
- Governance docs (`CONSTITUTION.md`, `METHODOLOGY.md`).
