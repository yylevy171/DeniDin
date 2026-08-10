# Production Analysis

Post-hoc reviews of what actually happened in `prod` — user intent vs. performed
action, UX friction, internal assumptions that broke against reality, and whether
the ledger/Morning state ends up representing reality.

These are **read-only investigations**. They are not bug reports filed one at a
time; they are periodic sweeps over a real usage window that produce a ranked
issue list. Individual issues get promoted into `specs/bugfixes/` or `specs/` as
they're picked up.

## Reviews

| Date | Window | Doc |
|---|---|---|
| 2026-08-09 | Aug 7–9, 2026 | [2026-08-09-aug7-9-review.md](2026-08-09-aug7-9-review.md) |

---

## How to run one of these (read-only runbook)

Everything below is non-mutating. **Never** start, stop, restart, redeploy, or
write to prod as part of an analysis. No `run_*.sh`, no `docker compose up`, no
edits to anything under the data mount.

### 1. Prod data (sessions, ledger events, ChromaDB memory)

Prod's persistent data folder is mounted on the Mac **read-only** over sshfs:

```bash
mount | grep denidin-winprod-data
# denidin-winprod:denidin-prod-data on /Users/yaron/denidin-winprod-data (macfuse, ..., read-only, ...)
```

If it isn't mounted: `./scripts/windows_prod/mount_data.sh denidin-winprod`
(mounts with `-o ro`).

Layout:

```
/Users/yaron/denidin-winprod-data/
  events/          # one immutable JSON per ledger event (Feature 033)
  sessions/        # <session-uuid>/session.json + messages/<msg-uuid>.json
  sessions/expired/<YYYY-MM-DD>/<session-uuid>/
  memory/          # ChromaDB — chroma.sqlite3 + per-collection dirs
  media/
```

### 2. ⚠️ Use an explicit interpreter

Bare `python3` on this machine can resolve to **another clone's venv**
(observed: `coder2/apps/morning-mcp-app/venv/bin/python3`). That is a
cross-clone violation. Always check and pin:

```bash
which -a python3          # confirm what you'd actually get
/usr/bin/python3 ...      # use the absolute path
```

### 3. Rendering a session as a transcript

`session.json` holds `message_ids` in order; each message is its own file. A
small renderer that walks the index, prints role/timestamp/content, and flags
messages present on disk but missing from the index is the fastest way to read
a conversation. (Reference implementation used for the 2026-08-09 review is
described in that doc's appendix.)

### 4. Prod logs

Two sources, both read-only:

```bash
# a) Persisted log files on the Windows box (survive container recreation)
source scripts/windows_prod/_wsl_ssh.sh
wsl_ssh_run denidin-winprod 'ls -la ~/denidin-prod/apps/denidin-app/logs/prod/'
wsl_ssh_run denidin-winprod "sed -n '/2026-08-07/,\$p' ~/denidin-prod/apps/denidin-app/logs/prod/denidin.log" > local.log

# b) Live container logs (only cover since the container was last recreated)
docker --context denidin-winprod ps
./scripts/windows_prod/tail_logs.sh denidin-winprod denidin-app-prod
```

`wsl_ssh_run` is a shell function — it cannot be wrapped in `timeout`. Use the
Bash tool's own timeout instead.

Timestamps are **Israel local time everywhere** — logs, ledger events, session
records alike — and every full timestamp carries its real offset (`+03:00` IDT,
`+02:00` IST). They can be compared directly.

This changed on **2026-08-10** (bugfix-037). Anything written **before** that
date still shows the old mixed representation: log lines in UTC with no label,
`captured_at`/`message_timestamp` as `+00:00`, and `event_id`/`event_date`/
`event_time` in local time with no offset — so on older data a ledger event's
`06:00` and its own log line's `03:00:27` are the same instant, three hours
apart on their face. Don't compare those directly.

### 5. ChromaDB inspection

Open the sqlite file immutably so nothing can be written:

```bash
/usr/bin/python3 -c "
import sqlite3
c=sqlite3.connect('file:/Users/yaron/denidin-winprod-data/memory/chroma.sqlite3?mode=ro&immutable=1',uri=True)
for r in c.execute('select id,name from collections'): print(r)
"
```

### 6. Ground truth

Prod data and logs tell you what DeniDin *believed*. They do **not** tell you
what Morning actually stored. Always get independent ground truth — a screenshot
or export of the Morning document list for the window. The single most valuable
finding of the first review came from a figure that appeared **only** in the
Morning UI and nowhere in our logs.

## What to look for

- **Intent vs. action** — diff what the user approved against what was created.
- **Reported vs. actual** — diff what DeniDin *said* it did against ground truth.
- **Loops** — repeated identical bot messages are the signature of a broken
  state machine, not a chatty model.
- **Errors that log as success** — `error=None` with a failure string in the
  output payload.
- **Recurring background errors** — hourly cleanup/transfer failures are easy to
  miss and can leak cost indefinitely.
- **Silent drops** — `WARNING ... skipping/discarding/rejecting` lines.
