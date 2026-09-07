# Feature 070 — Prod Migration Runbook

**One-phase migration** (chosen 2026-09-06): prod stays STOPPED for the whole pipeline — no
pre-staging, no delta-merge. Simple, single shot, rehearsed twice.

Written from the **Stage 1 dress rehearsal executed 2026-09-04** against a byte copy of live prod
data (`~/denidin-migration/snapshots/prod-20260904/`). Every command below is the exact command
that rehearsal ran, only the data-root path changes for the live run. Runs **on the Mac** from the
`coder1` clone checked out on `feature/070-rolling-memory-window` (the migration tools live there);
the Windows box only stops/starts and sends/receives the `data/` tree. `<PY>` =
`/Users/yaron/Projects/DeniDin/coder1/apps/denidin-app/venv/bin/python3` (chromadb 1.5.9 —
confirmed to read the current prod store). `<APP>` = `.../coder1/apps/rolling-memory-backfill`.

Target release: **0.5.4-70** (both apps, cut from `feature/070` — tags `denidin-app-v0.5.4-70` /
`morning-mcp-app-v0.5.4-70`, artifacts under `/Users/yaron/Projects/DeniDin/artifacts/`).
`$PREV` = **0.5.4** (what prod runs now).

## The three copies (never confuse them)

| name | path | role | ever written to? |
|---|---|---|---|
| **backup #0** | `${WINPROD_DATA}_pre070_backup_$DATE` (on the Windows box) | fastest local restore | **no** |
| **backup #1 / `$PULL`** | `~/denidin-migration/prod-pull-$DATE/` (Mac, real named folder) | authoritative pre-migration snapshot | **no — never passed as `--data-root`, never edited** |
| **working copy / `$WORK`** | `~/denidin-migration/prod-work-$DATE/` (Mac) | the 4-tool pipeline runs here; this is what gets pushed back | yes, by the tools only |

`$WORK` is always a fresh `cp -r` **from `$PULL`**. If anything goes wrong, delete `$WORK` and
start over from the untouched `$PULL` — no re-pull from prod needed.

## Rehearsal result (what to expect — live counts will differ; prod moved since 2026-09-04)

| step | prod-snapshot outcome | wall time |
|---|---|---|
| consolidate | 96 source dirs → **2** canonical (GROUP `12e158e2` 954 msgs, SOLO `83495a2b` 127 msgs); 954/954 + 127/127, 0 dup, 0 ts-fallback; `_pre070_raw_<DATE>/` = all originals; `expired/` pruned | < 1 min |
| reconcile check | 2 chats → 2 dirs, **0** "maps to N session dirs" warnings, integrity OK, `chat_index.db` 2 rows | seconds |
| backfill `2026-08-01..<today-14>` | 21 committed markers/chat; **21 `daily_summary`** (14 GROUP + 7 SOLO non-empty days); ~21 summary + 21 embedding calls | **~6–8 min** |
| finalize | GROUP 559 archived / **395 live**; SOLO 101 archived / **26 live**; integrity OK | seconds |
| purge | GROUP collection 21675 → **14**; SOLO 13 → **7**; 21667 legacy deleted | seconds |
| turns (3 billed) | recent-context ✓; in-window history ✓; **out-of-window Aug-05 fee agreement answered from its `daily_summary`** ✓ | ~1 min |
| rollback (`rsync` restore) | `diff -rq` snapshot vs restored = **IDENTICAL**; no `chat_index.db`/`memory_rolls`/`_pre070_raw` | seconds |

**Downtime: ~15–20 min realistic** (pull + pipeline + push-back + deploy + verify). The 6–8 min
backfill is the long pole. Plan a **30-min window** for headroom.

---

## Live procedure (prod STOPPED throughout steps 3–8)

