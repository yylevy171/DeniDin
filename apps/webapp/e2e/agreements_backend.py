"""Feature 089 e2e launcher: the REAL webapp backend app, with the official client list injected
(dependency injection, as the backend's own integration tests do) so the suite needs no Morning
sandbox. Everything else - the session gate, the Agreements facade, the real HTTP calls to the
real denidin-app Agreements API - is the production code path.

Usage: agreements_backend.py <config.backend.json> <manifest.json>
"""
import json
import sys
from pathlib import Path

import uvicorn

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "backend" / "src"))
sys.path.insert(0, str(HERE.parents[1] / "denidin-app" / "src"))
sys.path.insert(0, str(HERE.parents[1] / "denidin-app"))

from webapp_backend.config import AppConfig  # noqa: E402
from webapp_backend.server import build_app  # noqa: E402


def main() -> None:
    config = AppConfig.from_file(sys.argv[1])
    official = list(json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))["clients"].values())
    app = build_app(config, official_clients_fn=lambda: list(official))
    uvicorn.run(app, host=config.http.host, port=config.http.port, log_level="warning")


if __name__ == "__main__":
    main()
