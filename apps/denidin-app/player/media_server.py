"""
LocalMediaServer (Feature 043, tasks.md T011).

A local static-file HTTP server over the export's extracted media directory,
so the player can synthesize real `downloadUrl` values MediaHandler fetches
over HTTP exactly like it would a real Green API download URL - same pattern
tests/expensive/test_ledger_event_capture_e2e.py already uses for fixture
media, factored out here as a small reusable context manager.
"""
import threading
from functools import partial
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Optional


class LocalMediaServer:
    """Context manager: serves `media_dir` over HTTP on an OS-assigned free
    port (never a fixed port - avoids collisions on a long-running replay,
    and lets multiple instances coexist, e.g. across test runs).

    Usage:
        with LocalMediaServer(media_dir) as base_url:
            ...  # base_url is "http://127.0.0.1:<port>"
    """

    def __init__(self, media_dir: Path, port: int = 0):
        self._media_dir = Path(media_dir)
        self._port = port
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def __enter__(self) -> str:
        handler = partial(SimpleHTTPRequestHandler, directory=str(self._media_dir))
        self._server = HTTPServer(("127.0.0.1", self._port), handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return f"http://127.0.0.1:{self._server.server_port}"

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)