```bash
# 0. capture the Windows-side data path + set the paths
docker --context denidin-winprod inspect denidin-app-prod --format '{{json .Mounts}}'   # -> $WINPROD_DATA
DATE=$(date +%Y%m%d)
PULL=~/denidin-migration/prod-pull-$DATE     # backup #1 — PRISTINE, never touched
WORK=~/denidin-migration/prod-work-$DATE     # working copy — pipeline runs here
mkdir -p ~/denidin-migration/reports

# 1. pre-flight
scripts/windows_prod/tail_logs.sh denidin-winprod denidin-app-prod   # confirm no client mid-conversation

# 2. stop prod
./scripts/stop_all.sh prod
docker --context denidin-winprod ps                                  # both down

# 3. back up (x2) then make the working copy
#    3a. backup #0 — on the box
ssh denidin-winprod "cp -r '$WINPROD_DATA' '${WINPROD_DATA}_pre070_backup_$DATE'"
#    3b. backup #1 — pull to the Mac, into $PULL. This folder is now FROZEN.
mkdir -p $PULL && rsync -a --delete denidin-winprod:"$WINPROD_DATA"/ $PULL/
find $PULL/sessions -name session.json | wc -l                       # sanity vs the box
#    3c. working copy — everything past this point operates on $WORK, never $PULL
cp -r $PULL $WORK

# 4. consolidate (dry, then real) — on $WORK
cd <APP>
<PY> consolidate_sessions.py --data-root $WORK --report-only | tee ~/denidin-migration/reports/consolidate-dryrun-$DATE.txt
<PY> consolidate_sessions.py --data-root $WORK               | tee ~/denidin-migration/reports/consolidate-run-$DATE.txt
#   verify: 2 canonical dirs + _pre070_raw_$DATE/ (all originals); Σ in == Σ out per chat

# 4b. reconcile check — on $WORK
<PY> - <<EOF
from pathlib import Path; import logging; logging.basicConfig(level=logging.WARNING, force=True)
import sys; sys.path.insert(0, "/Users/yaron/Projects/DeniDin/coder1/apps/denidin-app")
from src.managers.session_manager import SessionManager
from src.managers.message_integrity import assert_message_integrity
sm = SessionManager(storage_dir=str(Path("$WORK")/"sessions"))
for c in sorted(sm.known_chats()):
    s = sm.get_session(c); assert_message_integrity(Path(sm.storage_dir)/(s.storage_path or s.session_id))
    print(c, s.session_id[:8], s.message_counter, "OK")
EOF
#   verify: 2 chats, NO "maps to N session dirs" warning, integrity OK

# 5. backfill — RUN IT BACKGROUNDED, NEVER behind a timeout, DO NOT interrupt
<PY> backfill_daily_summaries.py --data-root $WORK \
  --config /Users/yaron/Projects/DeniDin/coder1/apps/denidin-app/config/config.dev.json \
  --since 2026-08-01 --until <today-14>            # read the plan for the exact --until, then:
<PY> backfill_daily_summaries.py --data-root $WORK --config .../config.dev.json \
  --since 2026-08-01 --until <today-14> --yes > ~/denidin-migration/reports/backfill-$DATE.txt 2>&1 &
wait   # ~6-8 min
#   if interrupted: sqlite3 $WORK/memory_rolls/roll_markers.db "DELETE FROM roll_markers WHERE status='claimed'" then re-run
#   verify: all markers committed; one daily_summary per non-empty (chat,date)

# 5b. finalize (archive >14-day messages) — on $WORK
<PY> finalize_migration.py --data-root $WORK --report-only
<PY> finalize_migration.py --data-root $WORK | tee ~/denidin-migration/reports/finalize-$DATE.txt
#   verify: messages/ = last 14 days only; archived/ = the rest; integrity OK; ABORT->rollback if it fails

# 6. purge legacy session_summary — on $WORK
<PY> purge_legacy_summaries.py --data-root $WORK --report-only
<PY> purge_legacy_summaries.py --data-root $WORK | tee ~/denidin-migration/reports/purge-$DATE.txt
#   verify: each collection now holds only daily_summary records

# 7. full validation against $WORK (MIGRATION-SCOPE §8 checklist), prod still STOPPED

# 7b. push the migrated tree back  ($WORK -> prod; $PULL stays as the pristine snapshot)
rsync -a --delete $WORK/ denidin-winprod:"$WINPROD_DATA"/
ssh denidin-winprod "ls '$WINPROD_DATA/sessions'"     # 2 canonical + _pre070_raw_$DATE, no chat_index.db yet

# 8. deploy 0.5.4-70 — morning FIRST, then denidin (👤 explicit approval each; each is also an env-start)
scripts/deploy_release.sh morning-mcp-app prod 0.5.4-70
scripts/deploy_release.sh denidin-app   prod 0.5.4-70

# 9. post-deploy: startup log has NO reconcile warning, roll scheduler armed 02:00, 0 "Created new session";
#    real WhatsApp turns (godfather 1:1 + collections group): recent context + a mid-August recalled day;
#    one docker restart -> startup sweep no-op

# 10. monitor: first live 02:00 roll, then 24-48h
```

## Rollback

`$PREV` = **0.5.4**.

- **Before step 7b** (nothing pushed): `rm -rf $WORK`; `./scripts/run_all.sh prod` ($PREV image, untouched). `$PULL` and backup #0 are untouched — a retry just re-runs `cp -r $PULL $WORK` and step 4 onward.
- **After 7b, before deploy**: `ssh denidin-winprod "rsync -a --delete '${WINPROD_DATA}_pre070_backup_$DATE'/ '$WINPROD_DATA'/"` then `./scripts/run_all.sh prod` ($PREV). (Or re-push `$PULL` if backup #0 is suspect.)
- **After deploy**: `scripts/deploy_release.sh morning-mcp-app prod $PREV` + `scripts/deploy_release.sh denidin-app prod $PREV`, then restore `$WINPROD_DATA` from backup #0; file a bugfix, do not retry the same night.

## haleluya / merge to master — AFTER, separately

The spec move to `specs/done/` + CLAUDE.md T063 update + PR + merge to master is a **separate
step run only once prod is confirmed healthy on 0.5.4-70** (user's sequencing, 2026-09-06). It is
not part of this runbook. Merging does not redeploy anything.

## Notes from the rehearsal

- The backfill exceeded a 2-minute shell limit — it MUST run in a real terminal / backgrounded.
  Claim-first markers make an interrupted run resumable, but a same-process re-run within
  `stale_claim_minutes` (120) skips the one in-flight day unless you clear `status='claimed'` first.
- chromadb 1.5.9 read + wrote + deleted against the live 256 MB prod `chroma.sqlite3` with no
  format issue. Run the real migration with the same version.
- SOLO's collection had only **6** legacy records vs GROUP's **21,661** — confirms bugfix-035 H1
  (the re-summarization loop) is specific to the group collection's post-write verify.
- The `pending_ledger_events: []` poison field on session `0f5eaa04` is dropped by the
  consolidator; the tolerant-load WARNING on it is expected and harmless. (Confirmed still present
  on live prod 2026-09-06 — it errors on every load under $PREV; the consolidator clears it.)
- Mac↔Windows rsync can leave `._*` AppleDouble junk files. Add `--exclude='._*'` to the
  push-back rsync (step 7b) if `ls '$WINPROD_DATA'` shows any after step 3b.
