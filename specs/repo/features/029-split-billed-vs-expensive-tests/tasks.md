# Tasks: Split `expensive` Marker into `billed` and `expensive`

**Feature ID**: 029-split-billed-vs-expensive-tests

No Task A/B (tests-then-implementation) split — there is no new application
behavior to test-drive here; verification is collection-only (see plan.md).

- [x] T1: `pytest.ini` — register `billed` marker, update `addopts`
- [x] T2: `conftest.py` — register `billed` marker in `pytest_configure`
- [x] T3: Create `tests/billed/__init__.py`
- [x] T4: Move + re-mark: `test_simple_text_e2e.py`, `test_ai_handler_real_api.py`,
      `test_session_transfer.py`
- [x] T5: Move + re-mark: `test_denidin_morning_mcp_e2e.py` +
      `denidin_mcp_e2e_helpers.py`
- [x] T6: Move + re-mark + fix import: `test_denidin_morning_document_creation_e2e.py`
- [x] T7: Split `test_ledger_event_capture_e2e.py` into billed/expensive halves
- [x] T8: Relocate `e2e_helpers.py` to `tests/e2e_helpers.py`, fix 4 consumer imports
- [x] T9: Fix docstring/comment path references in moved files and in
      `tests/unit/test_ai_handler_ledger_events.py` /
      `tests/integration/test_bot_exception_handling.py`
- [x] T10: Update CLAUDE.md (this clone only), CONSTITUTION.md,
      quick-ref-constitution.md, ARCHITECTURE.md
- [x] T11: Verify via `pytest --collect-only` (full, `-m billed`, `-m expensive`,
      default) — no execution

**apps/morning-mcp-app/ (added 2026-07-30 — scope was never denidin-only):**
- [x] T12: `pytest.ini` + `conftest.py` — register `billed` marker, update `addopts`
- [x] T13: Move + re-mark `test_openai_invokes_mcp_e2e.py` (2 tests) into new `tests/billed/`
- [x] T14: Relocate `e2e_helpers.py` to `tests/e2e_helpers.py`, fix its 2 consumers
      (the moved file + `tests/integration/test_ngrok_tunnel.py`)
- [x] T15: Update `README.md`'s config/testing sections
- [x] T16: Verify via `pytest --collect-only` (full, `-m billed`, `-m expensive`, default)

**Reconciliation with `origin/master` (added 2026-07-30 — master advanced
mid-implementation with features 024/026/031):**
- [x] T17: Fast-forward feature branch onto new `master`, re-resolve the one
      real conflict (`test_denidin_morning_mcp_e2e.py`, +14 new client-mgmt
      tests, all text-only → `billed`), move the new `hebrew_*_names.txt`
      data files into `tests/billed/data/`
- [x] T18: Re-run full verification in both apps post-merge — collection
      counts (denidin-app: 46 billed + 9 expensive = 55; morning-mcp-app: 2
      billed + 0 expensive) and full default-suite execution (563 passed /
      269 passed)

**Follow-up methodology changes requested alongside this feature (added
2026-07-30 — not test-classification, but adjacent housekeeping this
feature surfaced the need for):**
- [x] T19: `.github/METHODOLOGY.md` §VI (TDD) — require test-tier
      classification (unit/integration/billed/expensive) as part of the
      EXPLAIN Test Plan step, standing rule for all future features/bugfixes
- [x] T20: Strengthen CONSTITUTION.md/CLAUDE.md wording so it's unambiguous
      that `billed` tests are never subject to the approval-gate/stop-and-ask
      behavior that `expensive` tests require
