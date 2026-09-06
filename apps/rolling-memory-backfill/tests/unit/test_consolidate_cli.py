"""Stage 0.4 — session consolidator CLI contract, preconditions, and merge rules
(non-billed, no network, synthetic tmp session trees).

RED against the `consolidate_sessions.py` stub (its `main` / `_discover_source_sessions`
raise NotImplementedError). GREEN once the merge is implemented per
`specs/done/v0.5.4-70/070-rolling-memory-window/consolidator-spec.md` §1.
"""
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

import consolidate_sessions as cli

GROUP = "120363210094632983@g.us"
SOLO = "972522968679@c.us"

_BASE = datetime(2026, 8, 10, 9, 0, 0)


def _iso(dt: datetime) -> str:
    return dt.isoformat() + "+03:00"


def _mk_session(sessions_dir: Path, chat: str, session_id: str, msgs, *,
                expired_date: str = None, extra_session_fields: dict = None,
                counter: int = None) -> Path:
    """Build a synthetic session dir on disk. `msgs` = list of dicts, each with at
    least {"id", "ts" (datetime|None), "content"}; optional "received_at", "order_num",
    "role". Returns the session dir path."""
    if expired_date:
        sdir = sessions_dir / "expired" / expired_date / session_id
    else:
        sdir = sessions_dir / session_id
    (sdir / "messages").mkdir(parents=True)
    message_ids = []
    for i, m in enumerate(msgs, start=1):
        mid = m["id"]
        message_ids.append(mid)
        rec = {
            "message_id": mid,
            "session_id": session_id,
            "role": m.get("role", "godfather"),
            "ai_required_role": m.get("ai_required_role", "user"),
            "content": m["content"],
            "sender": m.get("sender"),
            "sender_name": m.get("sender_name"),
            "recipient": None,
            "recipient_name": None,
            "timestamp": _iso(m["ts"]) if m.get("ts") is not None else None,
            "received_at": _iso(m["received_at"]) if m.get("received_at") is not None
            else (_iso(m["ts"]) if m.get("ts") is not None else None),
            "was_received": True,
            "order_num": m.get("order_num", i),
            "image_path": None,
            "extracted_text": None,
            "ledger_event_ids": [],
        }
        (sdir / "messages" / f"{mid}.json").write_text(
            json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    session = {
        "session_id": session_id,
        "whatsapp_chat": chat,
        "message_ids": message_ids,
        "message_counter": counter if counter is not None else len(message_ids),
        "created_at": _iso(_BASE),
        "last_active": _iso(_BASE + timedelta(hours=len(msgs))),
        "total_tokens": 0,
        "transferred_to_longterm": False,
        "storage_path": None,
        "archived_message_ids": [],
    }
    if extra_session_fields:
        session.update(extra_session_fields)
    (sdir / "session.json").write_text(
        json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return sdir


def _data_root(tmp_path: Path) -> Path:
    dr = tmp_path / "data"
    (dr / "sessions").mkdir(parents=True)
    return dr


def _canonical(dr: Path, chat: str):
    """Return (session_dict, [message dicts in order]) for the one canonical dir of `chat`."""
    hits = [
        p for p in (dr / "sessions").iterdir()
        if p.is_dir() and not p.name.startswith(cli._RESERVED_DIR_PREFIXES)
        and p.name not in cli._RESERVED_DIR_NAMES
        and (p / "session.json").exists()
        and json.loads((p / "session.json").read_text())["whatsapp_chat"] == chat
    ]
    assert len(hits) == 1, f"expected 1 canonical dir for {chat}, got {[h.name for h in hits]}"
    sdir = hits[0]
    sess = json.loads((sdir / "session.json").read_text())
    msgs = [json.loads((sdir / "messages" / f"{mid}.json").read_text()) for mid in sess["message_ids"]]
    return sess, msgs


# --------------------------------------------------------------------------- #

class TestParser:
    def test_required_data_root(self):
        with pytest.raises(SystemExit):
            cli._build_parser().parse_args([])

    def test_chat_repeatable_and_defaults(self):
        ns = cli._build_parser().parse_args(
            ["--data-root", "d", "--chat", GROUP, "--chat", SOLO]
        )
        assert ns.chat == [GROUP, SOLO]
        assert ns.report_only is False and ns.resume is False and ns.raw_archive_name is None

    def test_default_raw_archive_name_shape(self):
        assert cli._default_raw_archive_name().startswith("_pre070_raw_")
        assert len(cli._default_raw_archive_name()) == len("_pre070_raw_20260101")


class TestPreconditionsFailClosed:
    def _run(self, capsys, *args):
        rc = cli.main(list(args))
        return rc, capsys.readouterr().err

    def test_missing_data_root(self, tmp_path, capsys):
        rc, err = self._run(capsys, "--data-root", str(tmp_path / "nope"))
        assert rc == 1 and "⚠️" in err and "data-root" in err

    def test_data_root_without_sessions(self, tmp_path, capsys):
        dr = tmp_path / "data"
        dr.mkdir()
        rc, err = self._run(capsys, "--data-root", str(dr))
        assert rc == 1 and "sessions" in err

    def test_target_chat_absent(self, tmp_path, capsys):
        dr = _data_root(tmp_path)
        _mk_session(dr / "sessions", GROUP, "g1", [{"id": "m1", "ts": _BASE, "content": "hi"}])
        rc, err = self._run(capsys, "--data-root", str(dr), "--chat", "999@c.us")
        assert rc == 1 and "999@c.us" in err

    def test_canonical_dir_exists_without_resume(self, tmp_path, capsys):
        dr = _data_root(tmp_path)
        _mk_session(dr / "sessions", GROUP, "g1", [{"id": "m1", "ts": _BASE, "content": "a"}], expired_date="2026-08-09")
        _mk_session(dr / "sessions", GROUP, "g2", [{"id": "m2", "ts": _BASE, "content": "b"}])
        assert cli.main(["--data-root", str(dr)]) == 0            # first run consolidates
        rc, err = self._run(capsys, "--data-root", str(dr))       # second run, no --resume
        assert rc == 1 and "resume" in err.lower()

    def test_raw_archive_name_exists_without_resume(self, tmp_path, capsys):
        dr = _data_root(tmp_path)
        _mk_session(dr / "sessions", GROUP, "g1", [{"id": "m1", "ts": _BASE, "content": "a"}])
        (dr / "sessions" / cli._default_raw_archive_name()).mkdir()
        rc, err = self._run(capsys, "--data-root", str(dr))
        assert rc == 1

    def test_unparseable_session_json_aborts(self, tmp_path, capsys):
        dr = _data_root(tmp_path)
        _mk_session(dr / "sessions", GROUP, "g1", [{"id": "m1", "ts": _BASE, "content": "a"}])
        bad = dr / "sessions" / "expired" / "2026-08-09" / "gbad"
        (bad / "messages").mkdir(parents=True)
        (bad / "session.json").write_text("{ not json", encoding="utf-8")
        rc, err = self._run(capsys, "--data-root", str(dr))
        assert rc == 1 and "gbad" in err
        # nothing consolidated
        assert not (dr / "sessions" / cli._default_raw_archive_name()).exists()


class TestMerge:
    def test_n_dirs_to_one_sorted_and_renumbered(self, tmp_path):
        dr = _data_root(tmp_path)
        # three source dirs, timestamps deliberately interleaved across dirs
        _mk_session(dr / "sessions", GROUP, "old2", [
            {"id": "a1", "ts": _BASE + timedelta(days=0, minutes=0), "content": "A1"},
            {"id": "a2", "ts": _BASE + timedelta(days=0, minutes=30), "content": "A2"},
        ], expired_date="2026-08-10")
        _mk_session(dr / "sessions", GROUP, "old1", [
            {"id": "b1", "ts": _BASE + timedelta(days=0, minutes=10), "content": "B1"},
        ], expired_date="2026-08-10")
        _mk_session(dr / "sessions", GROUP, "active", [
            {"id": "c1", "ts": _BASE + timedelta(days=1), "content": "C1"},
            {"id": "c2", "ts": _BASE + timedelta(days=1, minutes=5), "content": "C2"},
        ])
        assert cli.main(["--data-root", str(dr)]) == 0
        sess, msgs = _canonical(dr, GROUP)
        assert [m["content"] for m in msgs] == ["A1", "B1", "A2", "C1", "C2"]
        assert [m["order_num"] for m in msgs] == [1, 2, 3, 4, 5]
        assert sess["message_counter"] == 5
        assert sess["message_ids"] == ["a1", "b1", "a2", "c1", "c2"]
        assert sess["archived_message_ids"] == []
        assert sess["storage_path"] is None
        # canonical id = the source with the greatest message_counter (active: 2, old2: 2 -> tie -> smallest)
        assert sess["session_id"] in ("active", "old2")
        # every message's inner session_id rewritten to the canonical id
        assert all(m["session_id"] == sess["session_id"] for m in msgs)

    def test_canonical_id_is_max_counter_then_lexical(self, tmp_path):
        dr = _data_root(tmp_path)
        _mk_session(dr / "sessions", SOLO, "zzz", [{"id": f"z{i}", "ts": _BASE + timedelta(minutes=i), "content": str(i)} for i in range(5)])
        _mk_session(dr / "sessions", SOLO, "aaa", [{"id": f"a{i}", "ts": _BASE + timedelta(hours=1, minutes=i), "content": str(i)} for i in range(2)], expired_date="2026-08-10")
        assert cli.main(["--data-root", str(dr)]) == 0
        sess, _ = _canonical(dr, SOLO)
        assert sess["session_id"] == "zzz"      # 5 > 2

    def test_duplicate_message_id_kept_once(self, tmp_path, caplog):
        dr = _data_root(tmp_path)
        _mk_session(dr / "sessions", SOLO, "s1", [
            {"id": "dup", "ts": _BASE, "content": "first"},
            {"id": "x1", "ts": _BASE + timedelta(minutes=1), "content": "x"},
        ], expired_date="2026-08-10")
        _mk_session(dr / "sessions", SOLO, "s2", [
            {"id": "dup", "ts": _BASE, "content": "second copy"},
            {"id": "y1", "ts": _BASE + timedelta(minutes=2), "content": "y"},
        ])
        with caplog.at_level("WARNING"):
            assert cli.main(["--data-root", str(dr)]) == 0
        sess, msgs = _canonical(dr, SOLO)
        assert [m["message_id"] for m in msgs].count("dup") == 1
        assert sess["message_counter"] == 3
        assert any("dup" in r.message for r in caplog.records)

    def test_empty_source_dir_skipped_but_archived(self, tmp_path):
        dr = _data_root(tmp_path)
        _mk_session(dr / "sessions", GROUP, "real", [{"id": "m1", "ts": _BASE, "content": "hi"}])
        _mk_session(dr / "sessions", GROUP, "empty", [], expired_date="2026-08-09")
        assert cli.main(["--data-root", str(dr)]) == 0
        sess, msgs = _canonical(dr, GROUP)
        assert sess["message_counter"] == 1
        arch = dr / "sessions" / cli._default_raw_archive_name()
        # both originals preserved under the raw archive
        found = {p.name for p in arch.rglob("session.json")}
        assert (arch / "expired" / "2026-08-09" / "empty" / "session.json").exists()

    def test_missing_timestamp_falls_back_to_received_at(self, tmp_path, caplog):
        dr = _data_root(tmp_path)
        _mk_session(dr / "sessions", SOLO, "s1", [
            {"id": "m1", "ts": None, "received_at": _BASE + timedelta(minutes=1), "content": "no-ts"},
            {"id": "m2", "ts": _BASE + timedelta(minutes=2), "content": "has-ts"},
        ])
        with caplog.at_level("WARNING"):
            assert cli.main(["--data-root", str(dr)]) == 0
        _, msgs = _canonical(dr, SOLO)
        assert [m["content"] for m in msgs] == ["no-ts", "has-ts"]

    def test_legacy_fields_stripped_from_canonical(self, tmp_path):
        dr = _data_root(tmp_path)
        _mk_session(dr / "sessions", SOLO, "s1", [{"id": "m1", "ts": _BASE, "content": "a"}],
                    extra_session_fields={"pending_ledger_events": [], "storage_path": "weird/path",
                                          "session_timeout_hours": 24})
        assert cli.main(["--data-root", str(dr)]) == 0
        sess, _ = _canonical(dr, SOLO)
        assert "pending_ledger_events" not in sess
        assert "session_timeout_hours" not in sess
        assert sess["storage_path"] is None

    def test_originals_preserved_byte_identical(self, tmp_path):
        dr = _data_root(tmp_path)
        s1 = _mk_session(dr / "sessions", GROUP, "g1", [{"id": "m1", "ts": _BASE, "content": "a"}], expired_date="2026-08-09")
        before = (s1 / "session.json").read_bytes(), (s1 / "messages" / "m1.json").read_bytes()
        _mk_session(dr / "sessions", GROUP, "g2", [{"id": "m2", "ts": _BASE + timedelta(hours=1), "content": "b"}])
        assert cli.main(["--data-root", str(dr)]) == 0
        arch = dr / "sessions" / cli._default_raw_archive_name() / "expired" / "2026-08-09" / "g1"
        assert (arch / "session.json").read_bytes() == before[0]
        assert (arch / "messages" / "m1.json").read_bytes() == before[1]

    def test_empty_expired_folders_pruned_after_move(self, tmp_path):
        dr = _data_root(tmp_path)
        _mk_session(dr / "sessions", GROUP, "g1", [{"id": "m1", "ts": _BASE, "content": "a"}], expired_date="2026-08-09")
        _mk_session(dr / "sessions", GROUP, "g2", [{"id": "m2", "ts": _BASE + timedelta(hours=1), "content": "b"}], expired_date="2026-08-10")
        _mk_session(dr / "sessions", SOLO, "s1", [{"id": "s1m", "ts": _BASE, "content": "c"}])
        assert cli.main(["--data-root", str(dr)]) == 0
        # every source dir moved out -> expired/ tree gone entirely
        assert not (dr / "sessions" / "expired").exists()

    def test_integrity_asserted_on_result(self, tmp_path):
        dr = _data_root(tmp_path)
        _mk_session(dr / "sessions", SOLO, "s1", [{"id": f"m{i}", "ts": _BASE + timedelta(minutes=i), "content": str(i)} for i in range(4)])
        assert cli.main(["--data-root", str(dr)]) == 0
        from _denidin_loader import assert_message_integrity
        sdir = [p for p in (dr / "sessions").iterdir()
                if p.is_dir() and not p.name.startswith(cli._RESERVED_DIR_PREFIXES) and (p / "session.json").exists()][0]
        assert_message_integrity(sdir)   # raises on imbalance


class TestReportOnly:
    def test_report_only_writes_nothing(self, tmp_path, capsys):
        dr = _data_root(tmp_path)
        _mk_session(dr / "sessions", GROUP, "g1", [{"id": "m1", "ts": _BASE, "content": "a"}], expired_date="2026-08-09")
        _mk_session(dr / "sessions", GROUP, "g2", [{"id": "m2", "ts": _BASE, "content": "b"}])
        listing_before = sorted(p.name for p in (dr / "sessions").iterdir())
        rc = cli.main(["--data-root", str(dr), "--report-only"])
        out = capsys.readouterr().out
        assert rc == 0
        assert sorted(p.name for p in (dr / "sessions").iterdir()) == listing_before
        assert GROUP in out and "2" in out           # names the chat + source-dir count


class TestResumeAndIdempotency:
    def test_resume_noop_when_nothing_pending(self, tmp_path):
        dr = _data_root(tmp_path)
        _mk_session(dr / "sessions", SOLO, "s1", [{"id": "m1", "ts": _BASE, "content": "a"}], expired_date="2026-08-09")
        _mk_session(dr / "sessions", SOLO, "s2", [{"id": "m2", "ts": _BASE + timedelta(hours=1), "content": "b"}])
        assert cli.main(["--data-root", str(dr)]) == 0
        sess_after_first, _ = _canonical(dr, SOLO)
        assert cli.main(["--data-root", str(dr), "--resume"]) == 0
        sess_after_resume, _ = _canonical(dr, SOLO)
        assert sess_after_resume == sess_after_first        # unchanged

    def test_resume_folds_in_a_leftover_source_dir(self, tmp_path):
        dr = _data_root(tmp_path)
        _mk_session(dr / "sessions", SOLO, "s1", [{"id": "m1", "ts": _BASE, "content": "a"}])
        assert cli.main(["--data-root", str(dr)]) == 0
        # a straggler dir appears (simulating a crash mid-move on the first run)
        _mk_session(dr / "sessions", SOLO, "s2", [{"id": "m2", "ts": _BASE + timedelta(hours=1), "content": "b"}], expired_date="2026-08-11")
        assert cli.main(["--data-root", str(dr), "--resume"]) == 0
        sess, msgs = _canonical(dr, SOLO)
        assert [m["content"] for m in msgs] == ["a", "b"]
        assert sess["message_counter"] == 2
