"""Feature 070 (US5) — logger retention & lossless rotation (T050a).

The pre-070 race (each module its own RotatingFileHandler on the same file,
propagate=False → stale-fd rollover cascades) is designed out: one handler set on
the root logger, TimedRotatingFileHandler(backupCount=0) + gzip, never prunes.

These tests fully isolate the root logger (save/clear/restore) because
`conftest.py`'s per-test hook installs pytest's own root handlers.
"""
import gzip
import logging
import threading
import time
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

import pytest

from denidin_mcp_morning.utils import logger as logmod
from denidin_mcp_morning.utils.logger import (
    _gzip_rotator,
    _our_file_handler,
    get_logger,
    reconfigure_file_rotation,
    setup_logger,
)


@pytest.fixture
def isolated_root():
    """Strip the root logger to bare metal for the test, restore after."""
    root = logging.getLogger()
    saved_handlers = root.handlers[:]
    saved_filters = root.filters[:]
    saved_level = root.level
    root.handlers = []
    root.filters = []
    try:
        yield root
    finally:
        for h in root.handlers[:]:
            h.close()
            root.removeHandler(h)
        root.handlers = saved_handlers
        root.filters = saved_filters
        root.setLevel(saved_level)


def _drain(logger):
    for h in logging.getLogger().handlers:
        h.flush()


def _read_all_segments(logs_dir: Path, stem: str = "morning-mcp.log"):
    """Every line the logger ever wrote: active file + *.gz + any leftover plaintext."""
    lines = []
    active = logs_dir / stem
    if active.exists():
        lines += active.read_text(encoding="utf-8").splitlines()
    for gz in sorted(logs_dir.glob(f"{stem}.*.gz")):
        lines += gzip.decompress(gz.read_bytes()).decode("utf-8").splitlines()
    for pt in sorted(logs_dir.glob(f"{stem}.*")):
        if pt.suffix != ".gz":
            lines += pt.read_text(encoding="utf-8").splitlines()
    return lines


def _our_handlers(root):
    """Only the handlers setup_logger attaches — pytest keeps its own
    LogCaptureHandler / live-log handlers on the root during every test."""
    ours_file = [h for h in root.handlers
                 if isinstance(h, TimedRotatingFileHandler) and h.rotator is _gzip_rotator]
    ours_stream = [h for h in root.handlers if type(h) is logging.StreamHandler]
    return ours_file, ours_stream


class TestRootHandlerModel:
    def test_setup_logger_puts_one_file_and_one_stream_handler_on_root(self, isolated_root, tmp_path):
        for i in range(5):
            setup_logger(f"mod.{i}", logs_dir=str(tmp_path), log_level="INFO")
        ours_file, ours_stream = _our_handlers(isolated_root)
        assert len(ours_file) == 1  # no per-name stacking
        assert len(ours_stream) == 1

    def test_child_logger_has_no_handlers_and_propagates(self, isolated_root, tmp_path):
        child = setup_logger("some.child", logs_dir=str(tmp_path), log_level="INFO")
        assert child.handlers == []
        assert child.propagate is True

    def test_setup_logger_configures_root_file_handler(self, isolated_root, tmp_path):
        assert _our_file_handler(isolated_root) is None
        setup_logger("prod.mod", logs_dir=str(tmp_path), log_level="INFO")
        assert _our_file_handler(isolated_root) is not None

    def test_version_stamp_survives_propagation(self, isolated_root, tmp_path, capsys):
        vf = tmp_path / "VERSION"
        vf.write_text("1.2.3\n")
        child = setup_logger("v.mod", logs_dir=str(tmp_path), log_level="INFO", version_file=vf)
        child.info("hello-version")
        _drain(child)
        content = (tmp_path / "morning-mcp.log").read_text(encoding="utf-8")
        assert "[v1.2.3]" in content and "hello-version" in content


class TestTimedRotationRetention:
    def test_every_rotated_segment_is_gzipped_and_kept(self, isolated_root, tmp_path):
        child = setup_logger("rot.mod", logs_dir=str(tmp_path), log_level="INFO",
                             rotation_when="S", backup_count=0)
        for i in range(4):
            child.info("line %03d %s", i, "x" * 40)
            _drain(child)
            time.sleep(1.05)
        child.info("final line")
        _drain(child)

        gzs = sorted(tmp_path.glob("morning-mcp.log.*.gz"))
        assert len(gzs) >= 3, f"expected >=3 rotated .gz, got {[p.name for p in gzs]}"
        for gz in gzs:
            body = gzip.decompress(gz.read_bytes()).decode("utf-8")
            assert body.strip(), f"{gz.name} decompressed empty"

    def test_backup_count_zero_never_prunes(self, isolated_root, tmp_path):
        child = setup_logger("keep.mod", logs_dir=str(tmp_path), log_level="INFO",
                             rotation_when="S", backup_count=0)
        for i in range(6):
            child.info("keep %d", i)
            _drain(child)
            time.sleep(1.05)
        _drain(child)
        # backupCount=0 → getFilesToDelete returns nothing → all rotations remain
        assert len(list(tmp_path.glob("morning-mcp.log.*"))) >= 4


class TestLosslessRotation:
    """Contract §4: no record emitted during a rollover is dropped."""

    def test_concurrent_emit_across_rotations_loses_nothing(self, isolated_root, tmp_path):
        child = setup_logger("loss.mod", logs_dir=str(tmp_path), log_level="INFO",
                             rotation_when="S", backup_count=0)
        n_threads, per_thread = 4, 60
        emitted = set()
        lock = threading.Lock()

        def worker(base):
            for k in range(per_thread):
                seq = base * 1000 + k
                with lock:
                    emitted.add(seq)
                child.info("SEQ=%d", seq)
                time.sleep(0.01)

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        _drain(child)

        seen = []
        for line in _read_all_segments(tmp_path):
            if "SEQ=" in line:
                seen.append(int(line.split("SEQ=")[1].split()[0]))
        assert sorted(seen) == sorted(emitted), (
            f"lost={sorted(emitted - set(seen))} dupes={len(seen) - len(set(seen))}"
        )
        # and at least one rotation actually happened during the burst
        assert list(tmp_path.glob("morning-mcp.log.*"))

    def test_gzip_rotator_is_fail_safe_when_compression_raises(self, isolated_root, tmp_path, monkeypatch):
        source = tmp_path / "morning-mcp.log.2026-09-01"
        source.write_text("important pre-rotation content\n", encoding="utf-8")
        dest = str(tmp_path / "morning-mcp.log.2026-09-01.gz")

        def boom(*a, **k):
            raise OSError("disk full")

        monkeypatch.setattr(logmod.gzip, "open", boom)
        with pytest.raises(OSError):
            _gzip_rotator(str(source), dest)
        # plaintext segment left intact — never lost
        assert source.exists()
        assert source.read_text(encoding="utf-8") == "important pre-rotation content\n"
        assert not Path(dest).exists() or Path(dest).stat().st_size == 0


class TestReconfigure:
    def test_reconfigure_swaps_the_root_file_handler(self, isolated_root, tmp_path):
        setup_logger("rc.mod", logs_dir=str(tmp_path), log_level="INFO")
        first = _our_file_handler(isolated_root)
        reconfigure_file_rotation("S", 3, logs_dir=str(tmp_path), log_level="INFO")
        second = _our_file_handler(isolated_root)
        assert second is not None and second is not first
        assert second.when == "S"
        assert second.backupCount == 3
        ours_file, _ = _our_handlers(isolated_root)
        assert len(ours_file) == 1  # swapped, not stacked
