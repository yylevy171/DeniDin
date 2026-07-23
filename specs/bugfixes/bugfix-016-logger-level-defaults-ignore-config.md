# Bugfix Spec: Module Loggers Default to INFO Regardless of `config.log_level`, and Test Harness Can't Reliably Override This for Lazily-Imported Modules

## Bug ID
bugfix-016-logger-level-defaults-ignore-config

## Title
`src/utils/logger.py`'s `get_logger()`/`setup_logger()` hardcode a per-logger `log_level` default of `'INFO'` — every module that calls `get_logger(__name__)` without an explicit level (i.e. every module except `denidin.py` itself) is permanently pinned to `INFO`, both in production (ignoring `config.json`'s `log_level`) and in tests (ignoring `conftest.py`'s attempt to run the whole suite at `DEBUG`)

## Status
Open - root cause confirmed, fix not yet applied

## Date Opened
2026-07-23

## Reported By
yaronlev171 (found while adding diagnostic `logger.debug(...)` calls to `ai_handler.py` for Feature 022 and discovering they never appeared in any log output)

## Affected Area
- `apps/denidin-app/src/utils/logger.py` (`setup_logger`/`get_logger`'s `log_level: str = 'INFO'` default parameter)
- Every module using `logger = get_logger(__name__)` with no explicit level — `src/handlers/ai_handler.py`, `src/managers/session_manager.py`, `src/managers/memory_manager.py`, `src/managers/pending_approval_manager.py`, and most others (only `denidin.py` itself passes `log_level=config.log_level` explicitly)
- `apps/denidin-app/conftest.py`'s `pytest_runtest_setup` hook (attempted partial fix — resets `propagate`/level on already-created loggers, but can't help loggers created later, mid-test, via a lazy import)

## Description
While debugging Feature 022 (explicit-approval gate for Morning document creation), new `logger.debug(...)` diagnostic calls were added to `ai_handler.py` and `pending_approval_manager.py`. They never appeared in any test log output, including `logs/test_logs/test_denidin_morning_mcp_e2e.log` from real, billed E2E test runs — making it impossible to diagnose a separate, real bug in the approval-resolution flow without first fixing this.

Investigation found **two compounding causes**:

1. **`get_logger`/`setup_logger` hardcode `log_level: str = 'INFO'`** as the default parameter value. `logger.setLevel(getattr(logging, log_level))` runs unconditionally at logger-creation time. Since almost every module calls `get_logger(__name__)` with no `log_level` argument, that logger's own level is explicitly fixed to `INFO` the moment it's first created — regardless of `config.json`'s (or `config.test.json`'s) actual `log_level` value. Only `denidin.py`'s own top-level logger (`logger = get_logger(__name__, log_level=config.log_level)`, `denidin.py:49`) honors config at all. This means **`config.log_level = "DEBUG"` currently has no effect on any module's own `.debug()` calls except `denidin.py`'s**, in production or tests.

2. **`conftest.py`'s `pytest_runtest_setup` hook only fixes loggers that already exist** at the moment it runs (it iterates `logging.root.manager.loggerDict`, setting `propagate = True`, and — after a partial fix attempted during this investigation — `setLevel(logging.NOTSET)`). This works for test files that import the relevant module at collection time (e.g. `tests/unit/test_ai_handler_rbac.py`, which does `from src.handlers.ai_handler import AIHandler` at the top of the file — confirmed via a live run that its `[022]`-tagged debug lines DID appear in `logs/test_logs/test_ai_handler_rbac.log` after the `NOTSET` fix). It does NOT work for `tests/expensive/test_denidin_morning_mcp_e2e.py`, which imports `denidin` (and transitively `ai_handler.py`) **lazily, inside `_send_turn`, at test-CALL time** — i.e. after `pytest_runtest_setup` has already finished resetting whatever loggers existed at that point. `ai_handler.py`'s module logger doesn't exist yet at setup time in this case; it gets created fresh, mid-test, with the hardcoded `INFO` default from cause (1), and is never touched again.

Confirmed via three real (billed) E2E runs, all of which contain **zero** debug-level log lines whatsoever in `logs/test_logs/test_denidin_morning_mcp_e2e.log` — not just the new `[022]` diagnostic lines, but pre-existing lines like `"Calling OpenAI Responses API for request..."` and `"AIHandler initialized with models..."` that have nothing to do with Feature 022.

