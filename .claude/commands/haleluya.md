---
description: Finish off the current work - commit, push, PR, merge, deploy, docs update, spec cleanup, branch cleanup
---

The user has invoked the finish-feature shorthand ("haleluya" or a spelling variant, or this `/haleluya` command). See `.github/METHODOLOGY.md`'s "Finish-Feature Trigger Phrase" section and `CLAUDE.md`'s Spec-Driven Workflow section for the authoritative definition.

This assumes the actual work (feature or bugfix) in the current branch is already done and approved by the user — do not use this to skip any gate (tests must already pass, CONSTITUTION checks already satisfied). If work looks incomplete or unapproved, stop and check with the user before proceeding.

Do the following, in order:

1. **Review the diff**: `git status` / `git diff --stat` against the branch's base. Confirm nothing unexpected (secrets, stray files, runtime data) is staged.
2. **Commit**: stage the relevant files (never a blind `git add -A` without reviewing status first) and commit with a descriptive message following this repo's conventional-commit style (see recent `git log` for examples), ending with the `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>` trailer.
3. **Push**: push the current branch to `origin` with `-u` if not already tracking.
4. **Open a PR**: `gh pr create` with a concise title and a body covering Summary + Test plan, per this repo's PR conventions.
5. **Merge**: `gh pr merge --merge` (regular merge commit, never squash, per CONSTITUTION.md §III).
6. **Deploy**: merging to `master` does NOT redeploy anything by itself — Docker Compose does not auto-rebuild on `up -d`/`restart` when source code changed on disk (config-file changes ARE picked up live, since configs are bind-mounted, not baked into the image; code changes are not). For every environment container currently running (`docker ps`) whose app source this change touched:
   - `docker compose -f docker-compose.<env>.yml build <service>` to rebuild the image with the new code
   - Then `docker compose -f docker-compose.<env>.yml up -d <service>` (or the app's `run_*.sh <env>` script) to recreate the container from the fresh image
   - Verify: tail that environment's log for a clean startup, and if the change is behaviorally observable (e.g. a log line that only appears with the fix), confirm it shows up on the next real interaction
   - If a change only touched a mounted data file (e.g. `runtime_constitution.md`, which `AIHandler` hot-reloads via mtime check) or an example/config template, no rebuild is needed — restart is enough, or sometimes nothing at all
   - Skip this step only if no environment is currently running the affected app, or the user explicitly says not to deploy yet
7. **Docs update**: if the change affects `CLAUDE.md`, `README.md` files, or other docs and they weren't already updated as part of the feature work, update them now.
8. **Spec cleanup**: move the feature/bugfix spec to its correct `specs/` folder per METHODOLOGY.md §XI's Folder Movement Rules (typically `specs/done/` for a merged feature), and update its `Status` line to reflect the merge (e.g. "Done - Merged to master (PR #N)").
9. **Cleanup**: after confirming the merge succeeded, sync local `master` (`git checkout master && git pull`), then delete the feature branch both locally (`git branch -d`) and remotely (`git push origin --delete`).
10. **Release the dev lock, if you're holding it**: read `shared/active_env.json` (via `env_lock.sh`'s `env_lock_identity`/`env_lock_read`, sourced from repo root). If `active_env` is `dev` and `owner` matches this clone's personality, the feature work is done, so release it: run `stop_denidin.sh dev` and/or `stop_morning_mcp.sh dev` (whichever is actually running per `docker ps`) to stop the container(s) and clear the lock. Only release a lock this clone actually owns — never `-force` someone else's dev lock as part of this flow. Skip silently if `active_env` isn't `dev`, or the owner isn't this clone's personality.
11. **Report**: a brief summary of what was merged (PR number/link), what was redeployed where, whether the dev lock was released, and confirmation that branches are cleaned up.

If any step requires a permission this environment doesn't grant automatically (e.g. push blocked by a classifier), stop and ask the user rather than working around it.
