"""Starlette ASGI app for webapp-backend (Feature 068).

Auth model differs from morning-mcp-app's ``BearerTokenMiddleware`` in one way: the accepted
token is dynamic (minted at ``POST /api/auth/login``), so the middleware checks membership in
a live ``SessionStore`` rather than one fixed config value. ``/health`` and
``/api/auth/login`` are the only unauthenticated paths.
"""
import logging
import mimetypes
from pathlib import Path
from typing import Any, Awaitable, Callable

from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response
from starlette.routing import Route

from webapp_backend.auth import PasswordVerifier, SessionStore
from webapp_backend.config import AppConfig
from webapp_backend.context_reader import ContextReader
from webapp_backend.ledger_reader import DEFAULT_DAYS_BACK, LedgerReader

logger = logging.getLogger("webapp_backend")

DEFAULT_VERSION_FILE = Path(__file__).resolve().parents[3] / "VERSION"
_UNAUTHENTICATED_PATHS = {"/health", "/api/auth/login"}


def read_version(path: Path = DEFAULT_VERSION_FILE) -> str:
    try:
        return Path(path).read_text(encoding="utf-8").strip() or "0.0.0"
    except OSError:
        return "0.0.0"


def _error(code: str, message: str, status: int) -> JSONResponse:
    return JSONResponse({"error": code, "message": message}, status_code=status)


class SessionAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: Any, sessions: SessionStore) -> None:
        super().__init__(app)
        self._sessions = sessions

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.url.path in _UNAUTHENTICATED_PATHS:
            return await call_next(request)
        header = request.headers.get("Authorization", "")
        token = header[7:] if header.startswith("Bearer ") else None
        status = self._sessions.check(token)
        if status == "unknown":
            return _error("unauthorized", "Please log in.", 401)
        if status == "expired":
            return _error("session_expired", "Your session has expired. Please log in again.", 401)
        request.scope["session_token"] = token
        return await call_next(request)


def build_app(config: AppConfig) -> Starlette:
    verifier = PasswordVerifier(Path(config.password_hash_file), config.password_salt)
    sessions = SessionStore(config.session_expiry_hours)
    reader = LedgerReader(config.denidin_data_root)
    context_reader = ContextReader(config.denidin_data_root)
    version = read_version()
    if not verifier.usable:
        logger.warning(
            "Password hash file unusable (%s) - backend is up but every login will fail "
            "until the file is fixed",
            verifier.load_error,
        )

    async def health(_request: Request) -> JSONResponse:
        return JSONResponse(
            {"status": "ok", "environment": config.environment, "version": version}
        )

    async def login(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001 - any malformed body is just a failed login
            body = {}
        password = body.get("password") if isinstance(body, dict) else None
        ok = verifier.verify(password) if isinstance(password, str) else False
        logger.info("LOGIN %s", "success" if ok else "failure")
        if not ok:
            return _error("invalid_password", "Incorrect password.", 401)
        return JSONResponse({"token": sessions.issue()})

    async def logout(request: Request) -> Response:
        token = request.scope.get("session_token")
        if token:
            sessions.invalidate(token)
        return Response(status_code=204)

    async def events(request: Request) -> JSONResponse:
        raw = request.query_params.get("days_back")
        try:
            days_back = int(raw) if raw is not None else DEFAULT_DAYS_BACK
        except ValueError:
            days_back = DEFAULT_DAYS_BACK
        return JSONResponse(reader.list_event_rows(days_back))

    async def event_detail(request: Request) -> JSONResponse:
        record = reader.get_event_detail(request.path_params["event_id"])
        if record is None:
            return _error("not_found", "No such event.", 404)
        return JSONResponse(record)

    async def clients_search(request: Request) -> JSONResponse:
        prefix = request.query_params.get("prefix", "")
        return JSONResponse({"clients": reader.search_client_names(prefix)})

    async def event_context(request: Request) -> JSONResponse:
        record = reader.get_event_detail(request.path_params["event_id"])
        if record is None:
            return _error("not_found", "No such event.", 404)
        raw = request.query_params.get("lookback_minutes")
        try:
            lookback = int(raw) if raw is not None else 10
        except ValueError:
            lookback = 10
        return JSONResponse(
            context_reader.build_context(
                record.get("session_id"), record.get("message_id"), lookback
            )
        )

    async def media(request: Request) -> Response:
        path = context_reader.resolve_media(request.path_params["token"])
        if path is None:
            return _error("not_found", "Media not available.", 404)
        media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        return FileResponse(path, media_type=media_type)

    app = Starlette(
        routes=[
            Route("/health", health, methods=["GET"]),
            Route("/api/auth/login", login, methods=["POST"]),
            Route("/api/auth/logout", logout, methods=["POST"]),
            Route("/api/events", events, methods=["GET"]),
            Route("/api/events/{event_id}", event_detail, methods=["GET"]),
            Route("/api/events/{event_id}/context", event_context, methods=["GET"]),
            Route("/api/clients/search", clients_search, methods=["GET"]),
            Route("/api/media/{token}", media, methods=["GET"]),
        ]
    )
    app.add_middleware(SessionAuthMiddleware, sessions=sessions)
    # Dev convenience: the Vite dev server runs on a different port. Tightened at deploy time
    # (Story 10) when frontend + backend sit behind one Cloudflare hostname.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.sessions = sessions
    app.state.verifier = verifier
    return app


def app_factory() -> Starlette:  # pragma: no cover - uvicorn --factory entrypoint
    """Zero-arg factory for ``uvicorn webapp_backend.server:app_factory --factory``.

    Config path is a fixed default (``config/config.dev.json`` relative to CWD) or the single
    value of the ``WEBAPP_CONFIG`` first CLI arg via ``main()`` — no environment variables
    (repo rule). For anything other than the local dev launcher, use ``main()``.
    """
    import sys

    config_path = Path("config/config.dev.json")
    if not config_path.is_file():
        config_path = Path("config/config.test.json")
    config = AppConfig.from_file(config_path)
    config.validate()
    if config.denidin_src_path and config.denidin_src_path not in sys.path:
        sys.path.insert(0, config.denidin_src_path)
    return build_app(config)


def main() -> None:  # pragma: no cover - container entrypoint
    import sys

    import uvicorn

    config_path = sys.argv[1] if len(sys.argv) > 1 else "config/config.dev.json"
    config = AppConfig.from_file(config_path)
    config.validate()
    if config.denidin_src_path and config.denidin_src_path not in sys.path:
        sys.path.insert(0, config.denidin_src_path)
    logging.basicConfig(level=config.http.log_level.upper())
    uvicorn.run(
        build_app(config),
        host=config.http.host,
        port=config.http.port,
        log_level=config.http.log_level.lower(),
    )


if __name__ == "__main__":  # pragma: no cover
    main()
