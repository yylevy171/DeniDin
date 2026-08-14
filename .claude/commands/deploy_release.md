---
description: Deploy a cut release (both apps) to dev or prod, using scripts/deploy_release.sh only
---

The user has invoked `/deploy_release <env> <version>` — e.g. `/deploy_release dev 0.4.2` or
`/deploy_release prod 0.4.2`. Both args are required; if either is missing, ask for it rather
than guessing (CLAUDE.md's "VERSION AND RELEASE DECISIONS ARE HUMAN-ONLY" banner — this applies
to the target environment too, not just the version).

**This command invoking with explicit `<env>`/`<version>` IS the human's explicit, fresh
approval for this specific deploy** — per CLAUDE.md's "never start an environment without
approval" rule, that approval is per-action, and typing this command with real arguments is that
action's approval. Don't ask again before proceeding, but also don't infer or reuse this
approval for anything beyond this exact `<app> <env> <version>` triple x2 (morning-mcp-app +
denidin-app) — a later, separate deploy still needs its own fresh invocation.

Do the following, in order:

1. **Confirm the version was actually cut for both apps** — check
   `artifacts/denidin-app/denidin-app-v<version>.tar` and
   `artifacts/morning-mcp-app/morning-mcp-app-v<version>.tar` both exist. If either is missing,
   stop and tell the user rather than attempting a deploy of a version that was never cut (never
   run `scripts/cut_release.sh` yourself to fix this — cutting is its own separate, human-only
   decision, never bundled into a deploy).
2. **Deploy `morning-mcp-app` first, then `denidin-app`** (CLAUDE.md: morning-mcp-app must be up
   before denidin-app, which depends on discovering its MCP tunnel at startup):
   ```
   ./scripts/deploy_release.sh morning-mcp-app <env> <version>
   ./scripts/deploy_release.sh denidin-app <env> <version>
   ```
3. **Run `scripts/deploy_release.sh` directly and ONLY that — no manual pre-flight checks**
   (`tailscale status`, a manual `ssh` probe, or anything else) before either call. The script
   performs its own connectivity/health verification internally and fails loudly with a clear
   error if something's wrong; a manual check first is redundant, not caution (see
   CLAUDE.md/CONSTITUTION.md §VII/METHODOLOGY.md's release-prompt section — this is a hard,
   explicitly documented rule, not a style preference).
4. **If either call fails**, stop and report the failure plainly — do not retry silently, do not
   attempt a workaround, do not proceed to the second app if the first failed.
5. **After both succeed**, do a basic cross-app health sanity check beyond just trusting each
   script's own success message — especially for `dev`, where the two apps share
   `shared/active_env.json` and one app's container action can affect the other's watchdog (see
   `feedback_bundle_start_both_apps.md`'s 2026-08-13 addendum, a real incident this session).
   Check `docker ps` for both containers AND tail each one's own recent logs for signs of actual
   life (not just container status) — for `prod`, use
   `scripts/windows_prod/tail_logs.sh denidin-winprod <service>` (no `-f`, one-shot) rather than
   a fresh ad-hoc SSH session.
6. **Report**: which app(s)/env/version were deployed, each script's own verification result, and
   the cross-app health check outcome. Never claim success from one app's health check alone when
   two were deployed.
