# Bugfix Spec: Active Session Loses Context After App Restart

## Bug ID
bugfix-010-active-session-context-lost-on-restart

## Title
Recently-active session loses conversation context after app restart

## Status
Open — Root cause NOT yet established (requires live reproduction)

## Date Opened
2026-07-07

## Reported By
yaronlev171

## Affected Area
- `src/managers/session_manager.py` (`_load_sessions`, `get_session`, `get_conversation_history*`)
- `src/handlers/ai_handler.py` (`get_response` history retrieval and OpenAI message assembly)
- Startup path: `denidin.py` `initialize_app`, `run_denidin.sh` vs `python3 denidin.py` (CWD)

## Description
After restarting the app, a still-live (not-yet-transferred, recently active <24h) session appears
to lose its earlier messages. Within a single run (no restart) context works perfectly; a restart
causes the AI to answer as if the prior messages never happened, even though the app appears to
"remember" the session on disk.

## Steps to Reproduce (user's exact script)
1. Send "my name is Leo".
2. AI replies something like "Hi Leo".
3. Restart the app.
4. Ask "what is my name?".
- **Expected:** "Your name is Leo."
- **Observed:** "You haven't told me your name" (or similar).

Environment (from reporter): same machine, started via `./run_denidin.sh` or `python3 denidin.py`,
same config as the live instance; affected session was recently active (<24h).

## How It Is Supposed To Work (mechanism)
On restart, `SessionManager.__init__` → `_load_sessions()` (`session_manager.py:303-319`) scans
`data/sessions/*/session.json` and rebuilds `chat_to_session[whatsapp_chat] = session_id`. On the
next message, `get_response` → `get_conversation_history(chat)` → `get_session` (hits the rebuilt
index, re-reads `session.json` from disk) → `get_conversation_history_for_session` iterates persisted
`message_ids`, reads each `messages/*.json`, and returns `[{"role","content"}...]`
(`session_manager.py:205-238`). That history is prepended to the OpenAI `messages` array before the
current prompt (`ai_handler.py:297-306,363-374`). There is no in-memory-only conversation state —
every turn reads from disk — so it should behave identically before and after a restart.

## Current State of Investigation (honest)
Static analysis and empirical re-instantiation both show the active-session reload path **works**,
and the live `logs/denidin.log` confirms it in the reporter's own environment:
- Across restarts (SessionManager initialized at 22:05:27 and 22:22:45), session
  `d74a85a5-...` for chat `972522968679@c.us` is **reused** — there is **no** "Created new session"
  event after any restart (only 3 creation events ever, none post-restart).
- "Retrieved N messages from session history" keeps climbing across the restart (…12, 14 → **16**
  after 22:22, up to 24).

So the observed symptom **contradicts** the live evidence. The root cause therefore cannot be pinned
by static analysis and requires a **controlled live reproduction with instrumentation** before any
fix is proposed.

## Hypotheses To Test During Reproduction
- **(a) storage_dir/CWD/`data_root` resolution:** `./run_denidin.sh` vs `python3 denidin.py` may run
  with a different working directory, so the relative `data/sessions` resolves to a different/empty
  absolute path on restart → empty index → fresh empty session (a `bugfix-004-data-root-ignored`-class
  hazard). If so, expect a post-restart "Created new session".
- **(b) chat-id key mismatch:** stored `session.whatsapp_chat` vs retrieval `effective_chat_id`
  (`chat_id or request.chat_id`, `ai_handler.py:338-366`).
- **(c) load exception:** an exception in `_load_sessions`/`_load_session` for that session (caught &
  logged, `session_manager.py:318-319`) silently drops it from the index.
- **(d) history-retrieval exception:** a swallowed exception in `get_conversation_history`
  (`ai_handler.py:369-370`) yields empty history even though the session is intact.

## Known Secondary Gap (real, but out of scope for this <24h symptom)
`_load_sessions()` skips `expired/` (`session_manager.py:309`), while `archive_session` keeps
expired-but-untransferred sessions in the in-memory index only (`session_manager.py:436-474`). After a
restart those are not re-indexed → next message spawns a fresh empty session. This only fires for
sessions idle >24h, so it does **not** match this report; tracked here for follow-up, not assumed to
be the cause.

## Investigation Plan (before any fix)
1. Add targeted, behavior-neutral instrumentation (resolved absolute `storage_dir` + sessions loaded;
   `get_session` index-hit vs create + `session_id`/`len(message_ids)`; `chat_id`+`session_id`+
   `len(conversation_history)` on the "Retrieved N" line).
2. Reproduce with the user's "Leo" script via both `./run_denidin.sh` and `python3 denidin.py`; read
   `logs/denidin.log` (do not re-run repeatedly).
3. Use the instrumentation to pin the broken link to exactly one of (a)-(d).
4. Document the confirmed root cause here → 🚨 HUMAN APPROVAL gate → test-gap analysis → failing
   regression test → 🚨 approval → minimal fix → verify with the "Leo" script.

## Acceptance Criteria
- [ ] Root cause reproduced and documented (the specific broken link).
- [ ] Failing regression test that reproduces post-restart context loss.
- [ ] Fix restores full history after restart; the "Leo" script returns "Your name is Leo".
- [ ] "Retrieved N messages" (chat-id-tagged) equals the on-disk message count for that chat.
- [ ] No regression to within-run context, storage, or cleanup/archival.

## References
- `.github/CONSTITUTION.md`
- `.github/METHODOLOGY.md` (§VII Bug-Driven Development)
- `.github/BUG_DRIVEN_DEVELOPMENT.md`
- `specs/bugfixes/README.md`
- Related: `specs/bugfixes/bugfix-004-data-root-ignored.md`