## Root Cause Analysis
Confirmed, not merely hypothesized:
- Cause (1) verified by reading `src/utils/logger.py`'s `setup_logger` signature and the unconditional `logger.setLevel(...)` call at the top of the function body.
- Cause (2) verified empirically: the SAME code (after the `conftest.py` `NOTSET` fix) produces `DEBUG`-level `[022]` log lines in `test_ai_handler_rbac.log` (module-level import) but zero in `test_denidin_morning_mcp_e2e.log` (lazy, in-test import) — the only material difference is import timing relative to `pytest_runtest_setup`.

## Steps to Reproduce
1. Add any `logger.debug(...)` call to `src/handlers/ai_handler.py`.
2. Run `python3 -m pytest tests/unit/test_ai_handler_rbac.py::TestAIHandlerRBACTokenLimits::test_enforces_client_token_limit -v` (free, no approval needed) — the debug line appears in `logs/test_logs/test_ai_handler_rbac.log`.
3. Run (billed, requires fresh explicit approval per CLAUDE.md) any test in `tests/expensive/test_denidin_morning_mcp_e2e.py` — the same debug line, and every other pre-existing debug line, is absent from `logs/test_logs/test_denidin_morning_mcp_e2e.log`.

## Expected Behavior
- `config.log_level` (in whichever config file is actually loaded — `config.json`, `config.dev.json`, `config.prod.json`, or `config.test.json`) should control the effective log verbosity for **every** module's logger, not just `denidin.py`'s own.
- In tests specifically, `conftest.py`'s intent (running the whole suite at `DEBUG`, per its own hardcoded `root_logger.setLevel(logging.DEBUG)`) should hold regardless of when during a test a given module happens to be imported.

## Impact
- Any diagnostic `logger.debug(...)` call added anywhere in the codebase (except `denidin.py` itself) is silently a no-op in both production and most test contexts — a real gap for anyone trying to debug an issue via added log lines, as encountered here.
- In production, this means `config.json`'s `log_level` field is effectively decorative for every module except `denidin.py`'s own top-level one — operators cannot turn on `DEBUG` logging for `ai_handler.py`/`session_manager.py`/etc. by editing config, contrary to what the config field's existence implies.

## Acceptance Criteria
- [ ] `get_logger()`/`setup_logger()`'s default `log_level` parameter changed from `'INFO'` to a value that lets loggers properly inherit their effective level from the root logger (e.g. `'NOTSET'`), so any module's logger — whenever created — responds to whatever the root/config-driven level actually is, rather than being permanently pinned at creation time.
- [ ] Confirm this doesn't silently reduce production log verbosity for modules that currently rely on the `INFO` default with no root-level configuration in place (i.e. verify `denidin.py`'s main entry point, or an equivalent root-level setup, establishes a sensible root logger level in production so `NOTSET` loggers don't fall back to Python's built-in `WARNING` default).
- [ ] `conftest.py`'s `pytest_runtest_setup` `NOTSET` reset (already applied during this investigation, see References) remains in place as a defense-in-depth measure for loggers that already exist by test-setup time.
- [ ] Verify (via a repeat of the reproduction steps above) that a `logger.debug(...)` call in `ai_handler.py` now appears in `logs/test_logs/test_denidin_morning_mcp_e2e.log` from a real E2E test run, including one that imports `denidin` lazily mid-test.
- [ ] No regression in the full non-expensive suite (`pytest tests/unit tests/integration`).

## References
- `.github/METHODOLOGY.md` §VII (Bug-Driven Development)
- `apps/denidin-app/src/utils/logger.py` (`setup_logger`, `get_logger`)
- `apps/denidin-app/conftest.py` (`pytest_runtest_setup`)
- `apps/denidin-app/denidin.py:49` (the one module that already does this correctly: `get_logger(__name__, log_level=config.log_level)`)
- `apps/denidin-app/tests/unit/test_ai_handler_rbac.py` (control case — module-level import, debug logging confirmed working post-`NOTSET`-fix)
- `apps/denidin-app/tests/expensive/test_denidin_morning_mcp_e2e.py` (`_send_turn`'s lazy `from denidin import handle_text_message` — the specific pattern that doesn't get fixed by the `conftest.py` reset alone)
- Discovered during Feature 022 (`specs/backlog/022-explicit-approval-for-document-creation/`) implementation/debugging, branch `feature/022-explicit-approval-for-document-creation`

## Cost/Approval Note
Confirming the fix against a real E2E test requires a billed OpenAI/Morning sandbox run. Per CLAUDE.md's expensive-test rules: explicit human approval is required before every single run, one test at a time, never a batch. Three billed runs already spent on Feature 022 debugging did not have working debug output due to this bug — do not spend a fourth verifying this specific fix without weighing whether the same information can be obtained more cheaply (e.g. the free unit-test control case already demonstrates the underlying mechanism works once the default is fixed).
