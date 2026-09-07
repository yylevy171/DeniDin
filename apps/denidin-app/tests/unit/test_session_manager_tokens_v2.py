"""Feature 070 — no write-time prune + new config values load (T015a).

**Replacement** for the retired `test_session_manager_tokens.py` (the old file
pinned the write-time prune-to-budget behaviour that Feature 070 removes).
Immutable-tests rule: this is a new file, not an edit of an approved one.
"""
import json

import pytest

from src.managers.session_manager import SessionManager
from src.models.config import AppConfiguration

CHAT = "972500000001@c.us"


class TestNoWriteTimePrune:
    def test_appending_far_over_the_role_token_limit_persists_every_message(self, tmp_path):
        sm = SessionManager(storage_dir=str(tmp_path / "sessions"))
        for i in range(200):
            sm.add_message_with_tokens(
                chat_id=CHAT,
                role="user" if i % 2 == 0 else "assistant",
                content=f"message number {i} " + "padding " * 25,
                user_role="client",  # smallest budget (4000) — old code would have pruned
            )

        session = sm.get_session(CHAT)
        assert session.message_counter == 200
        assert len(session.message_ids) == 200
        assert session.archived_message_ids == []

        msg_dir = tmp_path / "sessions" / (session.storage_path or session.session_id) / "messages"
        assert len(list(msg_dir.glob("*.json"))) == 200, "every message must be on disk — no prune"

    def test_a_restart_still_sees_every_message(self, tmp_path):
        sm = SessionManager(storage_dir=str(tmp_path / "sessions"))
        for i in range(120):
            sm.add_message_with_tokens(chat_id=CHAT, role="user", content=f"m{i} " + "x " * 30,
                                       user_role="client")
        sm2 = SessionManager(storage_dir=str(tmp_path / "sessions"))
        reloaded = sm2.get_session(CHAT)
        assert reloaded.message_counter == 120
        assert len(reloaded.message_ids) == 120

    def test_total_tokens_still_tracked_but_never_triggers_a_drop(self, tmp_path):
        sm = SessionManager(storage_dir=str(tmp_path / "sessions"))
        for i in range(50):
            sm.add_message_with_tokens(chat_id=CHAT, role="user", content="word " * 100,
                                       user_role="client")
        session = sm.get_session(CHAT)
        assert session.total_tokens > 4000  # far over the client budget
        assert session.message_counter == 50  # nothing dropped


class TestFeature070ConfigValues:
    def _cfg(self, tmp_path, memory_overrides=None):
        data = {
            "green_api_instance_id": "1234567890", "green_api_token": "abcdef",
            "ai_api_key": "sk-test", "ai_model": "gpt-5.6-luna", "log_level": "INFO",
        }
        # A non-empty `memory` block must be present for the sub-field defaults
        # to apply (pre-Feature-070 behaviour); real config files always have one.
        data["memory"] = memory_overrides if memory_overrides is not None else {"session": {}}
        p = tmp_path / "config.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        return AppConfiguration.from_file(str(p))

    def test_defaults_are_injected_for_a_bare_config(self, tmp_path):
        cfg = self._cfg(tmp_path)
        assert cfg.memory["session"]["window_days"] == 14
        assert cfg.memory["longterm"]["daily_summary_top_k"] == 10
        assert cfg.memory["archive_retention_days"] == 0
        assert cfg.memory["roll"] == {"hour": 2, "catchup_lookback_days": 21, "stale_claim_minutes": 120}

    def test_operator_overrides_survive(self, tmp_path):
        cfg = self._cfg(tmp_path, {"session": {"window_days": 7}, "roll": {"hour": 3}})
        assert cfg.memory["session"]["window_days"] == 7
        assert cfg.memory["roll"]["hour"] == 3
        # untouched sub-keys still get their defaults
        assert cfg.memory["roll"]["catchup_lookback_days"] == 21

    @pytest.mark.parametrize("bad", [0, -1, "x", True])
    def test_invalid_window_days_is_rejected(self, tmp_path, bad):
        cfg = self._cfg(tmp_path, {"session": {"window_days": bad}})
        with pytest.raises(ValueError):
            cfg.validate()
