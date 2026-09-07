"""T090a — AC-4: the backfill run against **real OpenAI** (billed).

The real-money twin of the non-billed ``tests/integration/test_backfill_integration.py``
(T041a), which already locks the mechanics with the OpenAI boundary mocked. This
file proves the same end-to-end flow with real ``responses.create`` +
``embeddings.create`` calls (the exact nightly-roll summariser path), and that:

  * one real ``daily_summary`` per non-empty pre-window (chat, date), plus a
    marker for every day in range including a fully-empty one;
  * ``source="migration"`` metadata on every backfilled summary;
  * a same-args re-run is a true no-op — **0 new billed calls**, 0 new records;
  * a following real ``daily_summary_roll_service._sweep_daily_roll`` over the
    same range skips every migrated day (0 further billed calls);
  * ``assert_message_integrity`` holds before *and* after, and the raw message
    files are byte-unchanged (backfill reads only — nothing archived);
  * the per-chat operator report is printed for human review.

Run (billed — needs its own fresh explicit go-ahead, same as any billed test):
  apps/denidin-app/scripts/run_single_test.sh \\
    "tests/billed/test_backfill_billed.py::test_backfill_ac4_end_to_end_billed"
(the sub-app's run_single_test.sh is a symlink to denidin-app's.)
"""
import hashlib
import json
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

import backfill_daily_summaries as cli
from _denidin_loader import (
    RollMarkerStore,
    collection_name_for_chat,
    local_calendar_date,
    now_local,
    roll_service,
)
from src.managers.message_integrity import assert_message_integrity
from src.managers.session_manager import SessionManager

pytestmark = pytest.mark.billed

GROUP = "120363070090090090@g.us"
SOLO = "972505550090@c.us"

_DENIDIN_CONFIG = Path(__file__).resolve().parents[3] / "denidin-app" / "config" / "config.dev.json"


def _real_ai_config():
    if not _DENIDIN_CONFIG.is_file():
        pytest.skip(f"{_DENIDIN_CONFIG} not found")
    raw = json.loads(_DENIDIN_CONFIG.read_text(encoding="utf-8"))
    key = raw.get("ai_api_key", "")
    if not key or key.startswith("sk-test") or key.startswith("YOUR"):
        pytest.skip("no real ai_api_key in config/config.dev.json")
    return {
        "ai_api_key": key,
        "ai_embedding_model": raw.get("ai_embedding_model", "text-embedding-3-large"),
        "ai_model": raw.get("ai_model", "gpt-5.6-luna"),
        "memory": {"session": {"window_days": 14}, "roll": {"hour": 2, "catchup_lookback_days": 21}},
    }


def _seed(sm, chat, role, content, days_ago, *, sender_name=None):
    return sm.add_message_with_tokens(
        chat_id=chat, role=role, content=content, user_role="godfather",
        sender_name=sender_name, timestamp=now_local() - timedelta(days=days_ago),
    )


def _summary_ids(data_root, chat, date_str):
    import chromadb
    from chromadb.config import Settings

    client = chromadb.PersistentClient(
        path=str(data_root / "memory"), settings=Settings(anonymized_telemetry=False)
    )
    safe = collection_name_for_chat(chat).replace("@", "_at_").replace(":", "_")
    coll = client.get_or_create_collection(name=safe, metadata={"hnsw:space": "cosine"})
    return coll.get(where={"$and": [
        {"type": {"$eq": "daily_summary"}}, {"chat": {"$eq": chat}}, {"date": {"$eq": date_str}},
    ]})


def _tree_digest(session_dir: Path) -> dict:
    """sha256 of every raw message file under messages/ + archived/, keyed by name."""
    out = {}
    for sub in ("messages", "archived"):
        d = session_dir / sub
        if d.is_dir():
            for f in sorted(d.glob("*.json")):
                out[f"{sub}/{f.name}"] = hashlib.sha256(f.read_bytes()).hexdigest()
    return out


