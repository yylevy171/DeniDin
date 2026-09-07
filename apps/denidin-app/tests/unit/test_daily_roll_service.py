"""Feature 070 — daily_summary_roll_service (T022a).

Real SessionManager + real RollMarkerStore + real MemoryManager + real ChromaDB;
OpenAI mocked at the network boundary only (constitution: no internal mocks).
Covers: one summary per non-empty (chat, date) incl. @g.us; empty day -> marker,
0 calls; idempotent re-run; downtime catch-up; per-chat isolation on failure;
archived messages still summarised; a date older than catchup_lookback logs and
is not auto-rolled; the archive step runs once per chat per sweep.
"""
import hashlib
from datetime import timedelta
from types import SimpleNamespace

import pytest

from src.managers.memory_manager import MemoryManager
from src.managers.roll_marker_store import RollMarkerStore
from src.managers.session_manager import SessionManager
from src.services import daily_summary_roll_service as svc
from src.utils.time_utils import local_calendar_date, now_local
from tests.helpers.seed import seed_message

GROUP = "120363210094632983@g.us"
SOLO = "972522968679@c.us"


def _vec(text):
    h = hashlib.sha256(text.encode()).digest()
    return [b / 255.0 for b in h[:16]]


class _Embeddings:
    def __init__(self):
        self.fail_for = set()

    def create(self, model, input):
        if any(tok in input for tok in self.fail_for):
            raise RuntimeError("embedding service down")
        return SimpleNamespace(data=[SimpleNamespace(embedding=_vec(input))])


class _Responses:
    def __init__(self, fail_for=None):
        self.calls = []
        self._fail_for = fail_for or set()

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if any(tok in kwargs.get("input", "") for tok in self._fail_for):
            raise RuntimeError("boom")
        # Echo the full transcript so a token in the message content still
        # reaches the summary (and therefore the embedding call).
        return SimpleNamespace(output_text="SUMMARY: " + kwargs["input"])


class _Client:
    def __init__(self, fail_for=None):
        self.responses = _Responses(fail_for)
        self.embeddings = _Embeddings()


@pytest.fixture
def ctx(tmp_path):
    sm = SessionManager(storage_dir=str(tmp_path / "sessions"))
    client = _Client()
    mm = MemoryManager(storage_dir=str(tmp_path / "memory"), embedding_model="x", ai_client=client)
    store = RollMarkerStore(str(tmp_path / "memory_rolls"))
    ai_handler = SimpleNamespace(
        roll_marker_store=store, memory_manager=mm, client=client,
        config=SimpleNamespace(ai_model="gpt-5.6-luna",
                               memory={"session": {"window_days": 14},
                                       "roll": {"hour": 2, "catchup_lookback_days": 21}}),
        memory_enabled=True,
    )
    return SimpleNamespace(session_manager=sm, ai_handler=ai_handler,
                           config=ai_handler.config)


def _summary_count(mm, chat, date_str):
    coll = mm.get_or_create_collection(svc.collection_name_for_chat(chat))
    got = coll.get(where={"$and": [
        {"type": {"$eq": "daily_summary"}}, {"chat": {"$eq": chat}}, {"date": {"$eq": date_str}},
    ]})
    return len(got["ids"])


class TestBasicRoll:
    def test_one_summary_per_nonempty_chat_day_incl_group(self, ctx):
        seed_message(ctx.session_manager, GROUP, "user", "פגישה מחר", 1, sender_name="Dana")
        seed_message(ctx.session_manager, SOLO, "user", "שלום", 1)
        svc._sweep_daily_roll(ctx, now=now_local(), lookback_days=2)
        y = (local_calendar_date(now_local()) - timedelta(days=1)).isoformat()
        assert _summary_count(ctx.ai_handler.memory_manager, GROUP, y) == 1
        assert _summary_count(ctx.ai_handler.memory_manager, SOLO, y) == 1
        assert ctx.ai_handler.client.responses.calls  # real summariser calls made

    def test_daily_summary_is_recallable_with_correct_metadata(self, ctx):
        seed_message(ctx.session_manager, GROUP, "user", "פגישה חשובה מחר בבוקר", 1, sender_name="Dana")
        svc._sweep_daily_roll(ctx, now=now_local(), lookback_days=2)
        y = (local_calendar_date(now_local()) - timedelta(days=1)).isoformat()
        results = ctx.ai_handler.memory_manager.recall(
            query="פגישה", collection_names=[svc.collection_name_for_chat(GROUP)],
            top_k=10, min_similarity=0.0,
        )
        assert results, "the daily summary must be retrievable via recall()"
        md = results[0]["metadata"]
        assert md["type"] == "daily_summary"
        assert md["chat"] == GROUP
        assert md["date"] == y
        assert md["scope"] == "PRIVATE"
        assert md["user_phone"] == GROUP
        assert md["source"] in ("daily-roll", "catch-up", "migration")
        assert md["message_count"] == 1

    def test_group_collection_resolves_without_raw_get_collection(self, ctx):
        # A raw client.get_collection on the unsanitised @g.us name would raise
        # (bugfix-035 H1). The roll path must never do that.
        import chromadb
        seed_message(ctx.session_manager, GROUP, "user", "hi", 1)
        called = {"raw": 0}
        real = chromadb.api.client.Client.get_collection

        def spy(self, name, *a, **k):
            called["raw"] += 1
            return real(self, name, *a, **k)

        chromadb.api.client.Client.get_collection = spy
        try:
            svc._sweep_daily_roll(ctx, now=now_local(), lookback_days=2)
        finally:
            chromadb.api.client.Client.get_collection = real
        y = (local_calendar_date(now_local()) - timedelta(days=1)).isoformat()
        assert _summary_count(ctx.ai_handler.memory_manager, GROUP, y) == 1
        assert called["raw"] == 0  # only get_or_create_collection is used

    def test_empty_day_marker_no_openai_call(self, ctx):
        seed_message(ctx.session_manager, SOLO, "user", "today only", 0)  # nothing yesterday
        svc._sweep_daily_roll(ctx, now=now_local(), lookback_days=2)
        y = (local_calendar_date(now_local()) - timedelta(days=1)).isoformat()
        assert ctx.ai_handler.roll_marker_store.is_rolled(SOLO, y) is True
        assert ctx.ai_handler.client.responses.calls == []

    def test_rerun_over_committed_range_is_a_noop(self, ctx):
        seed_message(ctx.session_manager, SOLO, "user", "hi", 1)
        svc._sweep_daily_roll(ctx, now=now_local(), lookback_days=2)
        n = len(ctx.ai_handler.client.responses.calls)
        svc._sweep_daily_roll(ctx, now=now_local(), lookback_days=2)
        assert len(ctx.ai_handler.client.responses.calls) == n  # 0 new calls
        y = (local_calendar_date(now_local()) - timedelta(days=1)).isoformat()
        assert _summary_count(ctx.ai_handler.memory_manager, SOLO, y) == 1  # 0 dupes


