"""`assert_message_integrity` — the Feature 070 US3 balance invariant.

For a session directory:

    len(messages/*.json) + len(archived/*.json)
      == session.message_counter
      == len(set(message_ids) | set(archived_message_ids))

i.e. every message ever appended is on disk exactly once (live OR archived,
never both, never neither), and the counter never lies. Nothing is ever
deleted — archiving is a `rename`, so the total file count is conserved.

Lives under ``src/`` (not just ``tests/helpers/``) so the standalone
``apps/rolling-memory-backfill`` pipeline can assert the same invariant
before and after a migration run without duplicating the logic.
"""
import json
from pathlib import Path


def assert_message_integrity(session_dir: Path) -> None:
    session_dir = Path(session_dir)
    data = json.loads((session_dir / "session.json").read_text(encoding="utf-8"))

    live_files = sorted(p.stem for p in (session_dir / "messages").glob("*.json")) \
        if (session_dir / "messages").exists() else []
    arch_files = sorted(p.stem for p in (session_dir / "archived").glob("*.json")) \
        if (session_dir / "archived").exists() else []

    message_ids = list(data.get("message_ids", []))
    archived_ids = list(data.get("archived_message_ids", []))
    counter = data.get("message_counter", 0)

    on_disk = len(live_files) + len(arch_files)
    id_union = set(message_ids) | set(archived_ids)

    assert on_disk == counter, (
        f"file count {on_disk} != message_counter {counter} in {session_dir}"
    )
    assert len(id_union) == counter, (
        f"unique id count {len(id_union)} != message_counter {counter} in {session_dir}"
    )
    assert not (set(message_ids) & set(archived_ids)), (
        f"ids present in BOTH messages/ and archived/ index: "
        f"{set(message_ids) & set(archived_ids)}"
    )
    assert set(live_files) == set(message_ids), (
        f"messages/ files {set(live_files)} != message_ids {set(message_ids)}"
    )
    assert set(arch_files) == set(archived_ids), (
        f"archived/ files {set(arch_files)} != archived_message_ids {set(archived_ids)}"
    )
