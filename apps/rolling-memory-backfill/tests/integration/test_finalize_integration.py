"""Stage 0.3b — finalize_migration end-to-end through a real SessionManager (no network).

Seeds one consolidated session per chat with messages spanning ~30 days via the
real `add_message_with_tokens(timestamp=...)` seam, then runs
`finalize_migration.main` and asserts:
- `messages/` holds only messages within the last 14 calendar days of `--now`;
  everything older is under `archived/`.
- `message_counter` unchanged; balance invariant holds; nothing deleted.
- idempotent (second run moves 0).
- a chat entirely within 14 days → 0 moves.
- `--report-only` writes nothing.
"""
import json
from datetime import timedelta
from pathlib import Path

import pytest

import finalize_migration as cli
from _denidin_loader import assert_message_integrity, local_calendar_date, now_local
from src.managers.session_manager import SessionManager

GROUP = "120363210094632983@g.us"
SOLO = "972522968679@c.us"


@pytest.fixture
def consolidated(tmp_path):
    dr = tmp_path / "data"
    sessions = dr / "sessions"
    sessions.mkdir(parents=True)
    sm = SessionManager(storage_dir=str(sessions))
    n = now_local()
    # GROUP: messages 30, 20, 16, 13, 5, 1 days ago  -> after finalize, only 13/5/1 stay live
    for d in (30, 20, 16, 13, 5, 1):
        sm.add_message_with_tokens(chat_id=GROUP, role="user", content=f"g-{d}d",
                                   user_role="godfather", sender_name="T", timestamp=n - timedelta(days=d))
    # SOLO: all within 14 days
    for d in (10, 6, 2):
        sm.add_message_with_tokens(chat_id=SOLO, role="user", content=f"s-{d}d",
                                   user_role="godfather", sender_name="T", timestamp=n - timedelta(days=d))
    del sm
    return dr


def _live_archived(sessions_dir: Path, chat: str):
    sm = SessionManager(storage_dir=str(sessions_dir))
    s = sm.get_session(chat)
    sdir = Path(sm.storage_dir) / (s.storage_path or s.session_id)
    live = {json.loads((sdir / "messages" / f"{m}.json").read_text())["content"] for m in s.message_ids}
    arch = {json.loads((sdir / "archived" / f"{m}.json").read_text())["content"] for m in s.archived_message_ids}
    return s, live, arch, sdir


def test_finalize_archives_only_aged_messages(consolidated):
    sessions = consolidated / "sessions"
    rc = cli.main(["--data-root", str(consolidated)])
    assert rc == 0

    s, live, arch, sdir = _live_archived(sessions, GROUP)
    assert live == {"g-13d", "g-5d", "g-1d"}
    assert arch == {"g-30d", "g-20d", "g-16d"}
    assert s.message_counter == 6
    assert_message_integrity(sdir)
    # nothing deleted — every file still on disk
    assert len(list((sdir / "messages").glob("*.json"))) + len(list((sdir / "archived").glob("*.json"))) == 6

    s_solo, live_solo, arch_solo, _ = _live_archived(sessions, SOLO)
    assert arch_solo == set() and len(live_solo) == 3        # all within window -> 0 moves


def test_finalize_is_idempotent(consolidated):
    sessions = consolidated / "sessions"
    assert cli.main(["--data-root", str(consolidated)]) == 0
    _, live1, arch1, _ = _live_archived(sessions, GROUP)
    assert cli.main(["--data-root", str(consolidated)]) == 0
    _, live2, arch2, _ = _live_archived(sessions, GROUP)
    assert (live1, arch1) == (live2, arch2)


def test_report_only_writes_nothing(consolidated, capsys):
    sessions = consolidated / "sessions"
    before = SessionManager(storage_dir=str(sessions)).get_session(GROUP).message_ids[:]
    rc = cli.main(["--data-root", str(consolidated), "--report-only"])
    out = capsys.readouterr().out
    assert rc == 0 and "would move" in out and GROUP in out
    after = SessionManager(storage_dir=str(sessions)).get_session(GROUP).message_ids
    assert after == before                                   # unchanged


def test_now_seam_shifts_the_cutoff(consolidated):
    sessions = consolidated / "sessions"
    # pretend "now" is 10 days in the future -> the 13-days-ago message is now 23 days old -> archived
    future = (now_local() + timedelta(days=10)).isoformat()
    assert cli.main(["--data-root", str(consolidated), "--now", future]) == 0
    _, live, arch, _ = _live_archived(sessions, GROUP)
    # cutoff = (today+10) - 13 = today-3; only the 1-day-ago message stays live
    assert "g-13d" in arch and "g-5d" in arch and live == {"g-1d"}
