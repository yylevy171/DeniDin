# Data Model: Automated Daily Prod Backups (Feature 078)

This feature is operational/infrastructure tooling — it introduces no new application data
model, database table, or persisted domain entity inside `denidin-app`/`morning-mcp-app`. The
"entities" here are filesystem artifacts produced/consumed by the backup scripts.

## Backup Archive

A single `.tgz` file representing one point-in-time, consistent snapshot of prod state.

| Field | Type | Notes |
|---|---|---|
| `filename` | string | `denidin-prod-backup-YYYY-MM-DD.tgz` (REQ-078-03); `YYYY-MM-DD` is the Israel-local calendar date the backup was taken, matching every other date-stamped artifact in this codebase (`now_local()`). |
| `tier` | enum: `daily` \| `monthly` | `daily` for every archive; an archive is additionally copied into the `monthly` tier iff taken on the 1st of the month (REQ-078-06). A monthly-tier copy is byte-identical to its daily-tier sibling, not a separate build. |
| `location` | enum: `windows-host` \| `mac` | Same archive exists in both places once transfer succeeds (REQ-078-05/06); `location` is really "which of the two independent copies," not a property of the archive itself. |
| `contents` | tar entries | Full `data/`, `config/`, `logs/prod/` trees (REQ-078-01), with SQLite files replaced by `.backup`-produced consistent snapshots (see research.md R2) rather than live files. |

## Retention Windows (derived, not persisted)

No new state file/manifest is introduced (see research.md R5) — retention is computed fresh each
run directly from the filename dates of `.tgz` files already present in each tier's folder:

| Tier | Folder (per host) | Keep | Purge rule |
|---|---|---|---|
| Daily | `denidin daily backups/` | last 30 days | delete any `.tgz` whose filename date is > 30 days before today |
| Monthly | `denidin monthly backups/` | last 36 months | delete any `.tgz` whose filename date is > 36 months before today |

## Folder Layout (both hosts)

```text
denidin daily backups/
  denidin-prod-backup-2026-09-14.tgz
  denidin-prod-backup-2026-09-13.tgz
  ...
denidin monthly backups/
  denidin-prod-backup-2026-09-01.tgz
  denidin-prod-backup-2026-08-01.tgz
  ...
```

Exact parent path on each host is a config value (see `contracts/` and `quickstart.md`), not
hardcoded — consistent with CLAUDE.md's "config is code" / no-env-vars conventions applied to
this feature's own new script config.
