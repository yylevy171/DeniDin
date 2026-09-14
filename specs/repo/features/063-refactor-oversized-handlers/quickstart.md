# Quickstart: The Dynamic Capability Backbone (063)

## Enabling the new path (dev only, human-approved per CLAUDE.md's environment-start rule)

1. In `config/config.dev.json`, set `feature_flags.enable_capability_backbone: true` and add a
   `backbone_config` block (`data-model.md`'s Config additions) — `constitution_config` (used by
   the untouched `AIHandler`) is left exactly as it is.
2. Ensure `config/prompts/backbone.md` + `config/prompts/capabilities/*.md` (9 files: 2 meta —
   `intent_identification.md`, `planning.md` — + 7 domain) exist — `speckit.tasks` produces these
   as **new** files, authored fresh from the Capability Plugin Taxonomy in `spec.md` (not a
   split/move of `runtime_constitution.md`, `ledger_recognition_prompt.md`, or
   `prompts/image_analysis.txt`/`docx_analysis.txt`, all of which stay untouched and continue to
   serve the legacy path only).
3. Rebuild and restart `denidin-app-dev` (per CLAUDE.md's "Merging a code fix to master does not
   redeploy it" — this is a code+config change, needs an explicit rebuild, explicit approval each
   time per the environment-start rule).

## Verifying it worked

- Send a small-talk message → check `logs/denidin.log` for the turn's Intent Identification +
  Planning calls, followed by zero execution steps (an empty `Plan`) → final reply composed from
  Intent Identification's output alone, per `contracts/orchestration-loop.md`.
- Send a Ledger Query question → check the log shows Intent Identification → Planning (producing a
  one-step `Plan` naming `ledger_query`) → one execution-step call whose `instructions` carries
  Backbone + the `ledger_query` capability prompt only (not the whole taxonomy at once — R3's
  single-active-capability property).
- Send an image containing a fee-agreement note → check the log shows a `Plan` with two ordered
  steps (`media_analysis` then `ledger_capture`), the `media_analysis` step calling the same
  unmodified `ImageExtractor`, and its extracted text appearing in the `ledger_capture` step's
  accumulated context (R2a/REQ-063-04a — media enters through this same orchestrator, not a
  separate deterministic pre-route).
- Run `scripts/model_sanity_check.sh --config config/config.dev.json` (new mode from research.md
  R6) for the cache-hit/instrumentation proof: confirm `cached_tokens > 0` on the second of two
  back-to-back calls sharing the same `active_tag` (e.g. two `ledger_query` steps from different
  turns) — this is what REQ-063-06's 9-fixed-prefixes property predicts. Billed, human-approved
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
orchestrator), then with the flag **on** in `dev` (must also pass 100%, proving the new,
independently-built path — including its media-message entry point — is behaviorally equivalent to
the legacy one it parallels).
