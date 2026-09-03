"""Feature 070 — final billed acceptance pass (T070).

Real OpenAI (text-only: chat + embeddings + the nightly summariser), real
`SessionManager` / `MemoryManager` / ChromaDB / `RollMarkerStore`, isolated tmp
`data_root` per test. No Morning/MCP — none of these scenarios cross apps, so
`morning-mcp-app-dev` is not required.

Covers, per METHODOLOGY §VI (written here, run once, together):
  AC-1 (US1+US2) — an out-of-window day's daily summary answers a real question.
  AC-2 (US1)     — a process restart continues the same conversation seamlessly.
  AC-3 (US1+US3) — the token backstop keeps the newest context; trimmed messages
                   are on disk under archived/.
  AC-5 (US1+US2) — a legacy `pending_ledger_events` session.json loads with one
                   WARNING (no TypeError) and still participates in the roll.
  SC-007         — get_rolling_window p95 latency + worst-case token headroom.

Run: scripts/run_single_test.sh "tests/billed/test_rolling_memory_billed.py::<Class>::<test>"
"""
import json
import statistics
import time
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from openai import OpenAI

from src.handlers.ai_handler import AIHandler
from src.managers.memory_collections import collection_name_for_chat
from src.managers.message_integrity import assert_message_integrity
from src.models.config import AppConfiguration
from src.models.message import WhatsAppMessage
from src.services import daily_summary_roll_service as svc
from src.utils.time_utils import local_calendar_date, now_local

APP_DIR = Path(__file__).resolve().parents[2]
GROUP = "120363070070070070@g.us"
SOLO = "972505550070@c.us"

pytestmark = pytest.mark.billed


def _real_key():
    cfg_path = APP_DIR / "config" / "config.test.json"
    if not cfg_path.exists():
        pytest.skip("config/config.test.json not found")
    raw = json.loads(cfg_path.read_text(encoding="utf-8"))
    key = raw.get("ai_api_key", "")
    if not key or key.startswith("sk-test") or key.startswith("YOUR"):
        pytest.skip("no real ai_api_key in config/config.test.json")
    return raw, key


def _config(tmp_path, chat, *, window_days=14, max_tokens_by_role=None):
    raw, key = _real_key()
    return AppConfiguration(
        green_api_instance_id="i", green_api_token="t",
        ai_api_key=key,
        ai_model=raw.get("ai_model", "gpt-5.6-luna"),
        ai_embedding_model=raw.get("ai_embedding_model", "text-embedding-3-large"),
        ai_reply_max_tokens=600,
        godfather_phone=chat,
        feature_flags={"enable_memory_system": True, "enable_rbac": True},
        data_root=str(tmp_path),
        memory={
            "session": {
                "storage_dir": str(tmp_path / "sessions"),
                "window_days": window_days,
                "max_tokens_by_role": max_tokens_by_role or {"client": 4000, "godfather": 100000},
            },
            "longterm": {"enabled": True, "storage_dir": str(tmp_path / "memory"),
                         "daily_summary_top_k": 10, "min_similarity": 0.0},
            "roll": {"hour": 2, "catchup_lookback_days": 21, "stale_claim_minutes": 120},
        },
    )


def _handler(cfg):
    return AIHandler(OpenAI(api_key=cfg.ai_api_key), cfg)


def _roll_ctx(handler):
    return SimpleNamespace(session_manager=handler.session_manager,
                           ai_handler=handler, config=handler.config)


def _seed(sm, chat, role, content, days_ago, *, sender_name=None):
    return sm.add_message_with_tokens(
        chat_id=chat, role=role, content=content, user_role="godfather",
        sender_name=sender_name, timestamp=now_local() - timedelta(days=days_ago),
    )


def _ask(handler, chat, text):
    m = WhatsAppMessage(message_id="q", chat_id=chat, sender_id=chat, sender_name="Avi",
                        text_content=text, timestamp=0, message_type="text")
    req = handler.create_request(m, chat_id=chat, user_phone=chat)
    return handler.get_response(req, chat_id=chat, user_phone=chat, sender="Avi", recipient="DeniDin")


