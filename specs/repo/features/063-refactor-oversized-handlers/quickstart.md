# Quickstart: The Dynamic Capability Backbone (063)

## Enabling the new path (dev only, human-approved per CLAUDE.md's environment-start rule)

1. In `config/config.dev.json`, set `feature_flags.enable_capability_backbone: true` and add a
   `backbone_config` block (`data-model.md`'s Config additions) — `constitution_config` (used by
   the untouched `AIHandler`) is left exactly as it is.
2. Ensure `config/capabilities/*.md` (6 files) + `config/backbone.md` exist —
   `speckit.tasks` produces these as **new** files, authored fresh from the Capability Plugin
   Taxonomy in `spec.md` (not a split/move of `runtime_constitution.md`, which stays untouched).
3. Rebuild and restart `denidin-app-dev` (per CLAUDE.md's "Merging a code fix to master does not
   redeploy it" — this is a code+config change, needs an explicit rebuild, explicit approval each
   time per the environment-start rule).

## Verifying it worked

- Send a small-talk message → check `logs/denidin.log` for the turn's `instructions` size (should
  be roughly Backbone-only, i.e. much smaller than the pre-refactor single-file constitution).
- Send a Ledger Query question → check the same log line shows the Ledger-Query plugin's content
  length added in.
- Run `scripts/model_sanity_check.sh --config config/config.dev.json` (new mode from research.md
  R6) for the cache-hit/instrumentation proof — billed, human-approved per run.

## Rolling back

Set `feature_flags.enable_capability_backbone` back to `false` and rebuild/restart —
`initialize_app` constructs the untouched `AIHandler` again, reading the untouched
`runtime_constitution.md` again. No data migration involved (no persisted data changed shape); the
rollback is as safe as it is precisely because the legacy path was never modified in the first
place (REQ-063-07).

## Full regression gate

`python3 -m pytest tests/ -v --tb=short` (unit/integration — `ai_handler.py`'s existing unit tests
are trivially unaffected since the file didn't change; the new orchestrator's own new unit tests
run alongside) + `./scripts/run_sanity.sh` (billed sanity) + the full
`tests/billed/`/`tests/expensive/` suites per REQ-063-05/SC-003 — run with the flag **off** first
(must match today's production baseline exactly — this is closer to a formality than a real test,
since the code path is untouched, but confirms the flag's default doesn't accidentally select the
new orchestrator), then with the flag **on** in `dev` (must also pass 100%, proving the new,
independently-built path is behaviorally equivalent to the legacy one it parallels).
