# specs/done/ Version Mapping — 2026-08-20 Reorganization

`specs/done/` is now organized by release version: `specs/done/vX.Y.Z/<NNN-feature-name>/` and
`specs/done/vX.Y.Z/bugfix-NNN-description.md` sit side by side under the same version folder, no
separate `features`/`bugfixes` split. See CLAUDE.md's `specs/done/` note for the ongoing
convention (a freshly-finished spec lands flat until `scripts/cut_release.sh` sweeps it into a
version folder at the next actual release cut).

## Methodology for this one-time migration

Every pre-existing `specs/done/` entry was assigned a version using, in order:

1. **When was it actually merged/finished**, via `git log --diff-filter=A --follow` against the
   spec's own path (when the folder/file first landed in `specs/done/` or `specs/done/bugfixes/`)
   — not the spec's own "Created" front-matter date, which reflects when the *spec* was written,
   not when the *code* shipped.
2. **Matched against `apps/denidin-app/CHANGELOG.md` and `apps/morning-mcp-app/CHANGELOG.md`**:
   the nearest release cut on or after that date, with the release's own summary text used to
   confirm/disambiguate when multiple releases shared a cut date.
3. **Everything that predates Feature 034** (versioning itself, introduced 2026-08-02, `0.0.1`
   "Initial versioned release") has no real recorded version at all — per explicit user decision,
   these are all best-effort bucketed under `v0.0.1` rather than left unversioned or guessed at
   more precisely.

This is **best-effort**, not authoritative history — a few placements (noted below) had no clean
CHANGELOG match and were resolved by nearest-date tie-break rather than a confirmed content match.
Corrections are welcome; this file exists so a mistake can be found and fixed rather than silently
trusted.

## Low-confidence placements (no explicit CHANGELOG content match, resolved by date proximity)

- `v0.2.1/042-lift-dev-prod-concurrency-ban` — infra/ops change, dated 2026-08-05 (same day as
  both `0.2.0` and `0.2.1`); no changelog line names it specifically.
- `v0.3.0/bugfix-026-morning-documents-created-unsigned.md` — dated 2026-08-07 (same day as both
  `0.2.3` and `0.3.0`); no changelog line names it specifically.
- `v0.4.0/bugfix-037-mixed-timestamp-representation.md` — dated 2026-08-10, between `0.3.0`
  (08-07) and `0.4.0` (08-12); grouped with `bugfix-036` (same window, confirmed match) rather
  than confirmed itself.
- `v0.4.1/bugfix-039-list-invoices-skips-client-resolution.md` and
  `v0.4.1/bugfix-039-artifacts/` — dated 2026-08-12, the exact cut date of `0.4.0`; placed in
  `0.4.1` instead based on thematic proximity to that release's list_invoices-identifier fix, not
  a confirmed date match.
- `v0.4.1/bugfix-028-invoicing-and-approval-gate-p0-cluster/` — dated 2026-08-18 by its
  `specs/done/` move, well after `0.4.3` (08-14) and before `0.5.0` (08-19) by that signal alone;
  **corrected to `v0.4.1` per explicit user instruction (2026-08-20)** overriding the date-based
  placement this methodology would otherwise have produced.

Every other placement matched an explicit, named description in one or both apps' `CHANGELOG.md`
entries for that version.
