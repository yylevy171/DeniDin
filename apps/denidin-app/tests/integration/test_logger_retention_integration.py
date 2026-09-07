"""Feature 070 (US5) — logger retention through the real config path (T052a / AC-6).

Non-billed. This is the standing US5 acceptance evidence (AC-6): logging makes no
OpenAI call, so it runs with the ordinary suite, no separate billed pass.

Covers:
- the `config.logging` block composed by `AppConfiguration` actually reaches
  `setup_logger` / `reconfigure_file_rotation` and shapes the handler;
- under sustained load with a sub-second rotation unit, every rotated segment is
  gzipped, retained (`backup_count=0`), decompresses, and is line-ordered — none lost;
- after the real config-driven reconfigure, the root logger has **exactly one**
  gzip file handler (the pre-070 multi-handler race is designed out);
- `docker/docker-compose.{dev,prod}.yml` declare the `json-file` `max-size`/
  `max-file` cap on both services each.
"""
import gzip
import json
import logging
import threading
import time
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

import pytest

from src.models.config import AppConfiguration
from src.utils.logger import _gzip_rotator, _our_file_handler, reconfigure_file_rotation, setup_logger

APP_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = APP_ROOT.parents[1]


@pytest.fixture
def isolated_root():
    root = logging.getLogger()
    saved_h, saved_f, saved_l = root.handlers[:], root.filters[:], root.level
    root.handlers, root.filters = [], []
    try:
        yield root
    finally:
        for h in root.handlers[:]:
            h.close()
            root.removeHandler(h)
        root.handlers, root.filters = saved_h, saved_f
        root.setLevel(saved_l)


def _config_with_logging(tmp_path, overrides):
    """A real AppConfiguration loaded from a real file — the production path."""
    data = {
        "green_api_instance_id": "1234567890", "green_api_token": "abcdef",
        "ai_api_key": "sk-test", "ai_model": "gpt-5.6-luna", "log_level": "INFO",
    }
    if overrides is not None:
        data["logging"] = overrides
    p = tmp_path / "config.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return AppConfiguration.from_file(str(p))


@pytest.mark.integration
class TestConfigDrivenRetention:
    def test_config_logging_block_gets_safe_defaults(self, tmp_path):
        cfg = _config_with_logging(tmp_path, None)
        assert cfg.logging["rotation_when"] == "midnight"
        assert cfg.logging["backup_count"] == 0

    def test_reconfigure_from_real_config_yields_one_gzip_file_handler(self, isolated_root, tmp_path):
        # module import-time default first (as in production), then the config reconfigure
        setup_logger("boot.mod", logs_dir=str(tmp_path), log_level="INFO")
        cfg = _config_with_logging(tmp_path, {"rotation_when": "S", "backup_count": 0})
        reconfigure_file_rotation(
            rotation_when=cfg.logging["rotation_when"],
            backup_count=cfg.logging["backup_count"],
            logs_dir=str(tmp_path),
            log_level="INFO",
        )
        ours = [h for h in isolated_root.handlers
                if isinstance(h, TimedRotatingFileHandler) and h.rotator is _gzip_rotator]
        assert len(ours) == 1
        assert ours[0].when == "S"
        assert _our_file_handler(isolated_root) is ours[0]

    def test_sustained_load_retains_every_gzipped_segment_ordered(self, isolated_root, tmp_path):
        cfg = _config_with_logging(tmp_path, {"rotation_when": "S", "backup_count": 0})
        child = setup_logger("load.mod", logs_dir=str(tmp_path), log_level="INFO",
                             rotation_when=cfg.logging["rotation_when"],
                             backup_count=cfg.logging["backup_count"])

        seq = 0
        stop = time.time() + 4.0
        while time.time() < stop:
            child.info("N=%06d payload %s", seq, "y" * 60)
            seq += 1
            for h in logging.getLogger().handlers:
                h.flush()
            time.sleep(0.03)
        total = seq

        gzs = sorted(tmp_path.glob("denidin.log.*.gz"))
        assert len(gzs) >= 3, [p.name for p in gzs]

        seen = []
        for gz in gzs:
            body = gzip.decompress(gz.read_bytes()).decode("utf-8")
            nums = [int(l.split("N=")[1].split()[0]) for l in body.splitlines() if "N=" in l]
            assert nums == sorted(nums), f"{gz.name} out of order"
            seen += nums
        active = tmp_path / "denidin.log"
        seen += [int(l.split("N=")[1].split()[0])
                 for l in active.read_text(encoding="utf-8").splitlines() if "N=" in l]

        assert sorted(seen) == list(range(total)), (
            f"lost={sorted(set(range(total)) - set(seen))} dupes={len(seen) - len(set(seen))}"
        )

    def test_lossless_under_concurrency(self, isolated_root, tmp_path):
        child = setup_logger("cc.mod", logs_dir=str(tmp_path), log_level="INFO",
                             rotation_when="S", backup_count=0)
        emitted, lock = set(), threading.Lock()

        def worker(base):
            for k in range(80):
                s = base * 10000 + k
                with lock:
                    emitted.add(s)
                child.info("X=%d", s)
                time.sleep(0.012)

        ts = [threading.Thread(target=worker, args=(b,)) for b in range(5)]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        for h in logging.getLogger().handlers:
            h.flush()

        seen = []
        for p in list(tmp_path.glob("denidin.log*")):
            raw = gzip.decompress(p.read_bytes()) if p.suffix == ".gz" else p.read_bytes()
            seen += [int(l.split("X=")[1].split()[0])
                     for l in raw.decode("utf-8").splitlines() if "X=" in l]
        assert sorted(seen) == sorted(emitted), f"lost={sorted(emitted - set(seen))}"


@pytest.mark.integration
class TestTwinCoreIsMirrored:
    """T051b (relaxed per design review): the two logger.py files can't be
    byte-identical (per-app log_filename / log_level defaults / VERSION path /
    reconfigure_package_log_level), but the shared **core** must match exactly."""

    def test_shared_core_region_is_identical(self):
        den = (REPO_ROOT / "apps/denidin-app/src/utils/logger.py").read_text(encoding="utf-8")
        mor = (REPO_ROOT / "apps/morning-mcp-app/src/denidin_mcp_morning/utils/logger.py").read_text(encoding="utf-8")

        def core(text):
            start = text.index("def _gzip_namer(")
            end = text.index("def get_logger(")
            block = text[start:end]
            # documented per-app deltas inside the core region
            block = block.replace("'morning-mcp.log'", "'denidin.log'")
            block = block.replace("log_level: str = 'INFO',  # per-app delta", "log_level: str = 'NOTSET',")
            block = block.replace("'denidin_mcp_morning', logs_dir", "'denidin', logs_dir")
            block = block.replace("(default: 'morning-mcp.log')", "(default: 'denidin.log')")
            return block

        assert core(den) == core(mor)


@pytest.mark.integration
class TestComposeLoggingCap:
    @pytest.mark.parametrize("env", ["dev", "prod"])
    def test_json_file_cap_on_both_services(self, env):
        text = (REPO_ROOT / "docker" / f"docker-compose.{env}.yml").read_text(encoding="utf-8")
        # both denidin-app-<env> and morning-mcp-app-<env>
        assert text.count("driver: json-file") == 2, env
        assert text.count('max-size: "50m"') == 2, env
        assert text.count('max-file: "5"') == 2, env
