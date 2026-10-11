# User Stories: Higher Verbosity, Active Feedback, and Latency Telemetry

## Stories

### User Story 1 - The Patient Waiter (Keep-Alive) (Priority: P1)
**Given** the user submits a request that requires 40 seconds to process (e.g., heavy OCR and summarization)
**When** 20 seconds elapse since the last message
**Then** the bot MUST ensure the WhatsApp "typing..." indicator remains visible on the user's device by sending periodic presence updates to the Green API
**And** the indicator MUST only disappear once the processing is fully complete or a message is sent.

### User Story 2 - AI-Driven Progress Updates (Priority: P1)
**Given** the user asks a complex question requiring multiple internal tool calls
**When** the AI decides the task will take multiple steps (e.g., retrieving client details, then searching ledger, then drafting a response)
**Then** the AI MUST autonomously generate and send a brief, natural language update (e.g., "I'm checking the ledger for you right now...") to keep the user engaged
**And** this behavior MUST be driven generically by the system prompt/constitution rather than hardcoded edge-case handlers.

### User Story 3 - Consolidated Final Delivery (Priority: P2)
**Given** the AI has finished its internal processing and generated a substantial, 3-paragraph summary
**When** the response is dispatched to the user
**Then** it MUST be delivered as a single cohesive WhatsApp message rather than being artificially split into multiple partial messages.

### User Story 4 - Telemetry & Metrics Plumbing (Priority: P1)
**Given** a user message is fully processed by the system
**When** the execution cycle concludes
**Then** the system MUST record concrete, structured telemetry data
**And** the data MUST include end-to-end duration, total LLM inference time, and total tool execution time, stored in a queryable log or database for future performance audits.

## User Experience Testing Scenarios (UAT)

To ensure the "silent void" is effectively eliminated, the developers must manually verify the following timeline-based UX scenarios.

### Scenario A: The 45-Second Heavy Workflow (Document Upload)
**Goal**: Verify continuous typing indicator and proactive AI progress text during a long tool execution.
- **T=0s**: User sends a multi-page PDF document to DeniDin.
- **T+1s**: The bot attaches the fast-path "👀" reaction (Feature 084 logic). The WhatsApp `typing...` indicator appears on the user's screen.
- **T+5s**: The AI determines that OCR and analysis will take significant time. It autonomously dispatches a brief text: *"קיבלתי את המסמך, מתחיל לקרוא ולחלץ נתונים..."*
- **T+20s**: Behind the scenes, the system re-pings the Green API presence endpoint. The `typing...` indicator continues seamlessly without dropping.
- **T+35s**: The system pings the Green API presence endpoint again.
- **T+45s**: The internal pipeline finishes. DeniDin dispatches the final comprehensive analysis as a single cohesive message. The `typing...` indicator naturally stops. The initial "👀" reaction flips to "✅".

### Scenario B: The Multi-Step Lookup (Conversational)
**Goal**: Verify the AI constitution correctly instructs the bot to send an intermediate update when doing multi-tool research.
- **T=0s**: User asks: *"כמה הלקוח יוסי כהן שילם לנו השנה בסך הכל?"*
- **T+1s**: Bot attaches a "👍" reaction. `typing...` indicator appears.
- **T+8s**: The AI queries the client database, finds Yossi Cohen, and realizes it now needs to scan the ledger. It autonomously texts: *"שניה, אני בודק את היסטוריית התשלומים שלו ביומן..."*
- **T+20s**: The system re-pings the presence endpoint. `typing...` is maintained.
- **T+28s**: The final total is calculated and sent as a single message. `typing...` stops, and the "👍" flips to "✅".

### Scenario C: Telemetry Data Validation (Backend)
**Goal**: Verify the metrics plumbing captures the breakdown of where time was spent during Scenario A or B.
- **T=0**: Admin/Developer completes either Scenario A or B.
- **T+1**: Admin queries the new metrics log/database.
- **Expectation**: A distinct row/record exists for the processed message containing:
  - `total_duration_ms`: e.g., 28000
  - `llm_inference_ms`: e.g., 8500
  - `tool_execution_ms`: e.g., 18500
  - `tool_breakdown`: A breakdown showing exactly which tools took how long.

## Acceptance Scenarios (`billed`/`expensive`) — ✅ APPROVED by operator, 2026-09-12

Per METHODOLOGY.md §VI.a/§IV Phase -1: these are the automatable acceptance tests, described in
plain user-experience language only (no test code yet — that's written once, together, at the
end of implementation). Note: Scenarios A/B above involve a real WhatsApp on-device "typing…" indicator, which no
`pytest` assertion can observe — those two UX scenarios stay **manual-only UAT**, unchanged.

**Revised approach (per operator feedback, 2026-09-12)**: rather than write brand-new dedicated
acceptance tests, extend a **chosen subset of already-existing `billed`/`expensive` E2E tests**
with two additional assertions each, since practically every existing AI-response-driving test
in this codebase is affected by this feature's system-prompt/telemetry changes anyway. Chosen
subset: **5 `billed` + 2 `expensive`**, each already exercising a real multi-tool-call or
vision-heavy turn — a natural fit for observing progress-update behavior without inventing new
scenarios from scratch.

### Two assertions added to each chosen test (where applicable)
1. **Progress-update assertion** (Feature 080 User Story 2 / SC-002): for a turn spanning
   multiple tool calls or a slow vision/OCR step, assert DeniDin sent at least one interim
   WhatsApp text message distinct from the test's existing final-answer assertion, before that
   final answer. (Turns that resolve in a single quick tool call are **not** expected to trigger
   this — the constitution directive is judgment-based, not a hard trigger — so this assertion
   is only added to tests whose flow genuinely spans multiple steps.)
