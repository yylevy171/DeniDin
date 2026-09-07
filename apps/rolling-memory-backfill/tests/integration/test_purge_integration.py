"""Stage 0.6 — purge_legacy_summaries end-to-end against a real ChromaDB (no network).

Seeds a per-chat collection with N `session_summary` + M `daily_summary` records
via the real `MemoryManager`, then:
- purge deletes only the `session_summary` / `_fallback` rows; the `daily_summary`
  rows remain and are still recallable.
- the guard refuses a collection with 0 `daily_summary`.
- `--report-only` writes nothing.
"""
from types import SimpleNamespace

import pytest

import purge_legacy_summaries as cli
from _denidin_loader import MemoryManager, collection_name_for_chat

GROUP = "120363210094632983@g.us"
SOLO = "972522968679@c.us"


@pytest.fixture
def fake_ai():
    def emb_create(model, input):  # noqa: A002 - OpenAI kwarg name
        vec = [float((sum(bytearray(str(input).encode())) % 97) + i) for i in range(16)]
        return SimpleNamespace(data=[SimpleNamespace(embedding=vec)])
    return SimpleNamespace(embeddings=SimpleNamespace(create=emb_create))


@pytest.fixture
def seeded(tmp_path, fake_ai):
    dr = tmp_path / "data"
    (dr / "memory").mkdir(parents=True)
    mm = MemoryManager(storage_dir=str(dr / "memory"),
                       embedding_model="text-embedding-3-large", ai_client=fake_ai)
    for i in range(7):
        mm.remember(f"legacy session summary {i}", collection_name_for_chat(GROUP),
                    metadata={"type": "session_summary", "chat": GROUP, "scope": "PRIVATE"})
    mm.remember("legacy fallback", collection_name_for_chat(GROUP),
                metadata={"type": "session_summary_fallback", "chat": GROUP, "scope": "PRIVATE"})
    for d in ("2026-08-10", "2026-08-11"):
        mm.remember(f"clean daily summary {d}", collection_name_for_chat(GROUP),
                    metadata={"type": "daily_summary", "chat": GROUP, "date": d, "scope": "PRIVATE"})
    # SOLO: only legacy, no daily_summary -> guard must refuse
    for i in range(3):
        mm.remember(f"solo legacy {i}", collection_name_for_chat(SOLO),
                    metadata={"type": "session_summary", "chat": SOLO, "scope": "PRIVATE"})
    del mm
    return dr, fake_ai


def _counts(dr, fake_ai, chat):
    mm = MemoryManager(storage_dir=str(dr / "memory"),
                       embedding_model="text-embedding-3-large", ai_client=fake_ai)
    coll = mm.get_or_create_collection(collection_name_for_chat(chat))
    all_meta = coll.get().get("metadatas") or []
    by_type = {}
    for m in all_meta:
        by_type[m.get("type")] = by_type.get(m.get("type"), 0) + 1
    return by_type


def test_purge_deletes_only_legacy_records(seeded):
    dr, fake_ai = seeded
    rc = cli.main(["--data-root", str(dr), "--chat", GROUP])
    assert rc == 0
    after = _counts(dr, fake_ai, GROUP)
    assert after.get("session_summary", 0) == 0
    assert after.get("session_summary_fallback", 0) == 0
    assert after.get("daily_summary") == 2


def test_daily_summaries_still_recallable_after_purge(seeded):
    dr, fake_ai = seeded
    cli.main(["--data-root", str(dr), "--chat", GROUP])
    mm = MemoryManager(storage_dir=str(dr / "memory"),
                       embedding_model="text-embedding-3-large", ai_client=fake_ai)
    hits = mm.recall(query="daily summary", collection_names=[collection_name_for_chat(GROUP)], top_k=5)
    assert hits and all(h.get("metadata", {}).get("type", "daily_summary") == "daily_summary"
                        for h in hits if h.get("metadata"))


def test_guard_refuses_collection_without_daily_summary(seeded, capsys):
    dr, fake_ai = seeded
    rc = cli.main(["--data-root", str(dr), "--chat", SOLO])
    assert rc == 1 and "backfill first" in capsys.readouterr().err
    assert _counts(dr, fake_ai, SOLO).get("session_summary") == 3       # nothing deleted


def test_report_only_writes_nothing(seeded, capsys):
    dr, fake_ai = seeded
    before = _counts(dr, fake_ai, GROUP)
    rc = cli.main(["--data-root", str(dr), "--chat", GROUP, "--report-only"])
    out = capsys.readouterr().out
    assert rc == 0 and "would be deleted" in out
    assert _counts(dr, fake_ai, GROUP) == before


def test_default_targets_all_nonreserved_collections_but_guard_stops_solo(seeded, capsys):
    dr, _fake = seeded
    rc = cli.main(["--data-root", str(dr)])           # no --chat
    # SOLO has no daily_summary -> whole run fails closed (order-independent: at least one bad)
    assert rc == 1 and "backfill first" in capsys.readouterr().err
