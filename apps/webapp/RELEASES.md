# Releases

One longer-form section per release, newest first. Written only by `scripts/cut_release.sh` —
never hand-edited (see `specs/done/v0.0.1/034-versioning-release-mgmt/spec.md` REQ-REL-004/
REQ-REL-006).

<!-- No release cut yet. -->

## webapp v0.0.1-webapp — 2026-09-06

Feature 068 Ledger Web UI — read-only password-gated web UI over LedgerEvent data (backend BFF + frontend SPA). Test-only pre-release from feature/068-ledger-ui-and-reports; not merged to master.

## webapp v0.6.0-f68v2 — 2026-09-07

test

## webapp v0.7.0 — 2026-09-12

Ledger web UI, mandatory client resolution for ledger events, edited/deleted WhatsApp message handling

## webapp v0.7.1 — 2026-09-13

Feature 080: always-on progress updates, typing keep-alive, telemetry plumbing; fixes multi-tool dispatch collision, typing-indicator gap, and rogue-language leak.

## webapp v0.7.3 — 2026-09-14

supporting daily backups

## webapp v0.7.4 — 2026-09-15

Feature 083: Fee agreement document generation over WhatsApp (RBAC-gated get/render/verify/send tools, DocTemplateEngine, Word templates), with RBAC-only gating (no separate feature flag) and no automated page-count check (LibreOffice unavailable in the runtime container - one-page discipline is the model's own judgment).

## webapp v0.7.5 — 2026-09-15

Reconciliation release: combines Feature 083 (fee agreement document generation) with Feature 078 (prod daily backups) and the v0.7.4 fee-agreement-docs cut, which was mistakenly cut from a stale pre-078 branch base and is being superseded.
