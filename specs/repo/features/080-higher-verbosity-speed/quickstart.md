# Quickstart: Higher Verbosity, Active Feedback, and Latency Telemetry

## Enabling the feature (once implemented)

1. In `config/config.dev.json`, set `feature_flags.verbosity_and_telemetry_080: true`.
2. Rebuild/restart `denidin-app` in `dev` (per CLAUDE.md's environment-start approval rule —
   requires explicit human go-ahead each time, same as any other environment start).
3. Send a message that triggers a slow, multi-tool-call turn (e.g. a multi-page PDF, or a
   Morning ledger question requiring several lookups).

## Manually verifying each user story

- **US1 (keep-alive)**: watch the WhatsApp client during a turn known to take >20s (e.g. a
  multi-page PDF). The typing dots must not disappear before the reply arrives (up to the
  180s cap). Cross-check `logs/denidin.log` for renewal ticks every ~15s.
- **US2 (progress updates)**: ask a multi-step question (Scenario B in `user-stories.md`).
  Expect at least one short interim Hebrew text before the final answer.
- **US3 (single final payload)**: confirm the final substantive answer arrives as one WhatsApp
  message, not split into parts (regression check only — this should already be true today).
- **US4 (telemetry)**: after a processed message, query
  `apps/denidin-app/dev_data/telemetry/telemetry.db`:
  ```sql
  sqlite3 dev_data/telemetry/telemetry.db \
    "SELECT request_id, total_duration_ms, llm_total_inference_time_ms, tool_total_execution_time_ms, slowest_tool_name FROM request_telemetry ORDER BY timestamp_received DESC LIMIT 1;"
  ```
  Confirm the row exists and the numbers are plausible against what was observed live.

## Reverting

Set the feature flag back to `false` and restart — no data migration needed, since the flag
gates recording/behavior, not schema presence (the `telemetry.db` file, if created, is simply
unused while the flag is off).
