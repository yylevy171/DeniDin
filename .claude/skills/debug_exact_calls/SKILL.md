---
name: debug_exact_calls
description: Reconstruct the EXACT, verbatim, timestamp-ordered trace of one WhatsApp turn (or a whole test run) across all six boundaries — user↔app, app↔model, model↔Morning MCP — from existing log files. Use whenever the user asks "what did X send", "show me the exact conversation/calls", "who sent what and when", wants to trace a bug through a turn, or wants to verify a fix (e.g. after a T-numbered billed test) by inspecting the real request/response bodies rather than trusting a pass/fail alone.
---

# debug_exact_calls

Reconstructs, from **existing log files only** (never re-runs anything, never
calls OpenAI/Green API/Morning), the exact sequence of what crossed each of
six boundaries during one turn or test run, in chronological order, verbatim:

1. **user → app** — the raw inbound WhatsApp webhook (`boundary='whatsapp'
   direction='in' context='webhook'`) — text, image, interactive-button tap,
   whatever the user actually sent, exact payload.
2. **app → user** — the raw outbound WhatsApp send (`boundary='whatsapp'
   direction='out'`, any `context` — `text`/`buttons`/`reaction`/
   `progress_update`/`proactive`/`file`/etc.) — exactly what was sent, never
   a paraphrase.
3. **app → model** — the exact `responses.create()` request body
   (`boundary='openai' direction='out'`) — full `instructions` text, full
   `input` array, the `tools` list, `previous_response_id`, etc.
4. **model → app** — the exact `responses.create()` response body
   (`boundary='openai' direction='in'`) — every output item: `reasoning`,
   `message` (assistant text), `function_call` (tool name + raw arguments).
5. **model → Morning MCP** — an `mcp_call` item's `arguments` field, embedded
   *inside* one of the RECEIVED responses above (MCP calls are not logged as
   a separate line in this codebase — they only ever appear nested inside an
   `openai`/`in` response dump).
6. **Morning MCP → model** — that same `mcp_call` item's `output`/`error`
   field.

This governs **both** message pipelines in `apps/denidin-app` — the legacy
`ai_handler.py` path and the flag-gated `src/backbone/orchestrator.py` path
(Feature 063) — both call the exact same two logging functions, just under
different `context` labels (e.g. `_run_orchestration_loop (initial call)` vs
`call_capability_step[...]` vs `_call_openai_api (initial call)`). Nothing
here is backbone-specific.

## The logging this reads (2026-09-24 consolidation)

`src/utils/wire_log.py` holds the **only two** wire-logging functions in this
codebase — `audit_wire(boundary, direction, context, payload)` (INFO,
concise, prod-safe) and `debug_wire(boundary, direction, context, payload)`
(DEBUG, full byte/JSON-verbatim) — and every wire-crossing call site across
the app (`ai_handler.py`, `orchestrator.py`,
`accounting_reconciliation_service.py`, `image_extractor.py`, `denidin.py`,
`whatsapp_handler.py`, `green_api_bot.py`) calls them **directly**. There is
no third function, no per-module alias, no per-boundary wrapper anywhere
else — an earlier version of this consolidation still had five real
functions across two modules (`rawlog.py`, `whatsapp_audit_log.py`) plus a
third layer of `ai_handler.py`-local aliases re-exported cross-module; all
of that is gone. If you ever find a wire-crossing call site NOT calling
`audit_wire`/`debug_wire` directly, that's a real regression to fix, not a
style choice.

## The standing rule this exists to serve

CLAUDE.md: *"SHOW ME THE FULL CONVERSATION" MEANS VERBATIM, BOTH SIDES,
NOTHING ELSE* — no interpretation blended in, no silent substitution of a
logged intermediate value for what was actually sent/received, no
truncation. This skill's whole point is producing that raw trace correctly
and completely, every time, without hand-grepping and eyeballing timestamps
from scratch — a real, repeated source of slow/wrong answers before this
skill existed (see the session that produced it: a `previous_response_id`
instructions-retention bug that took several rounds of "no, THE VERBATIM
LOG LINE" corrections to actually pin down, and two real WhatsApp-boundary
sends — `react_to_message`'s reaction, `send_progress_update`'s interim
message — that turned out to have NO logging at all until this
investigation found the gap).

