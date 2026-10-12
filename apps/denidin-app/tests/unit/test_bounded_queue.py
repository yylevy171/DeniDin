"""Feature 067 (REQ-RMH-025/033/034): BoundedQueue - hard limit, drop, counters, stall."""
import json
import logging
import queue

import pytest

from src.models.config import AppConfiguration
from src.utils.bounded_queue import BoundedQueue, QueueLimitExceeded, QueueSettings


def test_put_and_get_preserve_order():
    q = BoundedQueue("t", 5)
    for i in range(3):
        q.put_or_raise(i)
    assert [q.get_nowait() for _ in range(3)] == [0, 1, 2]


def test_full_queue_raises_drops_and_logs_error(caplog):
    q = BoundedQueue("t", 2)
    q.put_or_raise("a")
    q.put_or_raise("b")
    with caplog.at_level(logging.ERROR):
        with pytest.raises(QueueLimitExceeded):
            q.put_or_raise("c", item_id="msg-3")
    assert q.size() == 2 and q.dropped == 1
    assert any("QUEUE LIMIT EXCEEDED" in r.getMessage() and "msg-3" in r.getMessage() for r in caplog.records)


def test_every_further_put_fails_until_room():
    q = BoundedQueue("t", 1)
    q.put_or_raise("a")
    for _ in range(3):
        with pytest.raises(QueueLimitExceeded):
            q.put_or_raise("x")
    assert q.dropped == 3
    q.get_nowait()
    q.put_or_raise("b")
    assert q.get_nowait() == "b"


def test_get_times_out_with_empty():
    with pytest.raises(queue.Empty):
        BoundedQueue("t", 1).get(timeout=0.01)


def test_high_water_and_warn_size():
    q = BoundedQueue("t", 10, warn_size=3)
    q.put_or_raise(1)
    q.put_or_raise(2)
    assert not q.is_over_warn_size()
    q.put_or_raise(3)
    assert q.is_over_warn_size() and q.high_water == 3


def test_stall_detection_uses_last_progress():
    q = BoundedQueue("t", 5)
    assert not q.is_stalled(1.0)  # empty is never stalled
    q.put_or_raise("a")
    base = q.last_progress_at
    assert not q.is_stalled(30.0, now=base + 5)
    assert q.is_stalled(30.0, now=base + 31)
    q.get_nowait()
    assert not q.is_stalled(30.0, now=base + 1000)


def test_settings_defaults_and_partial_override(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"green_api_instance_id": "x", "green_api_token": "x", "ai_api_key": "x",
                                "message_queues": {"session_max": 7, "stall_seconds": 1}}), encoding="utf-8")
    cfg = AppConfiguration.from_file(str(path))
    settings = QueueSettings.from_config(cfg)
    assert settings.session_max == 7 and settings.stall_seconds == 1
    assert settings.intake_max_per_chat == 50
    assert settings.warn_size(100) == 30


def test_settings_absent_block_gives_defaults():
    class Cfg:
        message_queues = {}
    assert QueueSettings.from_config(Cfg()) == QueueSettings()
