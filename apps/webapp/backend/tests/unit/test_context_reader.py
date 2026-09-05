"""Unit tests for webapp_backend.context_reader (Story 3A) — real session files, no mocking."""
import json
from pathlib import Path

import pytest

from webapp_backend.context_reader import ContextReader

BASE = "2026-08-03T19:20:00+00:00"


def _session(root: Path, sid: str, message_ids, archived_day=None):
    if archived_day:
        sdir = root / "sessions" / "expired" / archived_day / sid
    else:
        sdir = root / "sessions" / sid
    (sdir / "messages").mkdir(parents=True)
    (sdir / "session.json").write_text(json.dumps({
        "session_id": sid, "whatsapp_chat": "x@c.us", "message_ids": message_ids,
    }), encoding="utf-8")
    return sdir


def _msg(sdir: Path, mid, role, content, ts, image_path=None):
    (sdir / "messages" / f"{mid}.json").write_text(json.dumps({
        "message_id": mid, "role": role, "content": content, "timestamp": ts,
        "sender": "someone", "image_path": image_path,
    }), encoding="utf-8")


@pytest.fixture
def root(tmp_path):
    return tmp_path


class TestBuildContext:
    def test_happy_path_windows_and_orders_and_sides(self, root):
        sdir = _session(root, "s1", ["m1", "m2", "m3"])
        _msg(sdir, "m1", "user", "hi", "2026-08-03T19:10:00+00:00")       # 10m before anchor
        _msg(sdir, "m2", "assistant", "hello", "2026-08-03T19:15:00+00:00")
        _msg(sdir, "m3", "user", "anchor", "2026-08-03T19:20:00+00:00")   # anchor
        _msg(sdir, "m0", "user", "way before", "2026-08-03T18:00:00+00:00")  # outside 10m

        out = ContextReader(str(root)).build_context("s1", "m3", lookback_minutes=10)
        assert [m["message_id"] for m in out["messages"]] == ["m1", "m2", "m3"]
        assert [m["side"] for m in out["messages"]] == ["right", "left", "right"]
        assert out["lookback_minutes_used"] == 10

    def test_boundary_message_is_inclusive(self, root):
        sdir = _session(root, "s1", ["m1", "m2"])
        _msg(sdir, "m1", "user", "exactly 10m before", "2026-08-03T19:10:00+00:00")
        _msg(sdir, "m2", "user", "anchor", "2026-08-03T19:20:00+00:00")
        out = ContextReader(str(root)).build_context("s1", "m2", 10)
        assert [m["message_id"] for m in out["messages"]] == ["m1", "m2"]

    def test_lookback_clamped_to_60(self, root):
        sdir = _session(root, "s1", ["m1"])
        _msg(sdir, "m1", "user", "a", BASE)
        assert ContextReader(str(root)).build_context("s1", "m1", 999)["lookback_minutes_used"] == 60
        assert ContextReader(str(root)).build_context("s1", "m1", -5)["lookback_minutes_used"] == 0

    def test_archived_session_is_found(self, root):
        sdir = _session(root, "s9", ["m1"], archived_day="2026-08-03")
        _msg(sdir, "m1", "user", "a", BASE)
        out = ContextReader(str(root)).build_context("s9", "m1", 10)
        assert out["messages"][0]["message_id"] == "m1"

    def test_missing_session_is_context_unavailable(self, root):
        out = ContextReader(str(root)).build_context("ghost", "m1", 10)
        assert out["error"] == "context_unavailable"

    def test_missing_anchor_message_is_context_unavailable(self, root):
        sdir = _session(root, "s1", ["m1"])
        _msg(sdir, "m1", "user", "a", BASE)
        out = ContextReader(str(root)).build_context("s1", "no-such-msg", 10)
        assert out["error"] == "context_unavailable"

    def test_image_message_gets_media_url_token(self, root):
        (root / "media").mkdir()
        (root / "media" / "pic.jpg").write_bytes(b"\xff\xd8\xff")
        sdir = _session(root, "s1", ["m1"])
        _msg(sdir, "m1", "user", "look", BASE, image_path="media/pic.jpg")
        reader = ContextReader(str(root))
        out = reader.build_context("s1", "m1", 10)
        url = out["messages"][0]["media_url"]
        assert url.startswith("/api/media/")
        assert reader.resolve_media(url.rsplit("/", 1)[1]) == (root / "media" / "pic.jpg")

    def test_image_path_pointing_at_missing_file_yields_no_media_url(self, root):
        sdir = _session(root, "s1", ["m1"])
        _msg(sdir, "m1", "user", "x", BASE, image_path="media/gone.jpg")
        out = ContextReader(str(root)).build_context("s1", "m1", 10)
        assert "media_url" not in out["messages"][0]


class TestResolveMedia:
    def test_unknown_token_returns_none(self, root):
        assert ContextReader(str(root)).resolve_media("nope") is None

    def test_traversal_path_never_mints_a_token(self, root):
        (root / "media").mkdir()
        sdir = _session(root, "s1", ["m1"])
        _msg(sdir, "m1", "user", "x", BASE, image_path="../../../../etc/passwd")
        out = ContextReader(str(root)).build_context("s1", "m1", 10)
        assert "media_url" not in out["messages"][0]
