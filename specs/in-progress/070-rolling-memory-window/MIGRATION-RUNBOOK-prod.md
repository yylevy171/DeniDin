# Feature 070 — Prod Migration Runbook

Written from the **Stage 1 dress rehearsal executed 2026-09-04** against a byte copy of live prod
data (`~/denidin-migration/snapshots/prod-20260904/`). Every command below is the exact command
that rehearsal ran, only `--data-root` changes for the live run. Runs **on the Mac**; the Windows
box only stops/starts and sends/receives the `data/` tree. `<PY>` =
`/Users/yaron/Projects/DeniDin/coder1/apps/denidin-app/venv/bin/python3` (chromadb 1.5.9 —
confirmed to read the current prod store). `<APP>` = `.../apps/rolling-memory-backfill`.

## Rehearsal result (what to expect)

| step | prod-snapshot outcome | wall time |
|---|---|---|
| consolidate | 96 source dirs → **2** canonical (GROUP `12e158e2` 954 msgs, SOLO `83495a2b` 127 msgs); 954/954 + 127/127, 0 dup, 0 ts-fallback; `_pre070_raw_20260904/` = all 96 originals; `expired/` pruned | < 1 min |
| reconcile check | 2 chats → 2 dirs, **0** "maps to N session dirs" warnings, integrity OK, `chat_index.db` 2 rows | seconds |
| backfill `2026-08-01..08-21` | 21 committed markers/chat; **21 `daily_summary`** (14 GROUP + 7 SOLO non-empty days); ~21 summary + 21 embedding calls | **~6–8 min** |
| finalize | GROUP 559 archived / **395 live**; SOLO 101 archived / **26 live**; integrity OK | seconds |
| purge | GROUP collection 21675 → **14**; SOLO 13 → **7**; 21667 legacy deleted | seconds |
| turns (3 billed) | recent-context ✓; in-window history ✓; **out-of-window Aug-05 fee agreement answered from its `daily_summary`** ✓ | ~1 min |
| rollback (`rsync` restore) | `diff -rq` snapshot vs restored = **IDENTICAL**; no `chat_index.db`/`memory_rolls`/`_pre070_raw` | seconds |

**Downtime budget: ~30 min work + ~5 min push-back rsync + deploy → plan a 45-min window.**

---

## Live procedure (prod STOPPED throughout steps 3–8)

