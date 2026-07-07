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

## Terminology Glossary
- **session**: Tier-1 short-term conversation store, keyed by `whatsapp_chat`, persisted under
  `{storage_dir}/{session_id}/` with a `session.json` (metadata + ordered `message_ids`) and
  `messages/{message_id}.json` files.
- **whatsapp_chat**: WhatsApp chat id used as the session key (e.g. `972522968679@c.us`).
- **chat_to_session**: in-memory index `Dict[whatsapp_chat -> session_id]`, rebuilt from disk at
  startup by `_load_sessions()`.
- **storage_dir**: directory SessionManager reads/writes sessions from; taken from
  `config.memory['session']['storage_dir']` (default relative `data/sessions`), resolved against the
  process working directory (CWD).
- **conversation history**: the `[{"role","content"}...]` list rebuilt from a session's
  `messages/*.json` and prepended to the OpenAI request.
- **active session**: a session whose `last_active` is within `session_timeout_hours` (24h) — not
  expired, not archived, `storage_path == null`.

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

### Findings from free (no-restart) investigation — 2026-07-08
Ruled out from code + existing `logs/denidin.log` without a new repro:
- **(a) CWD/storage_dir**: ruled out — config path is also relative, so the app only runs from the
  app dir; `storage_dir` resolves consistently. See the hypothesis (a) section.
- **(c) load exception**: no `"Failed to load session"` / `"Failed to check session"` entries in the
  log — the index rebuilds cleanly; sessions are not being dropped on load.
- **Index behavior**: no post-restart `"Created new session"` for the active chat; the session is
  reused and "Retrieved N" climbs across restarts — i.e. context is preserved in this captured run.
- **Unrelated observation**: cleanup repeatedly fails to transfer old expired sessions
  `b1035d74`/`f82f4a42` with `empty_conversation` on every startup — a separate cleanup defect, not
  this bug (candidate follow-up ticket).

Net: the obvious causes are eliminated; a fresh instrumented "Leo" reproduction is required to catch
the failing link, since the currently-captured log only shows the *working* path.

## Hypothesis (a) CWD/storage_dir resolution — LARGELY RULED OUT (2026-07-08)
Initially the leading theory (would fit "files exist but AI forgets"). Ruled out by code inspection
for the reporter's two launch methods: `run_denidin.sh` does `cd "$SCRIPT_DIR"` (app dir), and
`python3 denidin.py` can only start from the app dir anyway because `CONFIG_PATH = 'config/config.json'`
is itself relative (from a wrong CWD, config load fails → exit 2 before any session work). Since
`from_file` combines `storage_dir` as the relative `data/sessions`, both methods resolve it to the
**same** `apps/denidin-app/data/sessions`. Still worth a one-line confirmation via instrumentation
(log the resolved absolute `storage_dir`), but no longer the primary suspect. NOTE: Docker (CWD `/app`,
mounted `data` volume) is also consistent — only relevant if the reporter ever restarts via a
different mechanism.

## Hypotheses To Test During Reproduction (revised)
- **(a) CWD/storage_dir resolution** — largely ruled out (above); confirm resolved absolute path once.
- **(b) chat-id key mismatch:** stored `session.whatsapp_chat` vs retrieval `effective_chat_id`
  (`chat_id or request.chat_id`, `ai_handler.py:338-366`).
- **(c) load exception on restart — ELEVATED (strongest restart-specific asymmetry):** the index is
  populated two different ways. Within a run, `get_session` inserts `chat_to_session[chat]=session_id`
  at session **creation** (`session_manager.py:121`). After a restart, the index is rebuilt **only**
  by `_load_sessions` (`session_manager.py:303-319`), which wraps each `_load_session` in
  `try/except` and, on **any** exception, logs and **skips** the session (never indexing it). So a
  session that worked all through a run can vanish from the index after restart if its
  `session.json` fails to load — e.g. `Session(**data)` raising `TypeError` on an unexpected/missing
  field (schema drift), a JSON parse error, or a partial write. Result: `get_session` misses the
  index → **creates a new empty session** → context lost, while the original files still sit on disk
  ("app seems to remember, AI forgets"). Confirming signals: a `_load_sessions` error log for that
  `session_id` at startup, then a post-restart `"Created new session"` for the chat.
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

## Requirements
- **REQ-SESSION-001**: After an app restart, the next message in a recently-active (<24h) chat MUST
  reuse the existing on-disk session (no new session created) and load its full conversation history.
- **REQ-SESSION-002**: `storage_dir` MUST resolve to the same absolute directory regardless of launch
  method (`./run_denidin.sh`, `python3 denidin.py`, Docker) / CWD.
- **REQ-SESSION-003**: The "Leo" reproduction MUST return "Your name is Leo" after restart.
- **REQ-SESSION-004**: Diagnostics MUST make the failing link observable (resolved absolute
  `storage_dir`, index hit vs. new-session, chat-id-tagged retrieved-message count).

## Acceptance Criteria
- [ ] Root cause reproduced and documented (the specific broken link) — REQ-SESSION-004.
- [ ] Failing regression test that reproduces post-restart context loss.
- [ ] Fix restores full history after restart; the "Leo" script returns "Your name is Leo" —
      REQ-SESSION-001, REQ-SESSION-003.
- [ ] `storage_dir` resolves identically across launch methods — REQ-SESSION-002.
- [ ] "Retrieved N messages" (chat-id-tagged) equals the on-disk message count for that chat.
- [ ] No regression to within-run context, storage, or cleanup/archival.

## References
- `.github/CONSTITUTION.md`
- `.github/METHODOLOGY.md` (§VII Bug-Driven Development)
- `.github/BUG_DRIVEN_DEVELOPMENT.md`
- `specs/bugfixes/README.md`
- Related: `specs/bugfixes/bugfix-004-data-root-ignored.md`
