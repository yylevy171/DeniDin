# MCP → Morning Green Receipt (Feature 005) — Authoritative Folder

This directory (`specs/in-definition/005-mcp-morning-green-receipt/`) is the authoritative location for all Phase‑0 and design artifacts for Feature 005 (MCP → Morning Green Receipt).

Key points
- Canonical artifacts: `spec.md`, `plan.md`, `tasks.md`, `data-model.md`, `contracts/`, `artifacts/`, `quickstart.md`, `webhook_canonicalization.md`, and related files under this folder.
- Naming convention: follow the spec-kit naming pattern (use `spec.md`, `plan.md`, `tasks.md`, `user-stories.md`, etc.). Do not use custom suffixes in filenames for canonical artifacts.
- No environment variables: per repository Constitution, runtime config MUST come from `config/config.json` validated against `specs/in-definition/005-mcp-morning-green-receipt/artifacts/config.schema.json`.

Archive & deprecated copies
- Archived original files (pre-consolidation) were copied to: `specs/archive/005-mcp-morning-green-receipt/`.
- The original folder was moved (safe, reversible) to: `specs/deprecated/005-mcp-morning-green-receipt.orig/`.
- A single-file snapshot of the merged originals is included at: `merged_from_specs_005.md` (for quick reference).

Restoring originals
- To restore archived originals to `/specs/005-mcp-morning-green-receipt/` run (from repo root):

```bash
mv specs/deprecated/005-mcp-morning-green-receipt.orig specs/005-mcp-morning-green-receipt
git add specs/005-mcp-morning-green-receipt
git commit -m "Restore archived specs/005 folder"
```

Automation notes
- The repository prerequisite checker (`.specify/scripts/bash/check-prerequisites.sh`) was updated to accept `specs/in-definition/` as a fallback source. CI and tooling should now prefer the `in-definition` path.
- If you add new artifacts for this feature, place them in this folder and follow the spec-kit naming conventions.

If you want, I can (A) remove `merged_from_specs_005.md` to reduce duplication, or (B) add a short CI check that enforces single-authoritative-folder rules for future PRs.
