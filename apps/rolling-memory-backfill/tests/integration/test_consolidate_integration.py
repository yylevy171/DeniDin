"""Stage 0.5 — session consolidator end-to-end through real Feature 070 components
(non-billed; OpenAI mocked at the network boundary only).

Builds the pre-070 fragmented state (many session dirs per chat, some under
`expired/`), runs `consolidate_sessions.main`, then drives a **real**
`SessionManager` + the real `daily_summary_roll_service` over the result:

- `_reconcile_chat_index` maps each chat to ONE dir — no "maps to N session dirs" WARNING.
- `get_rolling_window` returns the true rolling window across the merged history.
- `assert_message_integrity` holds; Σ messages in == out.
- the real nightly roll produces one `daily_summary` per non-empty (chat, date); a
  second sweep is a no-op.
- every original session dir is preserved byte-identical under `_pre070_raw_<date>/`.
"""
import hashlib
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

import consolidate_sessions as cli
from _denidin_loader import (
    MemoryManager,
    RollMarkerStore,
    collection_name_for_chat,
    local_calendar_date,
    now_local,
)
from src.managers.message_integrity import assert_message_integrity
from src.managers.session_manager import SessionManager
from src.services import daily_summary_roll_service as roll_service

GROUP = "120363210094632983@g.us"
SOLO = "972522968679@c.us"


