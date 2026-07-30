---
description: Finish off the current work - commit, push, PR, merge, deploy, docs update, spec cleanup
---

The user has invoked the finish-feature shorthand ("haleluya" or a spelling variant, or this `/haleluya` command). See `.github/METHODOLOGY.md`'s "Finish-Feature Trigger Phrase" section and `CLAUDE.md`'s Spec-Driven Workflow section for the authoritative definition.

This assumes the actual work (feature or bugfix) in the current branch is already done and approved by the user — do not use this to skip any gate (tests must already pass, CONSTITUTION checks already satisfied). If work looks incomplete or unapproved, stop and check with the user before proceeding.

Do the following, in order:

1. **Verify a spec exists**: extract the numeric ID from the branch name (e.g. `024` from `feature/024-ledger-event-recognition`, `009` from `bugfix/009-...`) and confirm a matching spec file is actually committed to git under `specs/` (any of `backlog/`, `in-progress/`, `done/`, `obsolete/`, `bugfixes/`, `done/bugfixes/`, `obsolete/bugfixes/`, `not_reproducible/bugfixes/` — check both the working tree and `git log --all --oneline --name-only | grep <id>` in case it exists but isn't staged/committed yet on this branch). **If no spec is found, STOP here and tell the user before doing anything else** — do not commit, push, or merge. This exists because feature 024 (Ledger Event Recognition) was fully implemented and merged with **no spec file ever committed at all** (confirmed via full git history search, 2026-07-30) — silently proceeding past a missing spec is exactly how that happened, and haleluya assuming "the work is already done" must not extend to assuming its spec exists too.
2. **Review the diff**: `git status` / `git diff --stat` against the branch's base. Confirm nothing unexpected (secrets, stray files, runtime data) is staged.
3. **Commit**: stage the relevant files (never a blind `git add -A` without reviewing status first) and commit with a descriptive message following this repo's conventional-commit style (see recent `git log` for examples), ending with the `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>` trailer.
4. **Push**: push the current branch to `origin` with `-u` if not already tracking.
5. **Open a PR**: `gh pr create` with a concise title and a body covering Summary + Test plan, per this repo's PR conventions.
6. **Merge**: `gh pr merge --merge` (regular merge commit, never squash, per CONSTITUTION.md §III).
7. **Test deploy**: merging to `master` does NOT redeploy anything by itself — Docker Compose does not auto-rebuild on `up -d`/`restart` when source code changed on disk (config-file changes ARE picked up live, since configs are bind-mounted, not baked into the image; code changes are not). This is a *test* deploy — verify the fresh code actually works, then tear it back down; do not leave it up through steps 9-10 (docs/spec cleanup) just for convenience, especially since another coder/clone may need the env in the meantime. For every environment currently running (`docker ps`) whose app source this change touched:
   - `docker compose --project-directory . -f docker/docker-compose.<env>.yml build <service>` to rebuild the image with the new code
   - Then `scripts/run_all.sh <env>` to recreate the container(s) from the fresh image (bundled — don't bring up just one app's container)
   - Verify: tail that environment's log for a clean startup, and if the change is behaviorally observable (e.g. a log line that only appears with the fix), confirm it shows up on the next real interaction
   - If a change only touched a mounted data file (e.g. `runtime_constitution.md`, which `AIHandler` hot-reloads via mtime check) or an example/config template, no rebuild is needed — restart is enough, or sometimes nothing at all
   - Skip this step only if no environment is currently running the affected app, or the user explicitly says not to deploy yet
8. **Release the dev lock, if you're holding it (and tear down what step 7 brought up)**: read `shared/active_env.json` (via `scripts/env_lock.sh`'s `env_lock_identity`/`env_lock_read`). If `active_env` is `dev` and `owner` matches this clone's personality, the feature work (and its test deploy) is done, so release it: run `scripts/stop_all.sh dev` to stop the container(s) and clear the lock. Only release a lock this clone actually owns — never `-force` someone else's dev lock as part of this flow. Skip silently if `active_env` isn't `dev`, or the owner isn't this clone's personality.
9. **Docs update**: if the change affects `CLAUDE.md`, `README.md` files, or other docs and they weren't already updated as part of the feature work, update them now.
10. **Spec cleanup**: move the feature/bugfix spec to its correct `specs/` folder per METHODOLOGY.md §XI's Folder Movement Rules (typically `specs/done/` for a merged feature), and update its `Status` line to reflect the merge (e.g. "Done - Merged to master (PR #N)").
11. **Sync**: after confirming the merge succeeded, sync local `master` (`git checkout master && git pull`). **NEVER delete git branches** — not the just-merged branch, not any other branch, locally or remotely, `-d` or `-D`, as part of this flow or any other step above. Leave the merged branch in place; if the user wants it deleted, they'll say so explicitly.
12. **Report**: a brief summary of what was merged (PR number/link), what was test-deployed and torn down, and whether the dev lock was released.

If any step requires a permission this environment doesn't grant automatically (e.g. push blocked by a classifier), stop and ask the user rather than working around it.