def test_backfill_ac4_end_to_end_billed(tmp_path, capsys):
    ai_cfg = _real_ai_config()
    data_root = tmp_path / "data"
    (data_root / "sessions").mkdir(parents=True)
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(ai_cfg), encoding="utf-8")

    today = local_calendar_date(now_local())
    # Three distinct out-of-window days with content + one fully-empty day between,
    # for two chats (a group and a 1:1). Days: 20, 18, 17 ago have messages; 19 is empty.
    sm = SessionManager(storage_dir=str(data_root / "sessions"))
    _seed(sm, GROUP, "user", "דנה: צריך להכין הצעת מחיר ללקוח החדש עד סוף השבוע.", 20, sender_name="דנה")
    _seed(sm, GROUP, "assistant", "אשלח טיוטה מחר בבוקר.", 20)
    _seed(sm, GROUP, "user", "יוסי: הפגישה עם רואה החשבון נדחתה ליום שלישי.", 18, sender_name="יוסי")
    _seed(sm, SOLO, "user", "תזכיר לי להעביר את המקדמה של 3000 שקל.", 20)
    _seed(sm, SOLO, "user", "שילמתי היום את החשבונית של ספק הענן.", 17)
    del sm

    since = today - timedelta(days=20)
    until = today - timedelta(days=17)
    days = [since + timedelta(days=k) for k in range((until - since).days + 1)]
    chats = [GROUP, SOLO]
    args = ["--data-root", str(data_root), "--config", str(config_path),
            "--since", since.isoformat(), "--until", until.isoformat(), "--yes"]

    # digest the raw message tree up front (backfill must not touch a single byte)
    sm0 = SessionManager(storage_dir=str(data_root / "sessions"))
    before_digests = {
        c: _tree_digest(Path(sm0.storage_dir) / (getattr(s, "storage_path", None) or s.session_id))
        for c in chats for s in [sm0.get_session(c)]
    }
    del sm0

    # --- the real backfill run -------------------------------------------------
    assert cli.main(args) == 0
    report = capsys.readouterr().out
    print(report)  # surfaced for the human operator review (T090a requirement)

    store = RollMarkerStore(str(data_root / "memory_rolls"))
    # every (chat, date) in range has a committed marker — including the empty day
    for c in chats:
        for d in days:
            assert store.is_rolled(c, d.isoformat()), f"no marker for {c} {d}"

    # one real summary per NON-EMPTY (chat, date); none for the empty day (19 ago)
    empty_day = (today - timedelta(days=19)).isoformat()
    nonempty = {
        GROUP: [(today - timedelta(days=20)).isoformat(), (today - timedelta(days=18)).isoformat()],
        SOLO: [(today - timedelta(days=20)).isoformat(), (today - timedelta(days=17)).isoformat()],
    }
    for c, dates_with_content in nonempty.items():
        for ds in dates_with_content:
            got = _summary_ids(data_root, c, ds)
            assert len(got["ids"]) == 1, f"expected 1 summary for {c} {ds}, got {len(got['ids'])}"
            meta = got["metadatas"][0]
            assert meta["source"] == "migration"
            assert meta["type"] == "daily_summary"
            assert meta["chat"] == c and meta["date"] == ds
            assert got["documents"][0].strip(), "summary text is empty"
        assert len(_summary_ids(data_root, c, empty_day)["ids"]) == 0

    # --- idempotent re-run: 0 new records, 0 new billed calls -------------
    first_ids = {(c, ds): set(_summary_ids(data_root, c, ds)["ids"])
                 for c in chats for ds in nonempty[c]}
    assert cli.main(args) == 0
    re_report = capsys.readouterr().out
    assert "billed_calls=0" in re_report, f"re-run made billed calls:\n{re_report}"
    assert "summaries=0" in re_report, f"re-run created summaries:\n{re_report}"
    for (c, ds), ids in first_ids.items():
        assert set(_summary_ids(data_root, c, ds)["ids"]) == ids  # identical, no dupes

    # --- backfill is read-only: integrity holds + raw bytes untouched ----
    sm1 = SessionManager(storage_dir=str(data_root / "sessions"))
    for c in chats:
        s = sm1.get_session(c)
        sdir = Path(sm1.storage_dir) / (getattr(s, "storage_path", None) or s.session_id)
        assert_message_integrity(sdir)
        assert not s.archived_message_ids, "the backfill archived nothing"
        assert _tree_digest(sdir) == before_digests[c], f"raw message bytes changed for {c}"
    del sm1

    # --- a following real nightly sweep skips every migrated day ----------
    # (the sweep's own archive step DOES move these out-of-window files into
    # archived/, so we assert on the roll — no re-summarise — not on file paths.)
    from src.managers.memory_manager import MemoryManager
    from openai import OpenAI

    session_manager = SessionManager(storage_dir=str(data_root / "sessions"))
    roll_marker_store = RollMarkerStore(str(data_root / "memory_rolls"))
    mem = MemoryManager(
        storage_dir=str(data_root / "memory"),
        embedding_model=ai_cfg["ai_embedding_model"],
        ai_client=OpenAI(api_key=ai_cfg["ai_api_key"]),
    )
    ctx = SimpleNamespace(
        session_manager=session_manager,
        ai_handler=SimpleNamespace(
            roll_marker_store=roll_marker_store, memory_manager=mem,
            client=OpenAI(api_key=ai_cfg["ai_api_key"]),
            config=SimpleNamespace(ai_model=ai_cfg["ai_model"], memory=ai_cfg["memory"]),
        ),
        config=SimpleNamespace(memory=ai_cfg["memory"]),
    )
    roll_service._sweep_daily_roll(ctx, now=now_local(), lookback_days=21, log_prefix="[TEST] ")
    for c in chats:
        for ds in nonempty[c]:
            assert len(_summary_ids(data_root, c, ds)["ids"]) == 1  # still exactly one — not re-rolled
        s = session_manager.get_session(c)
        sdir = Path(session_manager.storage_dir) / (getattr(s, "storage_path", None) or s.session_id)
        assert_message_integrity(sdir)  # balance invariant survives the archive move
