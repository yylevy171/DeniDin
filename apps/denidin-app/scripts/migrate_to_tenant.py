#!/usr/bin/env python3
"""
One-off migration script (Feature 055: Multi-Tenancy, REQ-MIGRATE-001).

Migrates an existing single-tenant deployment's `sessions/`, `memory/`, and
`events/` directories (today's flat layout directly under `data_root`) into
the tenant-scoped layout `{data_root}/{tenant_id}/{sessions,memory,events}/`
that `TenantAIHandlerFactory`/`Tenant.data_root` (`src/models/tenant.py`)
expect going forward — see data-model.md's "tenant-scoped data-root layout".

Copy-only, never destructive (shutil.copytree, never move/rmtree) — the
original flat-layout data is left in place untouched, so a bad migration run
can't lose data and this can be safely re-run. Idempotent: a subdirectory
that's already present under the tenant-scoped destination is treated as
"already migrated" and skipped, not re-copied or errored on (shutil.copytree
without `dirs_exist_ok=True` would otherwise raise `FileExistsError` on a
second run). A source subdirectory that doesn't exist (e.g. a fresh install
with no `events/` yet) is skipped without error - not every deployment has
all three.

Usage:
    python3 scripts/migrate_to_tenant.py --data-root dev_data --tenant-id <uuid> --dry-run
    python3 scripts/migrate_to_tenant.py --data-root dev_data --tenant-id <uuid>
"""
import argparse
import shutil
import sys
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).parent.parent))

SUBDIRS = ("sessions", "memory", "events")


def migrate_tenant_data(data_root: Path, tenant_id: str, dry_run: bool = False) -> List[str]:
    """Copies each of SUBDIRS from `data_root` into `data_root/{tenant_id}/...`.

    Returns a human-readable list of actions taken (or, in dry-run mode,
    actions that WOULD be taken) - one entry per subdir, for the caller/CLI
    to print. Never touches the source directories; never raises on a
    missing source subdir or an already-migrated destination subdir.
    """
    data_root = Path(data_root)
    tenant_root = data_root / tenant_id
    actions: List[str] = []

    for subdir in SUBDIRS:
        source = data_root / subdir
        destination = tenant_root / subdir

        if not source.exists():
            actions.append(f"Skipped {subdir}: no source directory at {source}")
            continue

        if destination.exists():
            actions.append(f"Skipped {subdir}: already migrated at {destination}")
            continue

        if dry_run:
            actions.append(f"Would copy {subdir}: {source} -> {destination}")
            continue

        shutil.copytree(source, destination)
        actions.append(f"Copied {subdir}: {source} -> {destination}")

    return actions


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-root", required=True,
        help="Existing flat-layout data root, e.g. dev_data or data",
    )
    parser.add_argument(
        "--tenant-id", required=True,
        help="Tenant id (tenants.json's tenant_id) to migrate this data under",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    data_root = Path(args.data_root)
    if not data_root.exists():
        print(f"ERROR: data root not found: {data_root}", file=sys.stderr)
        sys.exit(2)

    actions = migrate_tenant_data(data_root, args.tenant_id, dry_run=args.dry_run)

    label = "DRY RUN - " if args.dry_run else ""
    print(f"{label}Migration plan for tenant {args.tenant_id!r} under {data_root}:")
    for action in actions:
        print(f"  {action}")


if __name__ == "__main__":
    main()
