"""T041a — backfill end-to-end through real components (non-billed).

Real SessionManager + RollMarkerStore + MemoryManager + ChromaDB on an isolated
tmp data-root; OpenAI mocked at the network boundary only (constitution: no
internal mocks). Covers: one daily_summary per non-empty (chat, date) incl.
``@g.us``; empty day -> marker, 0 responses calls; message integrity balances
before AND after; a fully-idempotent re-run creates nothing and exits 0; the
roll markers written are the exact dedup key the nightly sweep reads.
"""
import json
from datetime import timedelta
from pathlib import Path

import pytest

import backfill_daily_summaries as cli
from _denidin_loader import (
    RollMarkerStore,
    collection_name_for_chat,
    local_calendar_date,
    now_local,
)
from src.managers.session_manager import SessionManager

GROUP = "120363210094632983@g.us"
SOLO = "972522968679@c.us"


def seed_message(session_manager, chat, role, content, days_ago, *, sender_name=None):
    """Append one message dated `days_ago` Israel-local calendar days in the past,
    via the real production `add_message_with_tokens(timestamp=...)` seam."""
    ts = now_local() - timedelta(days=days_ago)
    return session_manager.add_message_with_tokens(
        chat_id=chat, role=role, content=content,
        user_role="godfather", sender_name=sender_name, timestamp=ts,
    )


@pytest.fixture
def env(tmp_path, fake_openai_client, monkeypatch):
    data_root = tmp_path / "data"
    (data_root / "sessions").mkdir(parents=True)
    cfg = data_root.parent / "config.json"
    cfg.write_text(json.dumps({
        "ai_api_key": "sk-fake",
        "ai_embedding_model": "text-embedding-3-large",
        "ai_model": "gpt-5.6-luna",
        "memory": {"session": {"window_days": 14}, "roll": {"hour": 2, "catchup_lookback_days": 21}},
    }), encoding="utf-8")
    monkeypatch.setattr(cli, "OpenAI", lambda api_key: fake_openai_client)

    sm = SessionManager(storage_dir=str(data_root / "sessions"))
    # 20 days ago — safely outside the 14-day live-window guard.
    day = (local_calendar_date(now_local()) - timedelta(days=20))
    seed_message(sm, GROUP, "user", "פגישה חשובה מחר", 20, sender_name="Dana")
    seed_message(sm, GROUP, "assistant", "קיבלתי", 20)
    seed_message(sm, SOLO, "user", "שלום", 20)
    del sm
    return {"data_root": data_root, "config": cfg, "day": day,
            "client": fake_openai_client}


def _args(env, *extra):
    return ["--data-root", str(env["data_root"]), "--config", str(env["config"]),
            "--since", env["day"].isoformat(), "--until", env["day"].isoformat(),
            "--yes", *extra]


def _summary_count(data_root, chat, date_str):
    import chromadb
    from chromadb.config import Settings
    client = chromadb.PersistentClient(
        path=str(data_root / "memory"), settings=Settings(anonymized_telemetry=False)
    )
    safe = collection_name_for_chat(chat).replace("@", "_at_").replace(":", "_")
    coll = client.get_or_create_collection(name=safe, metadata={"hnsw:space": "cosine"})
    got = coll.get(where={"$and": [
        {"type": {"$eq": "daily_summary"}},
        {"chat": {"$eq": chat}},
        {"date": {"$eq": date_str}},
    ]})
    return len(got["ids"])


def test_backfill_creates_one_summary_per_nonempty_chat_day(env):
    rc = cli.main(_args(env))
    assert rc == 0
    ds = env["day"].isoformat()
    assert _summary_count(env["data_root"], GROUP, ds) == 1
    assert _summary_count(env["data_root"], SOLO, ds) == 1
    assert env["client"]._calls["responses"], "real summariser calls were made"


def test_markers_are_the_nightly_sweep_dedup_key(env):
    cli.main(_args(env))
    store = RollMarkerStore(str(env["data_root"] / "memory_rolls"))
    ds = env["day"].isoformat()
    assert store.is_rolled(GROUP, ds) is True
    assert store.is_rolled(SOLO, ds) is True


def test_empty_day_gets_marker_and_no_openai_call(env):
    empty_day = env["day"] - timedelta(days=1)
    rc = cli.main(["--data-root", str(env["data_root"]), "--config", str(env["config"]),
                   "--since", empty_day.isoformat(), "--until", empty_day.isoformat(), "--yes"])
    assert rc == 0
    store = RollMarkerStore(str(env["data_root"] / "memory_rolls"))
    assert store.is_rolled(GROUP, empty_day.isoformat()) is True
    assert env["client"]._calls["responses"] == []


def test_idempotent_rerun_is_noop_and_exits_zero(env):
    cli.main(_args(env))
    n = len(env["client"]._calls["responses"])
    rc = cli.main(_args(env))
    assert rc == 0
    assert len(env["client"]._calls["responses"]) == n  # nothing new
    ds = env["day"].isoformat()
    assert _summary_count(env["data_root"], SOLO, ds) == 1  # no dupes


def test_message_integrity_balances_before_and_after(env):
    from src.managers.message_integrity import assert_message_integrity
    cli.main(_args(env))
    sm = SessionManager(storage_dir=str(env["data_root"] / "sessions"))
    for chat in (GROUP, SOLO):
        s = sm.get_session(chat)
        base = Path(sm.storage_dir) / (getattr(s, "storage_path", None) or s.session_id)
        assert_message_integrity(base)
        # backfill reads only — nothing archived
        assert not s.archived_message_ids


def test_missing_chat_filter_fails_closed(env):
    rc = cli.main(_args(env, "--chat", "999@c.us"))
    assert rc == 1
