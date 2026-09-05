#!/usr/bin/env python3
"""
bugfix-035 prod stopgap — mark every stuck session in <sessions>/expired/ as
`transferred_to_longterm: true`, so the pre-070 hourly SessionCleanupThread stops
re-summarising them (real gpt-5.6-luna calls, ~1-2k/day).

Only touches `expired/<YYYY-MM-DD>/<uuid>/session.json`. Never touches `active/`.
Idempotent. Dry-run by default; pass --apply to write. Writes a one-time
`session.json.bak` next to each file it changes (unless --no-backup).

Run with the app STOPPED.

Usage:
    python mark_transferred_to_longterm.py <sessions_dir>            # dry run
    python mark_transferred_to_longterm.py --apply <sessions_dir>   # write
"""
import argparse
import json
import sys
from pathlib import Path


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("sessions_dir", help="the sessions/ directory (the one that contains expired/)")
    p.add_argument("--apply", action="store_true", help="actually write changes (default: dry run)")
    p.add_argument("--no-backup", action="store_true", help="do not write session.json.bak")
    args = p.parse_args(argv)

    sessions_dir = Path(args.sessions_dir)
    expired_base = sessions_dir / "expired"

    if not sessions_dir.is_dir():
        print(f"ERROR: {sessions_dir} is not a directory", file=sys.stderr)
        return 2
    if not expired_base.is_dir():
        print(f"nothing to do: {expired_base} does not exist")
        return 0

    mode = "APPLY" if args.apply else "DRY RUN"
    print(f"=== {mode} === scanning {expired_base}")

    total = already_true = changed = unreadable = 0
    changed_dirs = []

    for date_folder in sorted(expired_base.iterdir()):
        if not date_folder.is_dir():
            continue
        for session_dir in sorted(date_folder.iterdir()):
            if not session_dir.is_dir():
                continue
            sfile = session_dir / "session.json"
            if not sfile.exists():
                continue
            total += 1
            try:
                with open(sfile, encoding="utf-8") as f:
                    data = json.load(f)
            except Exception as e:  # noqa: BLE001
                unreadable += 1
                print(f"  SKIP (unreadable): {date_folder.name}/{session_dir.name}: {e}")
                continue

            if data.get("transferred_to_longterm", False) is True:
                already_true += 1
                continue

            changed += 1
            changed_dirs.append(f"{date_folder.name}/{session_dir.name}")
            if args.apply:
                if not args.no_backup:
                    bak = sfile.with_suffix(".json.bak")
                    if not bak.exists():
                        bak.write_bytes(sfile.read_bytes())
                data["transferred_to_longterm"] = True
                with open(sfile, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

    print()
    print(f"session.json files found : {total}")
    print(f"already transferred=true : {already_true}")
    print(f"unreadable (skipped)     : {unreadable}")
    print(f"{'CHANGED' if args.apply else 'WOULD CHANGE'}          : {changed}")
    for d in changed_dirs:
        print(f"    {d}")
    if not args.apply and changed:
        print("\nre-run with --apply to write these changes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
