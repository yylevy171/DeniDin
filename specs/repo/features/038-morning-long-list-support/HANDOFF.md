# Handoff: Feature 038 — Morning Long List Support

**Written**: 2026-08-05 (end of session, user requested a fresh start)
**Branch**: `feature/038-morning-long-list-support`
**Last commit**: `0a5cf80` (merge of `origin/master` into this branch)
**Uncommitted at handoff time**: `apps/denidin-app/tests/integration/test_group_conversation_routing.py` — see "Uncommitted fix" below. Commit or discard this before doing anything else.

---

## What's done

1. **Full SpecKit pipeline** for this feature, in `specs/in-progress/038-morning-long-list-support/`: `spec.md`, `user-stories.md`, `research.md` (7 decisions), `plan.md`, `data-model.md`, `contracts/`, `tasks.md`, `quickstart.md`. Went through 3 rounds of test-plan revision with the user — read `research.md` Decisions 5-7 before touching anything token-budget-related; the history there explains a real correction (a wrong assumption I made was caught and fixed by the user, see Decision 7).
2. **Root cause + fix, implemented and GREEN** (`apps/morning-mcp-app`): `list_invoices` silently truncated to 10 items from only Morning's first page (real 2026-08-04 prod incident: 46 of 62 invoices returned). Fixed by porting `list_clients`' real-pagination pattern (fetch cap raised 10→100, refuse+report-total above that) plus a new, independent token-budget-based display truncation (config-driven, `MorningMCPConfig.list_invoices_token_budget`, default **2500** — this is a real observed platform limit, not a constant to invent/lower; see Decision 7 for why an earlier "800" was wrong and reverted). Touches `tools.py`, `formatters.py`, `config.py`, `server.py`, `config.schema.json`, `config.example.json`, `requirements.txt` (added `tiktoken`).
3. **Tests**: `apps/morning-mcp-app` full suite — **289 passed, 0 failed, 1 pre-existing unrelated skip** (`test_ngrok_tunnel.py`, needs a live tunnel, verified unrelated). Includes 2 new real-sandbox integration tests (US1/US2, against live fixture data) and unit tests for the fetch-loop/cap-boundary/token-budget logic.
4. **`apps/denidin-app` billed E2E test suite split** (human-approved, per user direction — "this is denidin functionality, not morning" / "full split by section"): the old 2094-line `test_denidin_morning_mcp_e2e.py` is now 4 topic files + a shared `conftest.py` + shared `denidin_mcp_e2e_helpers.py`. Verified programmatically byte-identical to the original except one disclosed comment. 3 new billed tests added to `test_denidin_morning_list_invoices_e2e.py`, asserting on the model's **actual WhatsApp reply text**, not just `mcp_calls` (explicit user direction) — but **not yet run for real**, see below.
5. **Merged `origin/master`** into this branch — clean, no conflicts (feature 039 group-conversation-support landed, touches `ai_handler.py`/`denidin.py`/session manager, unrelated to this feature's files).

## Uncommitted fix (do this first)

After merging master, running the full `apps/denidin-app` suite turned up a real, reproducible failure: `test_media_webhook_routing.py::test_image_message_user_gets_response` failed only when run together with master's new `test_group_conversation_routing.py` (feature 039), not in isolation.

**Root cause** (confirmed, not guessed): `test_group_conversation_routing.py`'s `_stub_external_boundaries` monkey-patches methods directly on the **live, process-global** `denidin_app` singleton (`media_handler.image_extractor.analyze_media = lambda ...`) — itself a CONSTITUTION §XVII violation ("NO dynamic attribute injection", "NO function reassignment"). Because the `denidin_app` fixture in that file reuses the global singleton across test modules when already initialized, the unrestored patch leaked into whichever test ran next against that same singleton. Confirmed live: `test_media_webhook_routing.py` received the *other* file's own canned string (`"Full document analysis: invoice for services rendered."`) instead of its own expected result.

**What I did**: converted `_stub_external_boundaries` into a context manager that restores the original bound methods in a `finally` block, and wrapped both test bodies' `handle_image_message(notification)` calls in `with self._stub_external_boundaries(...):`. Verified this fixes the pollution: `pytest tests/integration/test_group_conversation_routing.py tests/integration/test_media_webhook_routing.py` → 8/8 pass.

**What I did NOT do**: fix the underlying monkey-patching violation itself (that needs dependency injection — constructing `MediaHandler`/`ImageExtractor` with injected fakes — not patch-and-restore). Flagged in a comment in the file. This is master's code, not something introduced by Feature 038 — whether/when to properly fix it is a separate decision (probably its own bugfix spec, Bug-Driven Development, not inline here).

**Status**: this file is modified but **not committed**. The user interrupted a re-run of the full suite (correctly — no more incidental test-running without being asked) before I could do a final full-suite confirmation post-fix. **Next step: get explicit confirmation on whether to commit this fix, then (if wanted) run the full `apps/denidin-app` suite once more to confirm the fix holds suite-wide, not just for these two files.**

## Explicitly NOT done — needs a human decision, not autonomous action

1. **The 3 new billed E2E tests can't pass yet.** They exercise the real, already-running `morning-mcp-app-dev` container over its live tunnel, which still runs pre-fix code. Rebuilding + restarting it is a separate environment-start action requiring explicit approval every time (CLAUDE.md) — I asked, no answer given yet before this handoff.
2. **`test_godfather_lists_invoices_via_whatsapp`** (in the new `test_denidin_morning_list_invoices_e2e.py`) has a flagged comment: its assertion (2 specific invoice numbers, first/last of a known 6) may break once the real fix is deployed, since those 6 invoices' formatted size may not fit the 2500-token budget entirely. Not touched — explicitly flagged for whoever runs it post-deploy, not fixed preemptively.
3. **No release has been cut, nothing has been pushed, no PR opened.** This branch is local-only relative to origin as of this handoff (except for the merge from origin/master, which was a pull not a push).

## Key things to know before continuing

- **Read `research.md` Decisions 5-7 before changing anything about the token budget.** There's a real corrected mistake in there (I permanently lowered a production value based on a misreading of feedback; the user caught it and corrected it). Don't repeat it.
- **All 3 new billed tests assert on the actual bot reply text** (`response`, not `ai_response.mcp_calls`), per explicit user direction — this is the point of those tests (verifying the *model* relays counts faithfully, not just that the tool was called).
- **Never run `expensive`-tier tests, and never start/rebuild `morning-mcp-app-dev`, without asking first, every time** — both already came up this session as things I must not do unprompted.
- User is being appropriately skeptical of claims — verify before asserting (e.g. "pre-existing skip," "no billed tests ran") rather than asserting from memory or assumption. Keep doing that.

## Suggested next steps for a fresh session

1. Decide on the uncommitted `test_group_conversation_routing.py` fix (commit as-is, revise, or discard).
2. Re-run `apps/denidin-app`'s full suite once (only after explicit go-ahead) to confirm the fix holds beyond the two-file check.
3. Ask the human whether/when to rebuild+restart `morning-mcp-app-dev` so the 3 new billed tests can run for real.
4. Once verified, proceed toward `/haleluya` (commit if not already, push, PR, merge, deploy, move spec to `specs/done/`) — but per CLAUDE.md, never run haleluya unprompted.
