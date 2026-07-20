---
description: Finish off the current work - commit, push, PR, merge, docs update, spec cleanup, branch cleanup
---

The user has invoked the finish-feature shorthand ("haleluya" or a spelling variant, or this `/haleluya` command). See `.github/METHODOLOGY.md`'s "Finish-Feature Trigger Phrase" section and `CLAUDE.md`'s Spec-Driven Workflow section for the authoritative definition.

This assumes the actual work (feature or bugfix) in the current branch is already done and approved by the user — do not use this to skip any gate (tests must already pass, CONSTITUTION checks already satisfied). If work looks incomplete or unapproved, stop and check with the user before proceeding.

Do the following, in order:

1. **Review the diff**: `git status` / `git diff --stat` against the branch's base. Confirm nothing unexpected (secrets, stray files, runtime data) is staged.
2. **Commit**: stage the relevant files (never a blind `git add -A` without reviewing status first) and commit with a descriptive message following this repo's conventional-commit style (see recent `git log` for examples), ending with the `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>` trailer.
3. **Push**: push the current branch to `origin` with `-u` if not already tracking.
4. **Open a PR**: `gh pr create` with a concise title and a body covering Summary + Test plan, per this repo's PR conventions.
5. **Merge**: `gh pr merge --merge` (regular merge commit, never squash, per CONSTITUTION.md §III).
6. **Docs update**: if the change affects `CLAUDE.md`, `README.md` files, or other docs and they weren't already updated as part of the feature work, update them now.
7. **Spec cleanup**: move the feature/bugfix spec to its correct `specs/` folder per METHODOLOGY.md §XI's Folder Movement Rules (typically `specs/done/` for a merged feature), and update its `Status` line to reflect the merge (e.g. "Done - Merged to master (PR #N)").
8. **Cleanup**: after confirming the merge succeeded, sync local `master` (`git checkout master && git pull`), then delete the feature branch both locally (`git branch -d`) and remotely (`git push origin --delete`).
9. **Report**: a brief summary of what was merged (PR number/link) and confirmation that branches are cleaned up.

If any step requires a permission this environment doesn't grant automatically (e.g. push blocked by a classifier), stop and ask the user rather than working around it.
