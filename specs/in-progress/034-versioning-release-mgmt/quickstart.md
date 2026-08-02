# Quickstart: Versioning & Release Management (Feature 034)

Manual verification scenarios once implementation lands, covering US1-US4. No dev/prod containers
need to be started specifically *for* this quickstart beyond whatever's already running — US1/US4
assume an already-running `denidin-app`/`morning-mcp-app` (dev or prod); **starting either
environment always needs its own explicit approval — nothing below authorizes that on its own.**

## Prerequisites

- Both apps have a `VERSION` file at their root with some starting value, e.g. `1.0.0`.
- `/Users/yaron/Projects/DeniDin/artifacts/` exists (see research.md Decision 7 for the
  cross-clone `.gitignore` coordination this may still need).
- `scripts/cut_release.sh` and `scripts/rollback_release.sh` are executable.

## US1 — See which version is currently deployed

With `morning-mcp-app-dev` (or `-prod`) running:
```
curl http://localhost:8000/health
```
Expect a `version` field matching that app's `VERSION` file content, alongside the existing
`status`/`environment` fields (unchanged).

With `denidin-app-dev` (or `-prod`) running, read any recent line of `logs/denidin.log` (not
specifically a startup line):
```
tail -5 logs/denidin.log
```
Expect every line to include the current version (e.g. `[v1.0.0]`), not just the first line after
process start.

## US2 — Cut a release

From a clean working tree on `master` (or wherever the deployed commit actually is), with a human
present to supply the version number:
```
scripts/cut_release.sh denidin-app 1.1.0
```
Expect: a summary is printed and confirmation requested (`[y/N]`) **before anything happens** — no
version number was suggested by anything other than what was typed at the command line. On
confirming:
- `apps/denidin-app/VERSION` now reads `1.1.0`.
- `apps/denidin-app/CHANGELOG.md` and `RELEASES.md` each have a new entry.
- `git tag -l 'denidin-app-v1.1.0'` shows the tag on the right commit.
- `/Users/yaron/Projects/DeniDin/artifacts/denidin-app/denidin-app-v1.1.0.tar` and `.json` exist.

Re-run the exact same command again — expect a refusal (REQ-REL-006), not a silent overwrite.

## US3 — Roll back to a prior release

With `denidin-app-v1.1.0` now deployed to `dev` (per US2 + a normal forward deploy) and
`denidin-app-v1.0.0`'s artifact still present:
```
scripts/rollback_release.sh denidin-app dev 1.0.0
```
Expect: no `docker build`/rebuild step runs — only `docker load` of the existing tarball, then the
`dev` container is recreated from it. Verify via US1's `/health`-or-log-line check that `1.0.0` is
now live. Confirm `git log master` is unchanged before/after (no history rewritten).

Then try rolling back to a version whose artifact was deliberately deleted first:
```
rm /Users/yaron/Projects/DeniDin/artifacts/denidin-app/denidin-app-v1.0.0.*
scripts/rollback_release.sh denidin-app dev 1.0.0
```
Expect: a clear failure naming the missing artifact — not a silent rebuild-from-source fallback.

## US4 — Ask the bot its own version over WhatsApp

With `denidin-app` running and some `VERSION` value set, send it a WhatsApp message asking "what
version are you running?" (any role — client, godfather, or admin).
Expect: an accurate reply stating the current version, with no MCP tool call involved (this is a
prompt-injection answer, not a tool round-trip — should be as fast as any other plain-text reply).

## Notes

- All four scenarios should also get automated coverage per `tasks.md` (Phase 2 of `plan.md`):
  US1/US2's version-in-log-line and `/health` behavior via unit tests; US2/US3's script behavior
  via integration-style tests that actually invoke the scripts against a scratch git repo/Docker
  context; US4 via a `billed`-tier real-API E2E test (text-only OpenAI call, same tier as Feature
  030's contact-card tests) since it exercises the real `AIHandler` → OpenAI round-trip.
- If US2's confirmation prompt is ever skipped, or a version number appears in an agent's message
  *before* the human has stated one, that is a regression of REQ-REL-002/CLAUDE.md's hard
  constraint — treat it as a P0 bug regardless of how the rest of the feature is behaving.
