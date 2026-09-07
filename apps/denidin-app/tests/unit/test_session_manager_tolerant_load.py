"""Feature 070 — tolerant session load (T011a), bugfix-035 H2.

_session_from_dict drops unknown top-level keys with exactly one WARNING (not
ERROR, not per-load), the session stays fully usable, and a legacy message dict
missing content/role is read via .get(...) without KeyError.
"""
import json

import pytest

from src.managers.session_manager import SessionManager
from tests.helpers.seed import seed_message

CHAT = "972522968679@c.us"


@pytest.fixture
def sm(tmp_path):
    return SessionManager(storage_dir=str(tmp_path / "sessions"))


def _poison(session_dir, **extra_keys):
    f = session_dir / "session.json"
    data = json.loads(f.read_text())
    data.update(extra_keys)
    f.write_text(json.dumps(data))


class TestUnknownKeyTolerated:
    def test_unknown_key_dropped_one_warning_session_usable(self, sm, tmp_path, caplog):
        seed_message(sm, CHAT, "user", "hi", 1)
        session = sm.get_session(CHAT)
        sdir = sm.storage_dir / (session.storage_path or session.session_id)
        _poison(sdir, pending_ledger_events=[])  # the real 0f5eaa04 shape

        fresh = SessionManager(storage_dir=str(sm.storage_dir))
        with caplog.at_level("WARNING"):
            reloaded = fresh.get_session(CHAT)
        assert reloaded.session_id == session.session_id
        assert len(reloaded.message_ids) == 1
        warnings = [r for r in caplog.records if r.levelname == "WARNING"]
        assert len(warnings) >= 1
        assert not any(r.levelname == "ERROR" for r in caplog.records)
        # still usable
        seed_message(fresh, CHAT, "user", "again", 0)
        assert len(fresh.get_session(CHAT).message_ids) == 2

    def test_second_unknown_key_also_tolerated_not_an_allowlist(self, sm):
        seed_message(sm, CHAT, "user", "hi", 1)
        session = sm.get_session(CHAT)
        sdir = sm.storage_dir / (session.storage_path or session.session_id)
        _poison(sdir, some_future_field=42, another_one={"x": 1})
        fresh = SessionManager(storage_dir=str(sm.storage_dir))
        assert fresh.get_session(CHAT).session_id == session.session_id


class TestLegacyMessageDict:
    def test_message_missing_content_and_role_no_keyerror(self, sm):
        mid = seed_message(sm, CHAT, "user", "real", 1)
        session = sm.get_session(CHAT)
        sdir = sm.storage_dir / (session.storage_path or session.session_id)
        mf = sdir / "messages" / f"{mid}.json"
        data = json.loads(mf.read_text())
        data.pop("content", None)
        data.pop("role", None)
        data.pop("ai_required_role", None)
        mf.write_text(json.dumps(data))
        # must not raise
        window = sm.get_rolling_window(CHAT, window_days=14)
        assert window and window[0]["content"] == ""
        assert window[0]["role"] == "user"
