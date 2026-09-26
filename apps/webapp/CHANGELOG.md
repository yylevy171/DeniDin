# Changelog

One entry per release, newest first. Written only by `scripts/cut_release.sh` — never hand-edited
(see `specs/done/v0.0.1/034-versioning-release-mgmt/spec.md` REQ-REL-003/REQ-REL-006).

<!-- No release cut yet. Feature 068 (Ledger Web UI) is the first; VERSION is seeded at 0.5.4
     to align with denidin-app's current version, per the Feature 068 plan. -->

## [0.0.1-webapp] - 2026-09-06

Feature 068 Ledger Web UI — read-only password-gated web UI over LedgerEvent data (backend BFF + frontend SPA). Test-only pre-release from feature/068-ledger-ui-and-reports; not merged to master.

## [0.6.0-f68v2] - 2026-09-07

test

## [0.7.0] - 2026-09-12

Ledger web UI, mandatory client resolution for ledger events, edited/deleted WhatsApp message handling

## [0.7.1] - 2026-09-13

Feature 080: always-on progress updates, typing keep-alive, telemetry plumbing; fixes multi-tool dispatch collision, typing-indicator gap, and rogue-language leak.

## [0.7.3] - 2026-09-14

supporting daily backups

## [0.7.4] - 2026-09-15

Feature 083: Fee agreement document generation over WhatsApp (RBAC-gated get/render/verify/send tools, DocTemplateEngine, Word templates), with RBAC-only gating (no separate feature flag) and no automated page-count check (LibreOffice unavailable in the runtime container - one-page discipline is the model's own judgment).

## [0.7.5] - 2026-09-15

Reconciliation release: combines Feature 083 (fee agreement document generation) with Feature 078 (prod daily backups) and the v0.7.4 fee-agreement-docs cut, which was mistakenly cut from a stale pre-078 branch base and is being superseded.

## [0.7.6] - 2026-09-25

Webapp: new Clients tab (Morning client status dashboard, operator comments, aliasing unmatched ledger names), in-memory caching with refresh-only reloads, correct WhatsApp conversation ordering, no refetch on tab switch (Feature 087). DeniDin: fee-agreement DOCX date/title order and bold party lines (bugfix-063).

## [0.7.7] - 2026-09-26

bugfix-066: config baked into the image is now used as shipped (compose files mount only config.<env>.json; no host copies of the constitution, ledger prompt or fee templates override the release); .dockerignore no longer bakes stray config/log/preview files; launch failures are reported with Docker's error; webapp /health adds Morning connectivity and ledger completeness; webapp index.html is served no-cache.