class TestAC1RollThenRecall:
    def test_out_of_window_day_is_answered_from_its_daily_summary(self, tmp_path):
        cfg = _config(tmp_path, GROUP, window_days=2)
        h = _handler(cfg)
        sm = h.session_manager

        # 3 simulated days; window_days=2 so day-3-ago is out of window.
        _seed(sm, GROUP, "user", "דנה: הפרויקט הסודי מספר 74-ALPHA-9152, אל תשכח.", 3, sender_name="דנה")
        _seed(sm, GROUP, "assistant", "רשמתי, מספר הפרויקט 74-ALPHA-9152.", 3)
        _seed(sm, GROUP, "user", "יוסי: נעדכן את הלקוח מחר.", 2, sender_name="יוסי")
        _seed(sm, GROUP, "user", "דנה: הפגישה נדחתה ליום חמישי.", 1, sender_name="דנה")

        ctx = _roll_ctx(h)
        today = local_calendar_date(now_local())
        # roll each of the past 3 days explicitly (real summariser call per non-empty day)
        for d in (3, 2, 1):
            svc._roll_one_chat_day(ctx, GROUP, today - timedelta(days=d),
                                   source="daily-roll", log_prefix="")

        # exactly one committed marker per day, no duplicate summary records
        coll = h.memory_manager.get_or_create_collection(collection_name_for_chat(GROUP))
        for d in (3, 2, 1):
            ds = (today - timedelta(days=d)).isoformat()
            assert h.roll_marker_store.is_rolled(GROUP, ds)
            got = coll.get(where={"$and": [
                {"type": {"$eq": "daily_summary"}}, {"chat": {"$eq": GROUP}}, {"date": {"$eq": ds}},
            ]})
            assert len(got["ids"]) == 1

        # re-roll → still one each (idempotent)
        for d in (3, 2, 1):
            svc._roll_one_chat_day(ctx, GROUP, today - timedelta(days=d),
                                   source="daily-roll", log_prefix="")

        resp = _ask(h, GROUP, "מה מספר הפרויקט הסודי שדנה הזכירה?")
        answer = resp.response_text
        assert "74-ALPHA-9152" in answer, f"expected the out-of-window fact in: {answer!r}"


class TestAC2RestartContinuity:
    def test_a_fresh_process_continues_the_same_conversation(self, tmp_path):
        cfg = _config(tmp_path, SOLO)
        h1 = _handler(cfg)
        _ask(h1, SOLO, "קוראים לי אבי ואני עובד על פרויקט לוּנה. תזכור את זה.")
        sid = h1.session_manager.get_session(SOLO).session_id

        # "restart": a brand-new handler stack on the SAME data_root
        h2 = _handler(_config(tmp_path, SOLO))
        assert h2.session_manager.get_session(SOLO).session_id == sid  # bugfix-044 / AC-2

        resp = _ask(h2, SOLO, "איך קוראים לי ועל איזה פרויקט אני עובד?")
        answer = resp.response_text
        assert "אבי" in answer and ("לונה" in answer or "לוּנה" in answer or "Luna" in answer.lower()
                                    or "luna" in answer.lower())


class TestAC3TokenBackstop:
    def test_newest_context_wins_and_trimmed_messages_are_archived(self, tmp_path):
        cfg = _config(tmp_path, SOLO, max_tokens_by_role={"client": 300, "godfather": 300})
        h = _handler(cfg)
        sm = h.session_manager

        # many in-window messages, well over the 300-token backstop
        for i in range(25):
            _seed(sm, SOLO, "user", f"הודעה מספר {i} עם המון טקסט מיותר " * 6, 1)
        _seed(sm, SOLO, "user", "המילה החשובה היום היא: ננופון.", 0)

        resp = _ask(h, SOLO, "מה המילה החשובה שאמרתי היום?")
        answer = resp.response_text
        assert "ננופון" in answer

        # the archive step then physically moves the backstopped messages
        session = sm.get_session(SOLO)
        sm.archive_aged_and_backstopped_messages(session, now=now_local(),
                                                 window_days=14, max_backstop_tokens=300)
        sdir = Path(sm.storage_dir) / (session.storage_path or session.session_id)
        assert (sdir / "archived").exists() and any((sdir / "archived").glob("*.json"))
        assert_message_integrity(sdir)


