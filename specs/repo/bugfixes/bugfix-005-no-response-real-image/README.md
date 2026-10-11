# BUGFIX-005: No Response When Sending Real Image via WhatsApp

Summary: moved from `specs/bugfixes/P0-001-no-response-real-image.md`.

Status: Done (analysis + fix implemented). See linked specs in `specs/bugfixes/` for detailed RCA documents.

Key points:
- Root cause: missing `@bot.router.message` handlers for media types in `denidin.py`.
- Fix: added media routers, initialized `MediaHandler`, centralized Hebrew error messages, updated tests.
- Tests: non-expensive unit tests passed; integration tests (non-expensive) passed; expensive media flow tests passed.

Review / PR:
- Branch: `feature/005-media-router-fix` (suggested)
- Commit message: "BUGFIX-005: Add media routers, initialize MediaHandler, centralize error messages, update tests"
