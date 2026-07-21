# Handoff — 2026-07-21 (evening)

## State: merged, deployed where it matters, containers up

PR #117 merged to `master` (commit `62b9093`), branch deleted (local + remote). No deploy step was needed — this PR only touched denidin-app test files, docs/specs, and build-time `.dockerignore` files, none of which change already-running container behavior.

## What merged (PR #117)

### 1. bugfix-013 — now fully closed
- Name-garbling half: closed as **not reproducible/fixable at the app level** (human decision, 2026-07-21) — no app-level cause found across the WhatsApp-receipt-to-tool-call path; consistent with a known GPT-4o-family tokenization weak point for uncommon Hebrew tokens. No follow-up entity-verification feature spec was opened (considered, explicitly declined for now).
- Date-narrowing half: already fixed in PR #116 (previous session) — unchanged here.
- Spec moved to **`specs/not_reproducible/bugfixes/`** — a new closure category (distinct from `done/` and `obsolete/`) for bugs investigated and closed by human decision where nothing was actually fixed. Documented in `CLAUDE.md`'s Spec-Driven Workflow section.

### 2. Real secret-leak fix (found as a drive-by while testing, not part of bugfix-013)
- Added `.dockerignore` to both `apps/denidin-app/` and `apps/morning-mcp-app/`. Previously, **`config.dev.json`/`config.prod.json`/`config.test.json` (all containing real secrets) were being baked into every Docker image layer** via `Dockerfile`'s `COPY . .`, with no exclusion — the runtime `VOLUME`/bind-mount override hides this at runtime but the secrets still persisted in the image's layer history. Both apps now exclude these files (and other local/VCS cruft) at build time. **Rebuilt both dev images this session to pick up the fix** (`docker compose -f docker-compose.dev.yml build`).

### 3. Test infrastructure gaps found and fixed while running the full suite
While running unit + integration + all 18 expensive tests against a freshly redeployed dev environment (first full run since PR #116's env-isolation/credential-scrub work), found and fixed:
- `denidin.py` hardcodes `CONFIG_PATH = 'config/config.json'` at module level — this file was deleted in PR #116's credential-scrub cleanup, breaking any test that does `import denidin` (5 files) when run locally outside a container. **Not fixed in code** (a full fix would mean refactoring `bot`/`ai_client`/router-registration out of module scope into a factory — discussed, decided against for now, "simplest solution, albeit ugly" instead). Worked around by restoring a local, gitignored `apps/denidin-app/config/config.json` (real dev Green API creds + real OpenAI key) — **this file is not tracked, so a fresh clone/session needs it recreated** (copy `config.test.json`'s shape, fill in real creds from `DeniDin Dev Creds.txt`).
- `apps/denidin-app/config/config.test.json` and `config.dev.json`/`config.prod.json` all had `ai_model: "gpt-5.6-luna"` (a real, valid OpenAI model — confirmed via API behavior, not a typo) but `test_real_api_connectivity.py` called it via the legacy `chat.completions.create(max_tokens=...)` shape instead of the Responses API production actually uses (`client.responses.create(max_output_tokens=..., ...)`, with a `temperature` param that `gpt-5.6-luna` specifically rejects — see `MODELS_WITHOUT_TEMPERATURE_SUPPORT` in `ai_handler.py:38`). Fixed the test's 3 call sites to match.
- `config.test.json`'s `ai_vision_model` was `gpt-4o-mini`, inconsistent with `config.dev.json`'s `gpt-4o` — per explicit instruction, set to `gpt-4o` in both.
- `config.test.json`'s `mcp.morning_auth_token` was still the placeholder string — set to match the real token now used by `morning-mcp-app-dev`'s `config.dev.json`.
- `test_denidin_morning_mcp_e2e.py`'s paid-status assertion only matched the masculine `שולם`, not the grammatically-correct feminine `שולמה` (different final-letter form — sofit-mem ם vs regular מ) the model correctly produces when agreeing with a feminine noun (חשבונית). Fixed to accept both.

### 4. Two new binding rules added to CLAUDE.md (agent behavior, added after live violations this session)
- **Never start any environment (`run_denidin.sh`/`run_morning_mcp.sh`/`docker compose up`) without explicit approval for that specific action, every time** — approval for something else (e.g. editing test config) does not imply approval to also start what it needs.
- **Config is code** — once a test run has started, config files are frozen for that run's duration; any blocker found mid-run must be surfaced and fixed before/after, never patched in silently while a run is in progress.

## Current runtime state

**`morning-mcp-app-dev` is running** (left up per explicit instruction, not torn down at end of session) — real dev Morning sandbox credentials, live ngrok tunnel. `denidin-app-dev` is **not** running. `shared/active_env.json` shows `"active_env": "dev"`.

## Test results this session (full run, all passing)

- **462 unit tests** — pass
- **35 integration tests** — pass (1 deselected: the expensive one, run separately below)
- **18 expensive tests** — all run individually with fresh human approval each time, all pass:
  - `test_ai_handler_real_api.py` ×3
  - `test_denidin_morning_mcp_e2e.py` ×7 (includes both bugfix-013 regression tests: `test_zehavit_client_name_transcribed_exactly`, `test_no_date_mentioned_omits_date_range`)
  - `test_simple_text_e2e.py` ×1
  - `test_media_e2e.py` ×6
  - `test_session_transfer.py::test_session_transfer_and_recall_after_expiration` ×1
- Confirmed directly from the running container (not just the config file) that Morning MCP traffic goes to `sandbox.d.greeninvoice.co.il`, never production, before running any of the state-changing sandbox tests.

## Suggested next steps

1. **`denidin.py`'s module-level config-loading design remains an open wart** — every `import denidin` triggers real disk I/O and a real `GreenAPIBot` network call as a side effect of import, which is why 5 test files need a real, gitignored `config/config.json` to exist locally to even collect. A proper fix (factory function wrapping `bot`/`ai_client`/router registration, called only from `__main__`) was scoped and discussed this session but explicitly deferred — revisit if this friction recurs.
2. **`config/config.json` (gitignored, local-only) needs to exist with real dev Green API + OpenAI credentials** for the 5 `import denidin`-based test files to collect at all locally. Not present in a fresh clone — recreate from `DeniDin Dev Creds.txt` if a new session hits `INTERNALERROR` on `tests/integration/test_archived_session_recovery.py` or similar.
3. Consider whether `morning-mcp-app-dev` should stay up or be torn down (`./killall_containers.sh`) before starting unrelated work — it was left running per explicit instruction at end of this session, not because ongoing work needs it.
4. No outstanding invoice/prod-safety concerns from this session — all sandbox, confirmed.
