# Feature Specification: Higher Verbosity, Active Feedback, and Latency Telemetry

**Feature Branch**: `feature/080-higher-verbosity-speed`  
**Created**: 2026-09-12  
**Status**: Done (2026-09-13). `speckit.plan`/`speckit.tasks`/`speckit.implement` Phases 0-5
(T001-T018) implemented and green; Phase 6/7 (cross-cutting test-helper audit + billed/expensive
acceptance tests) explicitly deferred by operator decision in favor of repeated real-WhatsApp
manual live testing against the dev environment, which verified the feature end-to-end and
surfaced/fixed three real bugs a written-inventory audit alone would not have caught: (1) the
local-tool dispatch loop rejecting any response carrying more than one pending tool call type at
once (react_to_message, unconditionally attached by a separately-merged feature, colliding with
query_ledger_events/list_reminders/send_progress_update); (2) a typing-indicator renewal gap
caused by Green API's own `sendTyping` latency interacting with the renewal job's scheduling
(fixed via cadence, not duration - `typingTime` is capped at 20000ms by Green API itself); (3) a
rogue-language leak (a reply mixing in a non-Hebrew script mid-sentence), fixed via a broadened
constitution guard. `verbosity_and_telemetry_080` (the feature flag originally planned in Phase 0)
was removed entirely on 2026-09-12, per explicit operator instruction - the feature is
unconditionally always-on, never flag-gated. PR #315.  
**Input**: User description: "Higher verbosoty and speed, multiple replies per user message." Revised: Continuous feedback, keeping user in the loop via AI constitution, keep-alive typing indicator, and gather latency metrics plumbing.

---

**CRITICAL - MANDATORY REQUIREMENT**:
🚨 **This feature MUST have a separate `user-stories.md` file** before spec approval:
- ✅ **`user-stories.md`** exists and conforms to Given-When-Then standard.

---

## Executive Summary

When complex workflows (OCR, multiple tool calls) take 30–60 seconds, users experience a "silent void." WhatsApp drops the "typing..." indicator after 20 seconds, leading users to believe the bot has crashed or ignored them. Furthermore, we lack concrete data on exactly *why* and *where* these latency bottlenecks occur. 

This feature addresses both perceived latency (UX) and actual latency (Telemetry) by:
1. Ensuring the WhatsApp typing indicator never drops prematurely.
2. Directing the AI (via constitution) to proactively communicate intermediate progress updates.
3. Building the foundational metrics plumbing to measure end-to-end and tool-specific latency.

## Requirements *(mandatory)*

### Functional Requirements

- **REQ-080-01: Continuous Typing Keep-Alive**  
  The system MUST periodically re-trigger the WhatsApp "typing" status (e.g., every 15 seconds) while a request is actively being processed, ensuring the indicator does not drop until a textual response is dispatched.
  
- **REQ-080-02: AI-Driven Progress Feedback (Verbosity)**  
  The `runtime_constitution.md` MUST be updated with a generic behavioral directive. The AI must be instructed to proactively keep the user in the loop during complex or multi-step operations (e.g., sending short updates like "בודק את המסמכים..." or "מזהה לקוח..."). This should be driven by the AI's contextual awareness of time and milestones, not by rigid hardcoded triggers.

- **REQ-080-03: Single Final Payload**  
  Contrary to earlier assumptions, the system MUST NOT arbitrarily chunk or split final substantive responses. Final responses should be delivered intact as a single message.

- **REQ-080-04: Latency Telemetry Plumbing**  
  The system MUST implement structured metrics gathering to record execution times for every user request. The telemetry payload MUST be stored in a queryable log or database, and MUST specifically capture:
  - `request_id`: Unique identifier for the user's message/workflow.
  - `timestamp_received`: Exact time the webhook was received.
  - `total_duration_ms`: End-to-end time until the final message is dispatched.
  - `llm_total_inference_time_ms`: Aggregate time spent waiting for LLM completions.
  - `llm_turns_count`: Number of back-and-forth roundtrips to the LLM.
  - `tool_total_execution_time_ms`: Aggregate time spent executing external/internal tools.
  - `tool_calls_count`: Total number of tools invoked during the workflow.
  - `slowest_tool_name`: The specific tool that consumed the most time (e.g., `extract_doc`, `search_ledger`).
  - `slowest_tool_duration_ms`: Execution time of that slowest tool.
  - `morning_api_request_times_ms`: Breakdown of downstream Morning API latency categorized by endpoint type (e.g., `list_clients: 300ms`, `get_document_details: 1200ms`).
  - `input_tokens_count` / `output_tokens_count`: To correlate latency with context size and generation length.
### Key Entities
- **WhatsApp API / Presence Manager**: Handles the periodic 15-second "typing" keep-alive pings.
- **AI Constitution**: The prompt layer providing the directive to communicate interim status.
- **Telemetry Recorder / Logger**: New service or middleware for timing and persisting duration spans of internal processes.

## Success Criteria *(mandatory)*

### Measurable Outcomes
- **SC-001**: A request taking 45 seconds maintains a continuous "typing..." indicator on the user's WhatsApp client for the entire duration (unless interrupted by an interim progress text).
- **SC-002**: The AI autonomously dispatches at least one "progress update" text message when engaging in a known multi-turn or slow operation.
- **SC-003**: The logs/database show structured latency metrics for 100% of processed user messages, clearly separating LLM think time from tool execution time.