def _mk_session(sessions_dir: Path, chat: str, session_id: str, msgs, *, expired_date=None):
    sdir = (sessions_dir / "expired" / expired_date / session_id) if expired_date \
        else (sessions_dir / session_id)
    (sdir / "messages").mkdir(parents=True)
    ids = []
    for i, (mid, dt, content) in enumerate(msgs, start=1):
        ids.append(mid)
        rec = {
            "message_id": mid, "session_id": session_id, "role": "godfather",
            "ai_required_role": "user", "content": content, "sender": None,
            "sender_name": "Tester", "recipient": None, "recipient_name": None,
            "timestamp": dt.isoformat(), "received_at": dt.isoformat(),
            "was_received": True, "order_num": i, "image_path": None,
            "extracted_text": None, "ledger_event_ids": [],
        }
        (sdir / "messages" / f"{mid}.json").write_text(
            json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    session = {
        "session_id": session_id, "whatsapp_chat": chat, "message_ids": ids,
        "message_counter": len(ids), "created_at": msgs[0][1].isoformat(),
        "last_active": msgs[-1][1].isoformat(), "total_tokens": 0,
        "transferred_to_longterm": True, "storage_path": None, "archived_message_ids": [],
    }
    (sdir / "session.json").write_text(
        json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8")
    return sdir


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    for f in sorted(path.rglob("*")):
        if f.is_file():
            h.update(f.relative_to(path).as_posix().encode())
            h.update(f.read_bytes())
    return h.hexdigest()


@pytest.fixture
def fragmented(tmp_path):
    dr = tmp_path / "data"
    sd = dr / "sessions"
    sd.mkdir(parents=True)
    n = now_local()

    def at(days_ago, hh=9, mm=0):
        return (n - timedelta(days=days_ago)).replace(hour=hh, minute=mm, second=0, microsecond=0)

    # GROUP: 4 fragmented dirs across 25/22/18/(within-window) days ago
    _mk_session(sd, GROUP, "g-25", [("g25a", at(25), "פגישה לפני 25 יום"),
                                    ("g25b", at(25, 9, 5), "המשך")], expired_date=(at(25)).strftime("%Y-%m-%d"))
    _mk_session(sd, GROUP, "g-22", [("g22a", at(22), "לפני 22 יום")], expired_date=(at(22)).strftime("%Y-%m-%d"))
    _mk_session(sd, GROUP, "g-18", [("g18a", at(18), "לפני 18 יום"),
                                    ("g18b", at(18, 10), "עוד הודעה")], expired_date=(at(18)).strftime("%Y-%m-%d"))
    _mk_session(sd, GROUP, "g-now", [("gn1", at(3), "לפני 3 ימים"),
                                     ("gn2", at(1), "אתמול")])
    # SOLO: 3 fragmented dirs
    _mk_session(sd, SOLO, "s-20", [("s20a", at(20), "1:1 לפני 20")], expired_date=(at(20)).strftime("%Y-%m-%d"))
    _mk_session(sd, SOLO, "s-16", [("s16a", at(16), "1:1 לפני 16")], expired_date=(at(16)).strftime("%Y-%m-%d"))
    _mk_session(sd, SOLO, "s-now", [("sn1", at(2), "1:1 שלשום")])
    return SimpleNamespace(data_root=dr, sessions=sd, at=at)


def _reconcile_warnings(sessions_dir, caplog):
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        sm = SessionManager(storage_dir=str(sessions_dir))
    warns = [r.message for r in caplog.records if "maps to" in r.message and "session dirs" in r.message]
    return sm, warns


class TestConsolidationThroughRealSessionManager:
    def test_pre_state_has_the_bug_then_consolidation_fixes_it(self, fragmented, caplog):
        # BEFORE: real SessionManager on the fragmented tree warns for both chats
        _, warns_before = _reconcile_warnings(fragmented.sessions, caplog)
        assert len(warns_before) == 2

        assert cli.main(["--data-root", str(fragmented.data_root)]) == 0

        # AFTER: no multi-dir warning; one canonical session per chat
        sm, warns_after = _reconcile_warnings(fragmented.sessions, caplog)
        assert warns_after == []
        assert set(sm.known_chats()) == {GROUP, SOLO}

        group_sess = sm.get_session(GROUP)
        assert group_sess.storage_path is None
        assert group_sess.message_counter == 7          # 2+1+2+2
        assert group_sess.whatsapp_chat == GROUP
        assert_message_integrity(Path(sm.storage_dir) / group_sess.session_id)

        solo_sess = sm.get_session(SOLO)
        assert solo_sess.message_counter == 3

    def test_rolling_window_spans_the_merged_history(self, fragmented):
        cli.main(["--data-root", str(fragmented.data_root)])
        sm = SessionManager(storage_dir=str(fragmented.sessions))

        # group user turns get the Feature 039 "[sender_name] " prefix
        win14 = sm.get_rolling_window(GROUP, window_days=14)
        assert [m["content"] for m in win14] == ["[Tester] לפני 3 ימים", "[Tester] אתמול"]

        win90 = sm.get_rolling_window(GROUP, window_days=90)
        assert len(win90) == 7                                              # the whole merged history
        assert [m["content"] for m in win90][0] == "[Tester] פגישה לפני 25 יום"    # oldest first
        assert [m["content"] for m in win90][-1] == "[Tester] אתמול"

    def test_originals_preserved_in_raw_archive(self, fragmented):
        raw_name = cli._default_raw_archive_name()
        pre = {}
        for d in list((fragmented.sessions).iterdir()) + list((fragmented.sessions / "expired").rglob("g-*")) \
                + list((fragmented.sessions / "expired").rglob("s-*")):
            if d.is_dir() and (d / "session.json").exists():
                pre[d.name] = _digest(d)

        cli.main(["--data-root", str(fragmented.data_root)])
        raw = fragmented.sessions / raw_name
        post = {d.name: _digest(d) for d in raw.rglob("*") if d.is_dir() and (d / "session.json").exists()}
        for name, dig in pre.items():
            assert post.get(name) == dig, f"{name} changed in the raw archive"


class TestNightlyRollOverConsolidatedData:
    def _global_context(self, data_root, fake_openai_client):
        memory_block = {"session": {"window_days": 14}, "roll": {"hour": 2, "catchup_lookback_days": 40}}
        sm = SessionManager(storage_dir=str(data_root / "sessions"))
        rms = RollMarkerStore(str(data_root / "memory_rolls"))
        mm = MemoryManager(storage_dir=str(data_root / "memory"),
                           embedding_model="text-embedding-3-large", ai_client=fake_openai_client)
        return SimpleNamespace(
            session_manager=sm,
            ai_handler=SimpleNamespace(roll_marker_store=rms, memory_manager=mm,
                                       client=fake_openai_client,
                                       config=SimpleNamespace(ai_model="gpt-5.6-luna", memory=memory_block)),
            config=SimpleNamespace(memory=memory_block),
        ), rms, mm

    def _daily_summaries(self, mm, chat):
        safe = collection_name_for_chat(chat)
        coll = mm.get_or_create_collection(safe)
        got = coll.get(where={"type": {"$eq": "daily_summary"}})
        return got["metadatas"] or []

    def test_startup_sweep_rolls_each_nonempty_pre_window_day_once(self, fragmented, fake_openai_client):
        assert cli.main(["--data-root", str(fragmented.data_root)]) == 0
        gc, rms, mm = self._global_context(fragmented.data_root, fake_openai_client)

        roll_service.run_startup_daily_roll_sweep(gc)

        # the catch-up sweep rolls EVERY past non-empty day within lookback (a day
        # can have a daily_summary AND still be in the 14-day window — the summary
        # is additive; only archival respects the 14-day boundary).
        # GROUP non-empty calendar days: 25, 22, 18, 3, 1 days ago  -> 5
        g_dates = sorted({m["date"] for m in self._daily_summaries(mm, GROUP)})
        assert len(g_dates) == 5, g_dates
        # SOLO non-empty days: 20, 16, 2 days ago  -> 3
        s_dates = sorted({m["date"] for m in self._daily_summaries(mm, SOLO)})
        assert len(s_dates) == 3, s_dates
        assert all(m["source"] == "catch-up" for m in self._daily_summaries(mm, GROUP))

        # second sweep: no new records, all markers already committed
        n_calls_before = len(fake_openai_client._calls["responses"])
        roll_service.run_startup_daily_roll_sweep(gc)
        assert len(fake_openai_client._calls["responses"]) == n_calls_before
        assert len(self._daily_summaries(mm, GROUP)) == 5