class TestCatchUpAndResilience:
    def test_downtime_catches_up_each_missed_day_once(self, ctx):
        for d in (1, 2, 3):
            seed_message(ctx.session_manager, SOLO, "user", f"day-{d}", d)
        svc.run_startup_daily_roll_sweep(ctx)
        today = local_calendar_date(now_local())
        for d in (1, 2, 3):
            ds = (today - timedelta(days=d)).isoformat()
            assert _summary_count(ctx.ai_handler.memory_manager, SOLO, ds) == 1

    def test_one_poison_chat_never_aborts_the_sweep(self, ctx):
        # An embedding failure (remember() raises) leaves that day un-committed;
        # a summariser failure alone would fall back to a transcript and commit.
        ctx.ai_handler.client.embeddings.fail_for = {"POISON"}
        seed_message(ctx.session_manager, GROUP, "user", "POISON content", 1)
        seed_message(ctx.session_manager, SOLO, "user", "good content", 1)
        svc._sweep_daily_roll(ctx, now=now_local(), lookback_days=2)
        y = (local_calendar_date(now_local()) - timedelta(days=1)).isoformat()
        assert ctx.ai_handler.roll_marker_store.is_rolled(GROUP, y) is False
        assert ctx.ai_handler.roll_marker_store.is_rolled(SOLO, y) is True

    def test_failed_day_retried_on_a_later_sweep(self, ctx):
        ctx.ai_handler.client.embeddings.fail_for = {"flaky"}
        seed_message(ctx.session_manager, SOLO, "user", "flaky day", 1)
        svc._sweep_daily_roll(ctx, now=now_local(), lookback_days=2)
        y = (local_calendar_date(now_local()) - timedelta(days=1)).isoformat()
        assert ctx.ai_handler.roll_marker_store.is_rolled(SOLO, y) is False
        # The next nightly tick is >stale_claim_minutes later - age the claim.
        store = ctx.ai_handler.roll_marker_store
        stale = (now_local() - timedelta(minutes=200)).isoformat()
        store._conn.execute("UPDATE roll_markers SET claimed_at=? WHERE chat=? AND date=?", (stale, SOLO, y))
        store._conn.commit()
        ctx.ai_handler.client.embeddings.fail_for = set()  # embedding service recovers
        svc._sweep_daily_roll(ctx, now=now_local(), lookback_days=2)
        assert store.is_rolled(SOLO, y) is True

    def test_date_older_than_lookback_not_auto_rolled(self, ctx):
        seed_message(ctx.session_manager, SOLO, "user", "way back", 30)
        svc._sweep_daily_roll(ctx, now=now_local(), lookback_days=21)
        old = (local_calendar_date(now_local()) - timedelta(days=30)).isoformat()
        assert ctx.ai_handler.roll_marker_store.is_rolled(SOLO, old) is False


class TestArchiveStep:
    def test_archive_step_runs_once_per_chat_in_the_sweep(self, ctx):
        seed_message(ctx.session_manager, SOLO, "user", "old", 40)
        seed_message(ctx.session_manager, SOLO, "user", "recent", 1)
        svc._sweep_daily_roll(ctx, now=now_local(), lookback_days=2)
        session = ctx.session_manager.get_session(SOLO)
        assert len(session.archived_message_ids) == 1  # the 40-day-old message moved

    def test_archived_message_still_summarised_on_its_day(self, ctx):
        # Message 40 days old: archive it first, then roll THAT day.
        mid = seed_message(ctx.session_manager, SOLO, "user", "archived content", 40)
        ctx.session_manager.archive_aged_and_backstopped_messages(
            ctx.session_manager.get_session(SOLO), window_days=14
        )
        day = (local_calendar_date(now_local()) - timedelta(days=40)).isoformat()
        svc._roll_one_chat_day(ctx, SOLO, local_calendar_date(now_local()) - timedelta(days=40),
                               source="migration", log_prefix="")
        assert _summary_count(ctx.ai_handler.memory_manager, SOLO, day) == 1
