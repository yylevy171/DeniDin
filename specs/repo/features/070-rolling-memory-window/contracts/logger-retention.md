# Contract: `logger.py` retention refactor (US5)

**Module**: `apps/denidin-app/src/utils/logger.py` **+ its byte-identical twin**
`apps/morning-mcp-app/src/denidin_mcp_morning/.../logger.py`. The two files must stay identical.

**Gate**: because this is a shared byte-twinned core util, a short design-review checkpoint with
the user **before** the refactor lands (plan Phase 5).

---

## Problem (measured live 2026-09-02)

Every module calls `get_logger(__name__)` → `setup_logger(name)` → attaches its **own**
`RotatingFileHandler(maxBytes=10MB, backupCount=5)` to the **same** `logs/denidin.log`, with
`propagate=False`. When one handler hits 10 MB and renames, the others (stale fds) trip their own
rollover a few KB later → 5 near-simultaneous rename cascades → 5 tiny out-of-order fragments
(`denidin.log.1..5` = 8.4 KB / 11 KB / 3.7 KB / 27 KB / 9.2 KB, `.2` newer than `.1`). Everything
before the last cascade is lost. Docker's `json-file` driver has `Opts=map[]` — no `max-size` /
`max-file` on either service in either compose file.

## Target design (plan-mode decision B — full fix)

### 1. One handler set, on the root logger

- `setup_logger` attaches the file handler + the `StreamHandler` **once, to the root logger**
  (`logging.getLogger()`), guarded so repeated calls don't stack handlers.
- `get_logger(name)` returns `logging.getLogger(name)` with `propagate=True` and no handlers of its
  own — records flow up to the single root handler set.
- The `_VersionFilter` moves to the root logger (still stamps every record). The existing
  `get_logger` test-env shortcut (`if root_logger.handlers: return getLogger(name)`) still works —
  in pytest the root handlers are pytest's; in production they are the ones `setup_logger` just
  attached.
- `LocalTimeFormatter` + `LOCAL_LOG_DATEFMT` unchanged.

### 2. Time-based rotation, keep every segment, gzip

- File handler becomes
  `TimedRotatingFileHandler(log_path, when=<logging.rotation_when="midnight">, backupCount=<logging.backup_count=0>, encoding="utf-8")`.
- `backupCount=0` → the handler never deletes a rotated segment.
- Set `handler.rotator` and `handler.namer` for gzip:
  - `namer`: `lambda name: name + ".gz"`
  - `rotator`: read the just-rotated plaintext file, write it through `gzip.open(dest, "wb")`,
    `unlink` the plaintext intermediate (this `unlink` is of a *log* file the handler itself just
    produced, not a message/session file — outside the US3 no-delete audit scope, and it must be
    called out as such in the audit test's allowlist).
- Result: `denidin.log` (active) + `denidin.log.2026-08-31.gz`, `denidin.log.2026-09-01.gz`, … one
  per day, never pruned by the app.

### 3. Docker `json-file` cap (compose, not app code)

`docker/docker-compose.prod.yml` **and** `docker/docker-compose.dev.yml`, on **both**
`denidin-app-<env>` **and** `morning-mcp-app-<env>`:

```yaml
    logging:
      driver: json-file
      options:
        max-size: "50m"
        max-file: "5"
```

The `docker logs` stream is now bounded (~250 MB/container) and **lossy** — acceptable only because
the app file handler retains full history independently (REQ-MEM-053b). The runbook states this
dependency.

### 4. Rotation is lossless (user requirement, 2026-09-03)

No log record emitted **during** a rollover may be dropped:

- Within one process, `logging`'s handler lock already serialises `emit` against `doRollover`, so
  a concurrent `logger.info(...)` blocks until the swap completes and then writes to the fresh
  base file — never to a closed fd.
- The gzip `rotator` must be **fail-safe**: if gzip raises for any reason, it leaves the rotated
  **plaintext** segment in place (does NOT `unlink` it) and re-raises after logging — a segment is
  never deleted before its compressed copy exists and is readable. `backupCount=0` guarantees the
  handler itself never prunes.
- Net invariant: for any burst of N records spanning ≥1 rotation, all N appear exactly once across
  `{active file} ∪ {*.gz} ∪ {any leftover *.log.<date> plaintext}` — none lost, none duplicated.

**Unit test (both apps)** — spawn several threads emitting a known, countable sequence continuously
while `when="S"` forces ≥2 rotations under load; then decompress every `.gz` + read the active file
(+ any plaintext leftover), parse the sequence numbers, assert the full set `1..N` is present with
no gaps and no dupes.

## Config

`AppConfiguration` gains a top-level `logging: Dict = field(default_factory=dict)`; `from_file`
defaults `{"rotation_when": "midnight", "backup_count": 0}`; `denidin.py` `config_dict` (~line
1024) gains `'logging': config.logging`. `setup_logger` reads `when` / `backupCount` from what the
caller passes (composed from `config.logging`), not from a global.

## Tests — `test_logger_retention.py` (both apps)

- Point `setup_logger` at a tmp dir, tiny `when` (e.g. `"S"` seconds) via the param, generate
  enough volume to force ≥ 3 rotations → assert every rotated `*.gz` exists, decompresses, and its
  content is intact and in order.
- Call `get_logger` N times for N different names → assert the **root** logger has exactly one
  file handler + one stream handler (no per-name stacking).
- Assert a child logger has 0 handlers and `propagate is True`.