2. **Telemetry assertion** (Feature 080 User Story 4 / SC-003): assert a new
   `RequestTelemetry` row exists for the test's request(s) with plausible non-zero
   `total_duration_ms`/`llm_total_inference_time_ms`, `llm_turns_count` matching the number of
   real round-trips the test already knows it made, and (for the two `expensive` tests) a
   non-null `slowest_tool_name`/vision-call accounting.

### Chosen `billed` tests (5)
- `test_ledger_query_billed.py::test_hours_by_client_last_month` — aggregation query, closely
  mirrors Scenario B's shape (client resolution → ledger scan → computed answer).
- `test_ledger_query_billed.py::test_ambiguous_name_asks_then_both_confirmed_merges` —
  multi-turn disambiguation + merge.
- `test_denidin_morning_client_management_e2e.py::test_godfather_get_client_details_resolves_ambiguous_first_name_prefix_after_confirmation` —
  multi-tool client resolution.
- `test_denidin_morning_client_management_e2e.py::test_godfather_update_client_resolves_ambiguous_family_name_prefix_after_confirmation` —
  multi-tool client resolution + update.
- `test_denidin_morning_document_flows_e2e.py::test_create_document_for_new_client_full_flow_happy_path` —
  multi-step: client creation followed by document creation.

### Chosen `expensive` tests (2, revised again per operator feedback 2026-09-12)
- `tests/expensive/test_ledger_event_capture_e2e.py::test_given_real_bank_deposit_screenshot_when_processed_then_captured_as_bank_deposit` —
  **replaces the original AS-2 draft's PDF choice with a real bank-slip/deposit-screenshot
  image** (per operator correction), already a real vision call + multi-turn resolution detour
  in this codebase.
- `tests/expensive/test_ledger_event_capture_e2e.py::test_given_real_multi_component_agreement_image_then_components_correctly_persisted` —
  **swapped in for the multi-page-PDF pick** (per operator correction) — a real 4-component
  fee-agreement image (`Agreement-test-image.jpg`) driving client resolution + a multi-turn
  clarification detour (VAT question) before all four fee components persist; a genuinely
  multi-step, multi-tool-call vision flow, a good fit for observing a progress update.

Both chosen `expensive` tests are already in `@pytest.mark.sanity`'s current checklist — adding
assertions to them keeps the sanity suite's existing coverage intact rather than touching an
unrelated test. Each carries its own separate per-run human-approval gate at run time, same as
every other `expensive` test in this codebase.

## ⚠️ Cross-Cutting Risk: Loss of the Deterministic Single-Reply-Per-Turn Assumption

**Raised by operator, 2026-09-12 — critical, must be planned for, not discovered mid-implementation.**
Once REQ-080-02's constitution directive is live, **any** turn the AI judges as slow/multi-step
may now produce one or more extra interim WhatsApp messages before the final answer — for
**every** godfather/admin conversation, not just the handful of tests chosen above. Practically
every existing `billed`/`expensive` test in this codebase that drives a multi-tool-call AI
conversation currently assumes (implicitly or explicitly) a strict one-inbound-message →
one-outbound-reply correspondence — helpers like `_send_image`/`_drive_detour_until_captured`
and similar turn-driving helpers across the billed/expensive suites capture "the reply" as a
single value per turn. Feature 080 breaks that assumption for real, not just for the 5+2 tests
called out above: **most of the existing test suite's AI-response-handling helpers and
assertions may need to change** to tolerate zero-or-more interim messages before treating a
reply as "the" turn's answer, or the tests will start intermittently failing/misreading state the
moment this feature ships — an inherently harder problem than before, since interim-message
emission is a real model judgment call, not deterministic.

**Required task, added to the feature's scope** (not just the 5+2 acceptance tests above):
a **full sweep of `tests/billed/` and `tests/expensive/` in both apps** to (a) identify every
test/helper that assumes a single deterministic reply per driven turn, and (b) adapt each to
correctly distinguish "an interim progress update" from "the real answer" (e.g. by content/
completion signal, not just "whatever came back first") so existing assertions keep validating
what they were meant to, rather than being broken or silently made meaningless by this feature.
This is real, likely non-trivial implementation work — not a one-line assertion tweak — and must
be reflected as its own task(s) in `tasks.md` (§VI.b, unit/integration-adjacent tooling work,
since it's test-infrastructure not user-facing behavior), completed before the 5+2 acceptance
tests above are trusted to mean anything. Flagged here, at the acceptance-approval stage, so it
isn't discovered as a surprise deep into implementation.

### Explicitly out of scope for automated `billed`/`expensive` coverage
- The WhatsApp-native "typing…" dots actually staying lit on-device (Scenarios A/B's core
  UX claim) — not observable by any test; stays manual UAT per `quickstart.md`.
- Keep-alive renewal's internal re-ping cadence (every ~15s) — covered by a `unit` test on the
  renewal job itself (mocking only the external Green API call, per CONSTITUTION §I/§V), not by
  a `billed`/`expensive` test.
- Every OTHER existing `billed`/`expensive` test not in the two lists above keeps its current
  assertions unchanged for this feature — the two new assertion types are added only to the
  chosen 5+2, not codebase-wide, to keep the acceptance pass's scope bounded and reviewable.