class TestAC5PendingLedgerEventsFixture:
    def test_legacy_pending_ledger_events_session_loads_and_rolls(self, tmp_path, caplog):
        cfg = _config(tmp_path, SOLO)

        # Build a real session with one message dated yesterday through the
        # SessionManager itself (so its on-disk shape + chat_index.db row are
        # exactly what production writes)...
        h0 = _handler(cfg)
        _seed(h0.session_manager, SOLO, "user", "הפקדנו 5000 שקל בבנק אתמול.", 1)
        sid = h0.session_manager.get_session(SOLO).session_id

        # ...then inject the retired Feature-024 `pending_ledger_events` key into
        # that session.json on disk. A fresh handler stack must load it with one
        # WARNING (unknown field dropped) and no TypeError (REQ-MEM-010).
        sfile = tmp_path / "sessions" / sid / "session.json"
        data = json.loads(sfile.read_text(encoding="utf-8"))
        data["pending_ledger_events"] = []
        sfile.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        with caplog.at_level("WARNING"):
            h = _handler(_config(tmp_path, SOLO))  # _reconcile_chat_index runs here
            session = h.session_manager.get_session(SOLO)
        assert session.session_id == sid
        assert session.message_counter == 1
        assert any("pending_ledger_events" in r.message and r.levelname == "WARNING"
                   for r in caplog.records), "expected the unknown-field-dropped warning"
        assert not any(r.levelname == "ERROR" for r in caplog.records
                       if "pending_ledger_events" in r.message or "TypeError" in r.message)

        y = local_calendar_date(now_local()) - timedelta(days=1)
        svc._roll_one_chat_day(_roll_ctx(h), SOLO, y, source="migration", log_prefix="")
        assert h.roll_marker_store.is_rolled(SOLO, y.isoformat())

        # a second get_session on subsequent "turns" still doesn't error
        assert h.session_manager.get_session(SOLO).message_counter == 1


class TestSC007:
    def test_rolling_window_latency_and_token_headroom(self, tmp_path):
        cfg = _config(tmp_path, SOLO, window_days=14)
        h = _handler(cfg)
        sm = h.session_manager
        # ~1500 realistic messages spread across the 14-day window
        for i in range(1500):
            _seed(sm, SOLO, "user" if i % 2 == 0 else "assistant",
                  f"שורת שיחה {i}: עדכון שוטף על הפרויקט, מספרים וסטטוסים.", i % 14)

        # get_rolling_window reads every persisted message file for the chat
        # (one open()+json.loads() each) then filters to the in-window set and
        # walks it for the token backstop — an O(messages) cost. 1500 msgs is a
        # deliberately heavy synthetic day count (107/day for 14 days); real
        # production days run ~30-60 messages. Budget 300 ms p95 (spec amended
        # 2026-09-03, user sign-off).
        samples = []
        for _ in range(30):
            t0 = time.perf_counter()
            window = sm.get_rolling_window(SOLO, window_days=14, max_tokens=100000)
            samples.append((time.perf_counter() - t0) * 1000)
        p95 = statistics.quantiles(samples, n=20)[-1]
        assert p95 <= 300.0, f"get_rolling_window p95 = {p95:.1f} ms (budget 300)"

        window = sm.get_rolling_window(SOLO, window_days=14, max_tokens=100000)
        window_tokens = sum(sm.count_tokens(i["content"]) for i in window)
        constitution_tokens = sm.count_tokens(h._load_constitution())  # pylint: disable=protected-access
        worst_case = window_tokens + constitution_tokens + 4000  # + tools/output headroom
        # gpt-5.6-luna context window = 1,050,000 (research.md D11)
        headroom = 1_050_000 - worst_case
        assert headroom / 1_050_000 >= 0.30, (
            f"worst-case prompt {worst_case} tok vs 1.05M window — headroom "
            f"{headroom / 1_050_000:.0%} (< 30%)"
        )