## How to run it

```bash
cd apps/denidin-app
python3 ../../.claude/skills/debug_exact_calls/scripts/parse_trace.py \
    --log logs/test_logs/<test_file>.log \
    --date YYYY-MM-DD --since HH:MM:SS --until HH:MM:SS
```

- **`--log`**: the per-test-file log (`logs/test_logs/{test_file}.log` —
  matches the test file name, auto-written by `conftest.py`) for a
  billed/expensive test, or `logs/dev/denidin.log` / `logs/prod/...` (via
  the sanctioned windows_prod log-reading scripts — never an ad-hoc ssh) for
  a real conversation. Repeatable (`--log a.log --log b.log`) if a turn's
  trace spans a rotated file boundary.
- **`--since`/`--until`** (HH:MM:SS, `--date` defaults to today): **always
  narrow the window** once you know roughly when the turn happened — these
  logs are large (multi-MB) and the script has no default cap. Find the
  rough window first with a quick `grep -n "WIRE-AUDIT\|PASSED" <log>` or
  from `scripts/run_single_test.sh`'s own timestamped output filename, then
  re-run narrowed. Omitting both parses the WHOLE file — fine for a short
  dedicated test log, likely too slow/noisy for `logs/prod/denidin.log`.
- Output is one clearly delimited, timestamped block per log line, in file
  order (= chronological), labeled by which of the six boundaries it is.
  Every `instructions`/`input`/`arguments`/`output` field is printed in
  full — never truncate it yourself when relaying to the user either.
- `parse_trace.py` also still reads pre-2026-09-24 log files (the old
  `[RAWLOG]`/`[AUDIT-IN]`/`[AUDIT-OUT]` line shapes) for backward
  compatibility — labeled "legacy format" in its output — but has no
  companion `[WIRE-DEBUG]` data for WhatsApp sends in those older logs
  (that gap didn't exist yet).

## What to do with the output

1. **Show the raw block(s) the user actually asked about first, verbatim, exactly as the script printed them** — this is the deliverable, not a
   summary of it. If the user asked a narrower question ("what did the model
   send on the second follow-up call"), give that one block's full content,
   not a table/paraphrase of it.
2. Only *after* the verbatim content, in a clearly separate section, add any
   analysis (why a call happened, what a field's value implies) — never
   blend interpretation into the "here's what was sent" answer.
3. If the six-boundary categorization itself is what's being asked
   ("who sent what and when") — walk the numbered list from `parse_trace.py`'s
   output top to bottom, one line per event: `[timestamp] <category>: <one-line gist>`,
   then offer the full verbatim block for any one of them on request. Don't
   default to dumping every full block unprompted if the user's question
   was "give me the play-by-play" rather than "show me everything."
4. A tool call whose `arguments` are malformed JSON, or a response with no
   `output_text` and no recognized item type, is itself often the finding —
   don't silently skip it; the script already prints an `other item
   type=...` line for anything it doesn't specifically recognize, surface
   that to the user rather than omitting it.

## Known gaps (don't silently paper over these — say so if hit)

- **MCP `mcp_list_tools`/`mcp_approval_request` items** are printed as raw
  JSON, not specially formatted — fine as-is (still fully verbatim), just
  don't expect a specially-labeled section for them the way `mcp_call` gets
  one.
- **This reads only what was actually logged.** If a boundary crossing
  happened with logging disabled, or in a code path that predates
  `wire_log.py` being wired at that call site, there's nothing to
  reconstruct — say that plainly rather than guessing from adjacent
  context. If you find such a gap, it's worth fixing at the source
  (a missing `audit_wire`/`debug_wire` call), the same way the
  `react_to_message`/`send_progress_update` gap was fixed — never invent a
  wrapper function to patch around it locally.
