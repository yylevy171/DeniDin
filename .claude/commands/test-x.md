---
description: Run one test tier (unit/integration/billed/expensive) with -x across BOTH apps, sounding off pass/fail per test
argument-hint: <unit|integration|billed|expensive>
---

The user invoked `/test-x <type>` where `<type>` is one of `unit`, `integration`, `billed`, `expensive`. Argument: `$ARGUMENTS`.

If `$ARGUMENTS` is missing or not one of those four values, stop and ask which tier to run — do not guess.

## What this does

Runs that single tier's tests, **always with `-x`** (stop at first failure), across **both** apps — `apps/denidin-app` and `apps/morning-mcp-app` — one app at a time, denidin-app first. Announce each test's outcome as it completes (pass/fail, one line each) rather than only reporting a final summary — the user wants to "sound off" per test, live.

## Hard rules (from this repo's CLAUDE.md / CONSTITUTION.md — do not relax these for the sake of this command)

1. **Never trust a bare `python3`/`pytest`.** This repo is checked out in multiple sibling clones sharing one machine; a stale `PATH` can silently resolve to a *different* clone's venv. Before running anything, resolve each app's own interpreter explicitly:
   - `apps/denidin-app/venv/bin/python3`
   - `apps/morning-mcp-app/venv/bin/python3`
   Verify with `<path> -c "import sys; print(sys.prefix)"` that it actually points inside *this* clone's own `apps/<app>/venv` before trusting it. If either venv is missing, stop and say so — do not fall back to a bare `python3`.
2. **Use each interpreter's absolute path directly** in the pytest invocation (`./venv/bin/python3 -m pytest ...`) run from that app's own directory — never `cd` into a sibling clone, never activate another clone's venv.
3. **`unit` / `integration`**: no approval needed, run freely.
4. **`billed`**: no approval needed either, no one-at-a-time restriction — run the whole tier normally (`pytest tests/billed/ -m billed -v -x`). Do not add extra gating that only applies to `expensive`.
5. **`expensive`**: full strict discipline applies, this command does NOT bypass it —
   - User approval is required **before running any expensive test, every single time**, even under this command.
   - **Never run expensive tests all together** — never a bare `-m expensive` sweep. If invoked with `expensive`, stop and ask the user which single test to run (`pytest tests/expensive/test_X.py::test_name -v -m expensive`), rather than looping over the whole directory.
   - Read `logs/test_logs/` for that test file before re-running anything.
   - Never re-run a previously-failed expensive test speculatively — only once confident a fix addresses the failure.
   - Never re-run an expensive test that already reached OpenAI (pass or fail) without a fresh, explicit approval for that specific run.
6. **Stop on failure means stop, every time, no exceptions.** `-x` will halt the pytest run itself at the first failure. When that happens:
   - Report the failing test (name, file, assertion/traceback) clearly.
   - Do **not** investigate, fix, re-run, or move on to the next test/app — wait for fresh, explicit user direction.
   - This applies per-app too: if denidin-app's run fails, do not proceed to morning-mcp-app's run without direction.
7. **Never redirect output to `/tmp` or any ad-hoc log file.** Each app's `conftest.py` already writes per-test-file logs to `logs/test_logs/{test_file}.log` — read from there for extra detail instead of teeing output elsewhere.
8. **Morning-mcp-app's `billed`/`expensive` tiers may be empty or nearly empty** (per CLAUDE.md, it currently has ~2 `billed` tests and 0 `expensive`) — if a tier has zero collected tests for that app, say so plainly and move on to (or skip) the other app rather than treating it as a failure.

## Execution

For `unit`/`integration`/`billed` (no per-run approval needed):

```bash
cd apps/denidin-app && ./venv/bin/python3 -m pytest tests/<type>/ -m <type> -v -x
cd apps/morning-mcp-app && ./venv/bin/python3 -m pytest tests/<type>/ -m <type> -v -x
```

(`unit`/`integration` are typically unmarked directories, not marker-filtered — use `pytest tests/<type>/ -v -x` for those two, and `-m <type>` marker filtering only for `billed`/`expensive` where tests live in a dedicated directory but the marker is still the authoritative selector per CLAUDE.md.)

Stream results and call out each test by name as PASS/FAIL immediately, then a one-line summary per app. If the first app's run stops at a failure, report it fully and **wait** — do not start the second app's run automatically.

For `expensive`: do not auto-run anything above. Ask the user which specific test(s) to approve, one at a time, following rule 5 above.
