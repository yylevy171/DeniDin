# Feature Specification: Higher Verbosity, Active Feedback, and Latency Telemetry

**Feature Branch**: `feature/080-higher-verbosity-speed`  
**Created**: 2026-09-12  
**Status**: Draft — Pending Review  
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
  The system MUST implement structured metrics gathering to record execution times. At minimum, it must track:
  - Total Time To First Byte (TTFB) / End-to-end processing time.
  - LLM Inference latency (per turn).
  - Tool execution latency (time spent running individual MCP/local tools).
  This data must be stored or logged in a structured format (e.g., JSON logs, DB telemetry table) that allows for future latency profiling and dashboarding.

### Key Entities
- **WhatsApp API / Presence Manager**: Handles the periodic 15-second "typing" keep-alive pings.
- **AI Constitution**: The prompt layer providing the directive to communicate interim status.
- **Telemetry Recorder / Logger**: New service or middleware for timing and persisting duration spans of internal processes.

## Success Criteria *(mandatory)*

### Measurable Outcomes
- **SC-001**: A request taking 45 seconds maintains a continuous "typing..." indicator on the user's WhatsApp client for the entire duration (unless interrupted by an interim progress text).
- **SC-002**: The AI autonomously dispatches at least one "progress update" text message when engaging in a known multi-turn or slow operation.
- **SC-003**: The logs/database show structured latency metrics for 100% of processed user messages, clearly separating LLM think time from tool execution time.
