# Research: Higher Verbosity, Active Feedback, and Latency Telemetry

## R1: Keep-alive renewal mechanism (REQ-080-01)

**Prior art**: Feature 048 shipped a single-call `sendTyping(chatId, typingTime=20000)` with no
renewal. A background-thread renewal loop (`TypingIndicatorRenewer`, resend every 15s, cap
180s) was built and live-tested same day, but reverted: the renewer thread's *first* call was
observed delayed by ~20s after `.start()` in at least one live test, so the indicator often
wasn't showing for most of the turn — worse than the original single-call gap in practice. Root
cause (thread-scheduling delay vs. HTTP call latency) was never pinned down before the attempt
was abandoned.

**Decision**: Implement the renewal as a job on the existing `APScheduler` `BackgroundScheduler`
pattern (already used by `reminder_delivery_service.py` and
`accounting_reconciliation_service.py`) rather than an ad-hoc `threading.Thread` renewer.
Concretely: at the start of a turn, schedule a one-off-per-tick renewal via
`scheduler.add_job(..., trigger='interval', seconds=15, next_run_time=now_local())` (explicit
`next_run_time` forces immediate first execution rather than waiting a full interval), and
remove/cancel the job the instant the turn ends (a reply is sent, mirroring feature 048's Q4
"DeniDin's turn" definition unchanged).

**Rationale**: `BackgroundScheduler` runs its own dedicated scheduler thread with an event-driven
wakeup loop (not naive `time.sleep` polling), and is already proven live in this codebase for
sub-second-to-minute-scale periodic work with no observed first-tick scheduling delay in
`reminder_delivery_service`'s `CronTrigger(minute='*/5')` or the reconciliation service's
`IntervalTrigger`. Using the same, already-battle-tested primitive — instead of a bespoke
`Thread` — directly addresses feature 048's suspected root cause class (raw thread start/
scheduling latency) without needing to first fully diagnose the old renderer's specific bug,
consistent with the user's "proceed as spec'd" direction: this substitutes a mechanism that
avoids the known failure mode rather than reusing the one already shown to fail.