```bash
# 0. one-time: capture the Windows-side data path
docker --context denidin-winprod inspect denidin-app-prod --format '{{json .Mounts}}'   # -> $WINPROD_DATA
DATE=$(date +%Y%m%d)
LIVE=~/denidin-migration/prod-live-$DATE

# 1. pre-flight
scripts/windows_prod/tail_logs.sh denidin-winprod denidin-app-prod   # confirm no client mid-conversation

# 2. stop prod
./scripts/stop_all.sh prod
docker --context denidin-winprod ps                                  # both down

# 3. back up on the box + pull to the Mac
ssh denidin-winprod "cp -r '$WINPROD_DATA' '${WINPROD_DATA}_pre070_backup_$DATE'"
mkdir -p $LIVE && rsync -a --delete denidin-winprod:"$WINPROD_DATA"/ $LIVE/
find $LIVE/sessions -name session.json | wc -l                       # sanity vs the box

# 4. consolidate (dry, then real)
cd <APP>
<PY> consolidate_sessions.py --data-root $LIVE --report-only | tee ~/denidin-migration/reports/consolidate-dryrun-$DATE.txt
<PY> consolidate_sessions.py --data-root $LIVE               | tee ~/denidin-migration/reports/consolidate-run-$DATE.txt
#   verify: 2 canonical dirs + _pre070_raw_$DATE/ (all originals); Σ in == Σ out per chat

# 4b. reconcile check
<PY> - <<'EOF'
from pathlib import Path; import logging; logging.basicConfig(level=logging.WARNING, force=True)
import sys; sys.path.insert(0, "/Users/yaron/Projects/DeniDin/coder1/apps/denidin-app")
from src.managers.session_manager import SessionManager
from src.managers.message_integrity import assert_message_integrity
sm = SessionManager(storage_dir=str(Path("REPLACE_LIVE")/"sessions"))
for c in sorted(sm.known_chats()):
    s = sm.get_session(c); assert_message_integrity(Path(sm.storage_dir)/(s.storage_path or s.session_id))
    print(c, s.session_id[:8], s.message_counter, "OK")
EOF
#   verify: 2 chats, NO "maps to N session dirs" warning, integrity OK

# 5. backfill — RUN IT BACKGROUNDED, NEVER behind a timeout, DO NOT interrupt
<PY> backfill_daily_summaries.py --data-root $LIVE \
  --config /Users/yaron/Projects/DeniDin/coder1/apps/denidin-app/config/config.dev.json \
  --since 2026-08-01 --until <today-14>            # read the plan, then:
<PY> backfill_daily_summaries.py --data-root $LIVE --config .../config.dev.json \
  --since 2026-08-01 --until <today-14> --yes > ~/denidin-migration/reports/backfill-$DATE.txt 2>&1 &
wait   # ~6-8 min
#   if interrupted: sqlite3 $LIVE/memory_rolls/roll_markers.db "DELETE FROM roll_markers WHERE status='claimed'" then re-run
#   verify: all markers committed; one daily_summary per non-empty (chat,date)

# 5b. finalize (archive >14-day messages)
<PY> finalize_migration.py --data-root $LIVE --report-only
<PY> finalize_migration.py --data-root $LIVE | tee ~/denidin-migration/reports/finalize-$DATE.txt
#   verify: messages/ = last 14 days only; archived/ = the rest; integrity OK; ABORT->rollback if it fails

# 6. purge legacy session_summary
<PY> purge_legacy_summaries.py --data-root $LIVE --report-only
<PY> purge_legacy_summaries.py --data-root $LIVE | tee ~/denidin-migration/reports/purge-$DATE.txt
#   verify: each collection now holds only daily_summary records

# 7. full validation against $LIVE (MIGRATION-SCOPE §8 checklist), prod still STOPPED

# 7b. push the migrated tree back
rsync -a --delete $LIVE/ denidin-winprod:"$WINPROD_DATA"/
ssh denidin-winprod "ls '$WINPROD_DATA/sessions'"     # 2 canonical + _pre070_raw_$DATE, no chat_index.db yet

# 8. deploy the next version (0.5.4 shipped without 070 — likely 0.5.5, HUMAN-SUPPLIED)  (👤 each: /haleluya, cut_release x2 with human-supplied version, deploy_release morning then denidin)

# 9. post-deploy: startup log has NO reconcile warning, roll scheduler armed 02:00, 0 "Created new session";
#    real WhatsApp turns (godfather 1:1 + collections group): recent context + a mid-August recalled day;
#    one docker restart -> startup sweep no-op

# 10. monitor: first live 02:00 roll, then 24-48h
```

## Rollback

`$PREV` = the version prod is running right now (check before you start — likely 0.5.4).

- **Before step 7b** (nothing pushed): `rm -rf $LIVE`; `./scripts/run_all.sh prod` ($PREV image, untouched).
- **After 7b, before deploy**: `ssh denidin-winprod "rsync -a --delete '${WINPROD_DATA}_pre070_backup_$DATE'/ '$WINPROD_DATA'/"` then start $PREV.
- **After deploy**: `scripts/deploy_release.sh denidin-app prod $PREV` + restore `$WINPROD_DATA` from the backup; file a bugfix, do not retry the same night.

## Notes from the rehearsal

- The backfill exceeded a 2-minute shell limit — it MUST run in a real terminal / backgrounded.
  Claim-first markers make an interrupted run resumable, but a same-process re-run within
  `stale_claim_minutes` (120) skips the one in-flight day unless you clear `status='claimed'` first.
- chromadb 1.5.9 read + wrote + deleted against the live 256 MB prod `chroma.sqlite3` with no
  format issue. Run the real migration with the same version.
- SOLO's collection had only **6** legacy records vs GROUP's **21,661** — confirms bugfix-035 H1
  (the re-summarization loop) is specific to the group collection's post-write verify.
- The `pending_ledger_events: []` poison field on `0f5eaa04` is dropped by the consolidator; the
  tolerant-load WARNING on it is expected and harmless.
