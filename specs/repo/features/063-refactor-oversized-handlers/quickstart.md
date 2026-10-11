# Quickstart: The Dynamic Capability Backbone (063)

## Enabling the new path (dev only, human-approved per CLAUDE.md's environment-start rule)

1. In `config/config.dev.json`, set `feature_flags.enable_capability_backbone: true` and add a
   `backbone_config` block (`data-model.md`'s Config additions) — `constitution_config` (used by
   the untouched `AIHandler`) is left exactly as it is.
2. Ensure `config/prompts/backbone.md` + `config/prompts/capabilities/*.md` (one per `CapabilityTag`, see `data-model.md`) exist — `speckit.tasks` produces these
   as **new** files, authored fresh from the Capability Plugin Taxonomy in `spec.md` (not a
   split/move of `runtime_constitution.md`, `ledger_recognition_prompt.md`, or
   `prompts/image_analysis.txt`/`docx_analysis.txt`, all of which stay untouched and continue to
   serve the legacy path only).
3. Rebuild and restart `denidin-app-dev` (per CLAUDE.md's "Merging a code fix to master does not
   redeploy it" — this is a code+config change, needs an explicit rebuild, explicit approval each
   time per the environment-start rule).

## Verifying it worked

- Send a small-talk message → check `logs/denidin.log`: one model call whose `capabilities=` list is
  empty (`(none - plain backbone)`), ending in `send_to_user`.
- Send a Ledger Query question → the log shows the model calling `load_flows(["ledger_question"])` then `load_capabilities(["cap_ledger_query"])`,
  then a follow-up call whose `capabilities=` includes `cap_ledger_query` and whose tools include
  `query_ledger_events` (instructions and tools are rebuilt from the persisted set every call).
- Send an image containing a fee-agreement note → the model loads `cap_media_analysis` and calls
  `analyze_media` (the same unmodified `ImageExtractor`); ledger capture happens in denidin.py's
  shared post-turn recognition (REQ-063-04a — media enters through this same backbone, not a
  separate deterministic pre-route).
- Send a follow-up message in the same chat → the previously loaded capabilities are still listed
  (persisted `Session.active_capabilities`) until unloaded, reset, or the idle sweep clears them.
- Run `scripts/model_sanity_check.sh --config config/config.dev.json` (new mode from research.md
  R6) for the cache-hit/instrumentation proof: confirm `cached_tokens > 0` on the second of two
  back-to-back calls sharing the same loaded set — this is what REQ-063-06's stable-prefix
  property predicts. Billed, human-approved
  per run.

## Rolling back

Set `feature_flags.enable_capability_backbone` back to `false` and rebuild/restart —
`initialize_app` constructs the untouched `AIHandler` again, reading the untouched
`runtime_constitution.md`/`ledger_recognition_prompt.md`/`prompts/*.txt` again, and media messages
route straight back to `WhatsAppHandler.handle_media_message()` unchanged. No data migration
involved (no persisted data changed shape); the rollback is as safe as it is precisely because the
legacy path was never modified in the first place (REQ-063-07).

## Full regression gate

`python3 -m pytest tests/ -v --tb=short` (unit/integration — `ai_handler.py`'s existing unit tests
are trivially unaffected since the file didn't change; the new `src/backbone/`/`src/capabilities/`
code's own new unit tests run alongside) + `./scripts/run_sanity.sh` (billed sanity) + the full
`tests/billed/`/`tests/expensive/` suites per REQ-063-05/SC-003 (per the §VI.a decision in
`user-stories.md`, this existing suite — unmodified — is the entire acceptance gate; no new
`billed`/`expensive` tests are added for this refactor) — run with the flag **off** first (must
match today's production baseline exactly — this is closer to a formality than a real test, since
the code path is untouched, but confirms the flag's default doesn't accidentally select the new
backbone), then with the flag **on** in `dev` (must also pass 100%, proving the new,
independently-built path — including its media-message entry point — is behaviorally equivalent to
the legacy one it parallels).
