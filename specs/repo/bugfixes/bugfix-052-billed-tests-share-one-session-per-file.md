# Bugfix Spec: Billed E2E tests share one WhatsApp session per test FILE, not per test

## Bug ID
bugfix-052-billed-tests-share-one-session-per-file

## Title
`tests/billed/conftest.py`'s `denidin_config`/`denidin_app` fixtures are `scope="module"`, and the
godfather session store is wiped once per test file (`shutil.rmtree(sessions_dir)` inside
`denidin_config`), not once per test function. Combined with a single shared `GODFATHER_CHAT_ID`
constant (`denidin_mcp_e2e_helpers.py`) and `pytest-randomly` randomizing test order within a
file on every run, this means **any test in a file can inherit real conversation history left
behind by a different, unrelated test that happened to run earlier in the same file** — not just
its own turns. The sharing is deliberate and documented (2026-07-15 comment: "Tests WITHIN one
invocation still share the session... only cross-run carryover is dropped") but the "one
invocation" boundary chosen (module/file) is too wide: it was meant to let ONE test's own
multi-turn flow (ask → approve → verify) share context, not to let unrelated tests bleed into
each other.

## Priority
**P2** — doesn't produce wrong production behavior; makes the billed test suite non-deterministic
(pass/fail can depend on `pytest-randomly`'s seed) and produces misleading failure diagnoses
(a failure can look like a JSON-parsing/model bug when it is actually stale, irrelevant session
context).

## Status
**Open.** Root cause identified and confirmed live; fix not yet designed.

## Date Opened
2026-09-05

## Reported By
yaronlev171, during the Feature 069 JSON-contract-fix verification sweep — batch 2 sanity test
`test_create_document_for_existing_client_happy_path` failed with an empty tool-output capture
even though the bot's reply clearly contained the invoice's details; investigation showed the
model answered from its own in-session memory of an earlier turn rather than re-calling
`get_invoice_details`. The user correctly rejected the initial "this is normal session
continuity" framing and pushed to find the real defect: this suite's tests are not actually
isolated from each other by test function, only by pytest invocation.

## Affected Area
- `apps/denidin-app/tests/billed/conftest.py` — `denidin_config` (`scope="module"`, ~L35),
  `denidin_app` (`scope="module"`, ~L110). The `shutil.rmtree(sessions_dir)` wipe (~L72) runs
  once per fixture instantiation, i.e. once per module, not once per test.
- `apps/denidin-app/tests/billed/denidin_mcp_e2e_helpers.py` — `GODFATHER_CHAT_ID = "972500000021@c.us"`
  (~L436), a single constant shared by every test in every file that imports it. Comment on this
  line already documents one prior rotation for the same symptom (bugfix-028: "972500000018's
  persisted session had accumulated a long, noisy history that was confusing the model across
  turns") — rotating the number papered over the same underlying design, which is still present.
- Every `tests/billed/test_*.py` file with more than one test function that uses
  `GODFATHER_CHAT_ID` (the overwhelming majority of the suite) is exposed to this, at varying risk
  depending on how much each test's assertions depend on the model calling a tool afresh vs.
  tolerating an answer from memory.

## Description

### Observed
1. `denidin_config`/`denidin_app` are module-scoped fixtures; the session-store wipe happens once
   when the fixture is first built for a module, not before/after each test function.
2. `GODFATHER_CHAT_ID` is one hardcoded phone/chat id, imported and reused across effectively the
   entire billed suite.
3. `pytest-randomly` randomizes test execution order within a file on every invocation (every run
   logs a fresh `--randomly-seed=...`).
4. Net effect: test A's conversation turns remain in the godfather's session when test B (same
   file, same chat id) runs next — in whatever order pytest-randomly picked that run. A test whose
   correctness depends on the model calling a specific tool this turn (rather than answering from
   memory) can pass or fail depending on what unrelated test ran immediately before it.
5. Live reproduction: `test_create_document_for_existing_client_happy_path`'s own
   VERIFY turn ("מה הפרטים של החשבונית של X?") got answered entirely from the model's session
   memory of its own prior reply two turns earlier in the SAME test — confirmed via full log
   read (same `chat_id`, all three turns within 30 seconds) to be within-test, not cross-test, in
   that specific run; but the *design* that makes this possible (module-wide session sharing) is
   exactly what would also let a *different* test's history leak in, and has already caused a
   real incident once before (bugfix-028's session rotation).

### Expected
Each test function gets its own isolated conversation/session (and, per the user's own proposed
direction, its own distinct synthetic WhatsApp chat id/phone number, since these are already
entirely invented for testing purposes) — so a test's outcome never depends on pytest's test
execution order, on `pytest-randomly`'s seed, or on what other test happened to run before it in
the same file or under the same xdist worker.

### Not in scope of this bug
- The existing cross-*run* wipe (`shutil.rmtree` when the module fixture first loads) — that part
  already works as intended and is not being removed, only narrowed/supplemented.
- `_clean_reminders_around_every_test` / `_clean_ledger_events_around_every_test` (already
  function-scoped, `autouse=True`, run correctly before AND after every test) — these are the
  pattern to follow, not something broken.
- Any change to production `SessionManager` behavior — this is purely a test-harness isolation gap.

## Proposed Direction (per user, 2026-09-05, not yet designed/approved as a full fix)
Give each test its own individual chat-id fixture rather than one shared `GODFATHER_CHAT_ID` per
file — e.g. a function-scoped fixture that derives (or is given) a distinct synthetic phone number
per test function, so no two tests anywhere in the suite share a session, and ordering/parallelism
can never cause cross-test bleed. Exact mechanism (per-test-name-derived id vs. a counter vs.
explicit ids) still to be designed; needs a look at how many call sites assume the literal
`GODFATHER_CHAT_ID` constant (RBAC role wiring in `denidin_config` also pins
`config.godfather_phone = GODFATHER_CHAT_ID`, so any per-test id must still resolve to the
godfather role for that test's config).

## Test-gap analysis (to be done after root-cause approval)
Candidate: a test-harness-level check (not a `billed`/`expensive` test) that runs two dummy
tests sharing a file with deliberately conflicting canned conversation content and asserts
neither can observe the other's turns, regardless of run order.

## Related
- bugfix-028 (`GODFATHER_CHAT_ID` rotation, 2026-08-12) — same symptom, different unrelated
  chat id, same root cause never actually fixed.
- Feature 069 test-batch verification sweep (2026-09-05) — where this was found.