**Verification requirement carried into tasks.md**: this must still be *live-tested* (real Green
API calls, per CONSTITUTION's no-mocking-external-services rule) before being trusted — feature
048's own failure was only caught by live testing, not by unit tests, so a passing unit test
suite alone is not sufficient evidence here. Flagged as a mandatory manual UAT step
(`user-stories.md` Scenario A/B), not something `speckit.implement` can mark done from tests
alone.

**Alternatives considered**:
- Reuse feature 048's raw `threading.Thread` renewer as-is, now on a shorter/different interval
  — rejected: this is the exact mechanism already shown to fail in production-adjacent testing.
- Poll from within the main request-handling flow (no background job at all, e.g. check elapsed
  time between tool-call steps and re-send inline) — rejected: doesn't cover the case of a
  single long-running tool call or LLM inference with no intermediate checkpoints, which is
  precisely the scenario (OCR/multi-page PDF) the spec's Scenario A targets.

## R2: Telemetry storage technology (REQ-080-04)

**Decision**: SQLite, one row per request, under `{data_root}/telemetry/telemetry.db` —
mirrors the existing `roll_markers.db` (Feature 070) and `reminders.db` (Feature 054) pattern
already established in this codebase for structured, queryable local state, rather than
introducing a new storage technology. `morning_api_request_times_ms` (a breakdown by endpoint)
is stored as a JSON text column, consistent with how `LedgerEvent`'s free-form fields are
already handled elsewhere.

**Rationale**: "Queryable log or database" (REQ-080-04) is satisfied by SQL `SELECT`s;
consistency with existing per-feature SQLite stores avoids introducing a new dependency (no
Postgres/Timescale needed for this scale — one row per inbound message); avoids the downsides of
JSON-lines-on-disk (no easy aggregate queries like "average tool_execution_ms this week" without
loading the whole file).

**Alternatives considered**:
- Append-only JSON-lines file under `logs/telemetry/` — rejected: harder to query in aggregate
  (SC-003 wants "logs/database show structured latency metrics", and a per-line JSON file forces
  ad-hoc parsing for every question), though simpler to write; SQLite's write cost is
  acceptable at this volume (one row per inbound message, not per LLM/tool call).
- ChromaDB (already used for `MemoryManager`) — rejected: wrong tool, telemetry is structured
  numeric/categorical data with no semantic-search use case; ChromaDB adds embedding-generation
  overhead this data doesn't need.

## R3: Where to measure LLM/tool time inside `AIHandler` (REQ-080-04)

**Decision**: Wrap every `self.client.responses.create(**kwargs)` call site already present in
`ai_handler.py` (7 call sites as of this branch, per code inspection) with a thin timing
context, and wrap tool-call dispatch (both local `type: "function"` tools and remote MCP tool
results) similarly — accumulating into one `RequestTelemetry` object threaded through the
existing per-turn call chain (`get_response` → its helpers), not a separate global/thread-local
tracker, to avoid any concurrency ambiguity across chats.

**Rationale**: `ai_handler.py` already has a consistent pattern of dedicated pre/post logging
helpers around every `responses.create()` call (`_log_...` helpers noted at the top of the
file, per existing code) — timing instrumentation follows the same "explicit call at every
existing boundary" shape, consistent with the no-monkey-patching rule, rather than wrapping the
OpenAI client itself.

**Revised during implementation (2026-09-12)**: threading an explicit `TelemetryBuilder`
parameter through every internal call site turned out to be far higher-risk than estimated at
planning time — `ai_handler.py` is 4189 lines with deeply nested, sometimes-recursive
tool-call-follow-up helpers, and rewriting all their signatures risked introducing subtle bugs
in the app's largest, most critical file for comparatively little benefit. **Switched to a
`contextvars.ContextVar[Optional[TelemetryBuilder]]`, set once at the top of
`get_response()`** (via `.set()`/`.reset()` in a `try`/`finally`, guaranteeing cleanup even on
an exception) and read by each instrumented call site via `.get()`. This is NOT the "ambient
global state" this section originally rejected: this codebase processes each request
synchronously on its own thread (no asyncio anywhere in the request path), and `contextvars`
context is thread-local by default (a `.set()` on one thread is invisible to another) — so
per-request isolation across concurrent chats is preserved exactly as intended, just via a
mechanism that adds one small context-manager helper instead of dozens of signature changes.

**Alternatives considered**:
- Monkey-patch/wrap the OpenAI client globally to auto-time every call — rejected outright,
  forbidden by CONSTITUTION's no-monkey-patching rule.
- Explicit parameter-threading through every internal call site (the original R3 decision) —
  superseded per the above: correct in principle, but a much larger and riskier diff than the
  `contextvars` approach for the same correctness guarantee, once the actual file size/call
  graph was seen during implementation.
- A genuinely global (non-contextvar) mutable accumulator — still rejected: that really would
  leak across concurrent chats on different threads, unlike a `ContextVar`.

## R4: `runtime_constitution.md` directive shape (REQ-080-02)

**Decision**: A new top-level section (working title "Proactive Progress Updates"), following
the same shape CLAUDE.md's "every new tool-bearing feature needs explicit constitution
boundaries" rule already established for reminders/ledger-query — explicit "when this applies",
"when it does not" (e.g. don't narrate on fast, single-step turns — narrating "checking..." on a
turn that resolves in 2 seconds is noise, not signal), and how it composes with the existing
"Group Conversation Etiquette" / no-reply-sentinel rules (a progress update is a real outbound
message and therefore is subject to the same group-etiquette judgment as any other reply — no
special-casing needed, but stated explicitly per the cross-reference rule).

**Rationale**: matches this repo's established, mandatory pattern for adding any new
model-facing behavioral directive (see CLAUDE.md's 2026-08-19 banner) — a generic instruction
with no explicit boundary has repeatedly caused unwanted over-triggering in this codebase
(reminders precedent).

**Alternatives considered**: none seriously — CLAUDE.md is explicit and binding that this
boundary-setting step is mandatory for any new tool/behavior-bearing constitution addition.

## R5: `feature_flags` gating

**Decision**: One flag, `feature_flags.verbosity_and_telemetry_080` (default `false`), gating
all three pieces together as a single rollout switch — keep-alive renewal, the constitution
addition (loaded conditionally), and telemetry recording. When `false`, behavior is
byte-for-byte identical to feature 048's shipped single-call typing indicator and today's
untelemetered request path.

**Rationale**: CLAUDE.md's "Feature flags for new behavior... default false" rule is explicit
and unconditional; a single flag (rather than three independent ones) matches the fact that
these three pieces ship and roll out together as one coherent UX change per the spec's own
framing, and avoids partial-rollout states (e.g. telemetry on but keep-alive off) that nobody
asked for and would complicate `tasks.md`'s incremental delivery story unnecessarily. Per-story
task breakdown in `tasks.md` can still gate sub-behaviors behind the same flag being on, without
needing separate flags.

**Alternatives considered**: three independent flags (one per user story) — rejected as
unnecessary granularity for a coherent, jointly-designed UX change; would also complicate the
Constitution-directive rollout (a directive either is or isn't part of the assembled system
prompt for a given request — an all-or-nothing decision already, per how `AIHandler` assembles
`instructions`).
