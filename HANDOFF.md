# Session Handoff — 2026-08-20

**Clone**: coder1 ("Avi")
**Branch at end of session**: `chore/windows-prod-persistent-mount` (fully merged, nothing pending on it)

Everything below is **completed and merged to master** unless explicitly marked otherwise —
this is a summary for reference/continuity, not a "pick up where I left off" list. Nothing is
mid-flight.

---

## 1. Billed/expensive test staleness sweep (Feature 043)

Swept every file under `tests/billed/` and `tests/expensive/` against Feature 043's real,
already-merged schema changes (Phase 11's LedgerEvent revision, the Message identity redesign).
Found and fixed 4 real assertion bugs (not cosmetic):

- `tests/e2e_helpers.py`'s `assert_image_path_persisted` checked `role == "user"`, but `role` is
  now the real RBAC role — would have failed every image/media billed/expensive test. Fixed to
  check `ai_required_role`.
- `test_ledger_event_capture_e2e.py`'s persisted-event helper still asserted the removed
  `message_timestamp`/`sender` fields instead of `event_datetime`.
- `test_group_b_reference_approval_e2e.py` and `test_denidin_vcf_contact_e2e.py` both filtered
  ledger events by the removed `whatsapp_chat` field — silently always `False`, making a
  false-positive guard vacuous. Fixed to filter by `session_id`.

Added new-field coverage (`bank_number`/`bank_branch`/`bank_account`/`payer_name`/`vat_status`/
`extracted_text`) that had zero persisted-record assertions before.

**Verified live**: all fixes confirmed against real data, not just reasoned about — 12/12
originally-passing tests still pass, plus a 12-test random sample (10 billed + 2 expensive) via
the newly-merged `scripts/run_single_test.sh`, 11/12 passing (1 unrelated pre-existing Morning-
sandbox test-client-seeding collision).

Merged: PR #236.

## 2. Master-merge impact review → real player bug found and fixed (Feature 043)

Merged master (brought in Feature 054 reminders + a `max_retries` config fix) and assessed
impact:

- Feature 054 confirmed structurally isolated from ledger capture (`capture_ledger_event`
  explicitly bypasses reminders' new local-tool-approval gate; constitution has explicit
  bidirectional scoping).
- Found and fixed: `player/run_player.py`'s `_build_config_dict` was silently dropping the new
  `max_retries` config field (same bug-class as an already-documented `data_root` gap in the
  same function).

Merged: PR #236 (same PR as above).

## 3. Player idMessage/dedup collision — real, serious bug found and fixed (Feature 043)

A **second**, concurrent master merge (PR #235) landed `RecentNotificationDeduper`
(`denidin.py`) — suppresses any repeat `idMessage` within a 10-minute window. The player's
synthesized `idMessage` was built from a per-`PlayerExportSource`-instance counter that always
restarted at 1 — and the clarification-loop mechanism constructs a fresh `PlayerExportSource`
for the original dispatch *and every follow-up round*. Net effect: **every dispatch in an
entire player run got the identical `idMessage="player-1"`** — with the new deduper active,
only the first would ever reach a handler; everything else within a 10-minute window silently
swallowed, no error. Would have collapsed a real multi-hour export replay to ~1 message/10min.

**Fixed**: `idMessage` is now a real random UUID, generated inside `synthesize_notification`
itself. `idmessage_seq` removed entirely. Verified directly (5 identical-argument calls → 5
distinct ids). Also documented a deferred design note (per explicit human decision, not
implemented): `ParsedMessage.raw_line_no` should, in principle, drive `Message.order_num` for a
player-replayed message instead of `SessionManager`'s session-relative counter — needs
`SessionManager.add_message` to accept an optional override, left for a future session.

Merged: PR #237.

## 4. Feature 043 closed out

Spec moved from `specs/in-progress/` to `specs/done/043-production-data-setup-tooling/` — Status
line explicitly lists remaining open items (Phase 8, Phases 5–7, Phase 10, the constitution
"model should ask more often" gap, Finding A) as **deliberately non-blocking**, tracked for a
future session, not implying nothing's left.

One real slip caught and fixed along the way: the first move-commit (`7fcf731`) correctly moved
the directory but somehow committed the file's *pre-edit* Status-line content — caught
immediately after merge by directly diffing origin/master, fixed same-session.

Merged: PR #237 (move), PR #238 (fix).

## 5. Release v0.5.0 cut and deployed — both apps, both environments

Cut via `scripts/cut_release.sh` (human-supplied exact version, human-supplied summaries —
never inferred): `denidin-app-v0.5.0`, `morning-mcp-app-v0.5.0`. Real git tags, real Docker
artifacts saved to `/Users/yaron/Projects/DeniDin/artifacts/`. Merged via PR #239 (master is
branch-protected — direct push was rejected, went through a PR like everything else).

**Deployed and verified live**, in order (morning-mcp-app first, per dependency), dev then prod:

| App | Env | Status |
|---|---|---|
| morning-mcp-app | dev | ✅ verified live |
| denidin-app | dev | ✅ verified live |
| morning-mcp-app | prod | ✅ verified live (denidin-winprod) |
| denidin-app | prod | ✅ verified live (denidin-winprod) |

**Note**: dev was locked by another clone ("Ruth") with live containers running (~56min
uptime). Force-released with explicit user approval (`./scripts/stop_all.sh dev -force`) to
acquire it — a real disruption to another active session, done deliberately, not silently.

v0.5.0 highlights: Feature 054 (reminders — create/list/modify/delete via Hebrew conversation,
approval-gated, scheduled delivery); Feature 043 Phase 11 (ledger schema revision — bank/
payment-detail fields, unified reference mechanism); the WhatsApp export "player" tool; real
Message identity fields (JID + RBAC role); two real bug fixes (double OpenAI retry elimination,
notification dedup). Full text in both apps' `CHANGELOG.md`/`RELEASES.md`.

## 6. Prod data verified accessible + reminders DB confirmed real

`~/denidin-winprod-data` (read-only sshfs mount) confirmed showing real prod data: `events/`,
`media/`, `memory/`, `reminders/`, `sessions/`. `reminders/reminders.db` confirmed as a genuine
SQLite database with the correct Feature 054 schema (`reminders`/`reminder_exceptions`/
`fired_occurrences` tables) — 0 rows, expected for a freshly-recreated container.

## 7. Windows-prod data mount made permanent (new LaunchAgent)

Explicit requirement: *"if the Mac is on, the mount should be there. Always."* The old
`mount_data.sh` (`-o reconnect`) only survived brief network blips, not a full reboot or the
sshfs process actually dying.

Built: `scripts/windows_prod/mount_data_foreground.sh` (sshfs run in the foreground — this
build doesn't cleanly daemonize, confirmed live) + `com.denidin.winprod-mount.plist`
(`RunAtLoad` + `KeepAlive` — launchd directly supervises the sshfs process, restarting/
remounting it whenever it exits for any reason) + `install_persistent_mount.sh` (reproducible
installer). `unmount_data.sh` updated to unload the agent first, so an intentional unmount
actually sticks instead of being silently re-mounted.

**Verified live end-to-end**: `kill -9` on the running sshfs process → new PID, healthy mount
again within `ThrottleInterval` (15s), no manual action. `unmount_data.sh` → correctly stays
unmounted after 20s (agent unloaded). Installer → correctly re-establishes it. Along the way,
found and fixed a real launchd-PATH gap (Homebrew's bin dirs aren't in launchd's default PATH,
so a bare `sshfs` call failed under launchd despite working interactively).

**Currently live on this Mac right now** (`launchctl print gui/$(id -u)/com.denidin.winprod-mount`
shows `state = running`, `keepalive | runatload`).

Merged: PR #241.

## 8. Stray uncommitted edits from another clone ("Ruth") reverted

53 tracked files (specs, `.github/CONSTITUTION.md`/`ARCHITECTURE.md`, root `CLAUDE.md`, a couple
of scripts) had every `specs/done/NNN-.../` cross-reference rewritten **in-place, uncommitted**
to a nonexistent `specs/done/vX.Y.Z/NNN-.../` path (Ruth appears to be mid-way through some
"reorganize specs/done/ by release version" restructuring elsewhere, and it leaked into this
clone's working tree by mistake). No folders were actually moved on disk, so every link would
have broken. Nothing was ever committed, so `git restore .` was sufficient — confirmed
`git status`/`git diff` fully clean afterward, spot-checked several files back to correct real
paths.

---

## Current state / where things are

- **master**: has everything above (PRs #236, #237, #238, #239, #241, plus incidental
  unrelated merges from other work — #240 spec-059-placeholder, Ruth's own #234/#235 reminders
  work).
- **denidin-app / morning-mcp-app**: both at `v0.5.0`, live in dev and prod, all 4 verified via
  `deploy_release.sh`'s own health checks.
- **Windows-prod data mount**: permanently up via LaunchAgent, verified self-healing.
- **This clone's working tree**: fully clean, `chore/windows-prod-persistent-mount` branch (its
  own PR already merged — safe to leave as-is, per this project's "branches are never deleted
  as part of any flow" convention, or delete manually if desired).

## Nothing pending from this session

Every thread above reached a merged, verified, deployed end state. The only *deliberately*
deferred items are the ones already flagged as non-blocking in Feature 043's own spec Status
line (Phase 8, Phases 5–7, Phase 10, the constitution "ask more often" gap, Finding A) — see
`specs/done/043-production-data-setup-tooling/spec.md` and its `HANDOFF.md` for detail on those,
not repeated here.
