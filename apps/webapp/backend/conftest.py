"""Pytest bootstrap for webapp-backend.

Puts this app's ``src/`` and ``apps/denidin-app/src`` on ``sys.path`` (the latter for reused
managers + ``utils.time_utils``), mirroring morning-mcp-app's ``conftest.py`` shape. Per-test
file logging goes to ``logs/test_logs/{test_file}.log``.
"""
import logging
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

_DENIDIN_APP = PROJECT_ROOT.parents[1] / "denidin-app"
for _p in (_DENIDIN_APP / "src", _DENIDIN_APP):
    if _p.is_dir() and str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


def pytest_runtest_setup(item):
    test_file = Path(item.fspath).stem
    log_path = PROJECT_ROOT / "logs" / "test_logs" / f"{test_file}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    for handler in root.handlers[:]:
        handler.close()
        root.removeHandler(handler)
    file_handler = logging.FileHandler(log_path)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    root.addHandler(file_handler)
    root.setLevel(logging.DEBUG)


@pytest.fixture
def password_salt() -> str:
    return "denidin-pw"


@pytest.fixture
def known_password() -> str:
    return "s3cret-pw"


@pytest.fixture
def password_hash_file(tmp_path, password_salt, known_password) -> Path:
    from webapp_backend.auth import hash_password

    path = tmp_path / "auth" / "password.hash"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(hash_password(known_password, password_salt), encoding="utf-8")
    return path


@pytest.fixture
def app_config(tmp_path, password_hash_file, password_salt):
    from webapp_backend.config import AppConfig

    return AppConfig(
        environment="test",
        password_hash_file=str(password_hash_file),
        denidin_data_root=str(tmp_path / "data"),
        password_salt=password_salt,
        session_expiry_hours=168.0,
    )


@pytest.fixture
def client(app_config):
    from starlette.testclient import TestClient

    from webapp_backend.server import build_app

    with TestClient(build_app(app_config)) as test_client:
        yield test_client
