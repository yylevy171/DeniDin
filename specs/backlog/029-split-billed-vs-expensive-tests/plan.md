# Implementation Plan: Split `expensive` Marker into `billed` and `expensive`

**Feature ID**: 029-split-billed-vs-expensive-tests
**Branch**: `feature/029-split-billed-vs-expensive-tests`

## Scope

**Both apps** — `apps/denidin-app/` AND `apps/morning-mcp-app/` (corrected
2026-07-30; the original draft wrongly assumed denidin-app-only). No
application code changes — this is a test-infrastructure reorganization:
pytest marker split + physical file/folder split + doc updates, applied
identically in both apps' own independent `pytest.ini`/`tests/expensive/`.
No new runtime behavior, no feature flag needed (test collection/
classification isn't a runtime code path).

### apps/morning-mcp-app/ (added 2026-07-30)

Only one file exists there: `tests/expensive/test_openai_invokes_mcp_e2e.py`
(2 tests) + its own `tests/expensive/e2e_helpers.py`. Both tests verified
text-only (real OpenAI Responses API driving MCP tool calls, no vision) →
both move to `tests/billed/`, `tests/e2e_helpers.py` relocated up one level
(also used by `tests/integration/test_ngrok_tunnel.py`, which needed its
import fixed too). Its `expensive` marker/folder stay registered in
`pytest.ini`/`conftest.py` with zero current tests, for parity and in case
a future vision-based tool is added.

### Master moved during implementation (added 2026-07-30)

Between drafting and implementing, `origin/master` advanced (features 024,
026, 031) and touched exactly the two files this feature moved
(`test_denidin_morning_mcp_e2e.py` grew by ~719 lines/14 new client-
management tests; `test_denidin_morning_document_creation_e2e.py` by 18
lines), plus added two new data files
(`tests/expensive/data/hebrew_{family,first}_names.txt`) that
`test_denidin_morning_mcp_e2e.py` loads relative to its own path. Resolved
by: fast-forwarding the feature branch onto the new `master` (trivial, zero
local commits existed yet), then re-resolving the one real conflict by
taking upstream's full new content and mechanically reapplying the same
marker-rename/path-fix transform, and moving the `data/` folder alongside
its consuming file into `tests/billed/data/`. All 14 new tests are
text-only (client list/add/get-details/update via WhatsApp text + MCP) →
`billed`, consistent with the rest of this file.

## Approach

1. **pytest.ini**: add `billed` marker registration; change `addopts` from
   `-m "not expensive"` to `-m "not billed and not expensive"`.
2. **conftest.py**: register the `billed` marker alongside the existing
   `expensive` one in `pytest_configure`.
3. **New folder `tests/billed/`** (sibling of `tests/expensive/`), with its
   own `__init__.py`.
4. **Move (git mv) whole files, unchanged in content except marker rename**,
   into `tests/billed/`:
   - `test_simple_text_e2e.py`
   - `test_ai_handler_real_api.py`
   - `test_session_transfer.py`
   - `test_denidin_morning_mcp_e2e.py` + `denidin_mcp_e2e_helpers.py`
   - `test_denidin_morning_document_creation_e2e.py` (update its
     `from tests.expensive.test_denidin_morning_mcp_e2e import ...` to
     `from tests.billed.test_denidin_morning_mcp_e2e import ...`)
5. **Split `test_ledger_event_capture_e2e.py`**: extract the 2 text-flow
   tests into a new `tests/billed/test_ledger_event_capture_billed.py`
   (duplicating the shared `config`/`denidin_app` fixtures and the
   `_fresh_chat_id`/`_pending_events`/`_read_persisted_session`/
   `_assert_ledger_event_persisted` helpers — matching this codebase's
   existing convention of each E2E file being fixture-self-contained, not
   introducing a new shared module for two methods). The original file keeps
   only its `http_server` fixture and the 3 image-flow tests.
6. **Relocate `tests/expensive/e2e_helpers.py` → `tests/e2e_helpers.py`**
   (shared parent, since both `tests/billed/` and `tests/expensive/` files
   import it after the split) and update the 4 consumer imports
   (`test_simple_text_e2e.py`, `test_media_e2e.py`,
   `test_ledger_event_capture_e2e.py`, the new
   `test_ledger_event_capture_billed.py`) from relative `.e2e_helpers` to
   absolute `tests.e2e_helpers`.
7. **Rename markers**: `@pytest.mark.expensive` → `@pytest.mark.billed` on
   every test that moved into `tests/billed/`; `test_media_e2e.py` and the
   narrowed `test_ledger_event_capture_e2e.py` keep `@pytest.mark.expensive`
   unchanged.
8. **Update path/marker references in comments and docstrings** in the moved
   files themselves (e.g. "Run with: pytest tests/expensive/... -m expensive"
   → the new path/marker), plus the two cross-file docstring references in
   `tests/unit/test_ai_handler_ledger_events.py` and
   `tests/integration/test_bot_exception_handling.py`.
9. **Docs**: update CLAUDE.md (this clone's copy only), `.github/CONSTITUTION.md`,
   `.github/quick-ref-constitution.md`, `.github/ARCHITECTURE.md` to describe
   both tiers, their folders, and the differing approval rules.

## Verification (no new automated tests — this changes test classification/
location, not application behavior)

- `python3 -m pytest --collect-only -q` — full suite still collects with no
  import errors, same total test count as before the move.
- `python3 -m pytest --collect-only -q -m billed` — collects exactly the
  tests listed as `billed` above.
- `python3 -m pytest --collect-only -q -m expensive` — collects exactly
  `test_media_e2e.py`'s 6 tests + the narrowed `test_ledger_event_capture_e2e.py`'s
  3 tests.
- `python3 -m pytest --collect-only -q` (default addopts) — confirms neither
  tier collects by default.
- Do NOT execute any billed/expensive test in this session — collection-only
  verification is sufficient to prove the reorg didn't break anything, and
  actually running them spends real money / requires the approval this repo's
  rules still require for `expensive`.
