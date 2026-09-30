"""Starlette ASGI app for webapp-backend (Feature 068).

Auth model differs from morning-mcp-app's ``BearerTokenMiddleware`` in one way: the accepted
token is dynamic (minted at ``POST /api/auth/login``), so the middleware checks membership in
a live ``SessionStore`` rather than one fixed config value. ``/health`` and
``/api/auth/login`` are the only unauthenticated paths.
"""
import logging
import mimetypes
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response
from starlette.routing import Route

from webapp_backend.auth import PasswordVerifier, SessionStore
from webapp_backend.clients_reader import ClientsReader
from webapp_backend.config import AppConfig
from webapp_backend.context_reader import ContextReader
from webapp_backend.health_checks import INFORMATIONAL_CHECKS, build_health_check_fns, start_heartbeat_thread
from webapp_backend.ledger_reader import DEFAULT_DAYS_BACK, LedgerReader
from webapp_backend.logger import resolve_log_path, setup_logging
from webapp_backend.morning_client_source import MorningClientSource, MorningClientSourceError

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


def build_app(config: AppConfig, log_path: Optional[Path] = None) -> Starlette:
    verifier = PasswordVerifier(Path(config.password_hash_file))
    sessions = SessionStore(config.session_expiry_hours)
    reader = LedgerReader(config.denidin_data_root)
    context_reader = ContextReader(config.denidin_data_root)
    morning_source = MorningClientSource(
        api_key_id=config.morning_api_key_id,
        api_key_secret=config.morning_api_key_secret,
        auth_url=config.morning_auth_url,
        api_url=config.morning_api_url,
    )
    clients_reader = ClientsReader(
        config.denidin_data_root,
        config.clients_data_root,
        morning_source.list_active_client_names,
        events_fn=reader.events,
        generation_fn=lambda: reader.generation,
    )
    version = read_version()
    if not verifier.usable:
        logger.warning(
            "Password hash file unusable (%s) - backend is up but every login will fail "
            "until the file is fixed",
            verifier.load_error,
        )

    # Real dependency checks, same shape/rationale as denidin-app's and morning-mcp-app's
    # /health (bugfix-043): each is a zero-arg callable bound to a live value. log_path is only
    # passed when a file logger was set up (main()/app_factory()) - when it's None the
    # logs_writing check is simply omitted, not reported as failed.
    _health_checks = build_health_check_fns(
        denidin_data_root=config.denidin_data_root,
        password_hash_file=config.password_hash_file,
        ledger_reader=reader,
        log_path=log_path,
        morning_ping=morning_source.ping,
    )

    def health(_request: Request) -> JSONResponse:
        body: dict = {
            "app_up": "success",
            "environment": config.environment,
            "version": version,
        }
        all_ok = True
        for name, check_fn in _health_checks.items():
            try:
                ok = check_fn()
            except Exception:  # noqa: BLE001 - a check that raises is a failed check, not a 500
                logger.warning("health check %r raised", name, exc_info=True)
                ok = False
            body[name] = "success" if ok else "fail"
            if name not in INFORMATIONAL_CHECKS:
                all_ok = all_ok and ok
        body["status"] = "ok" if all_ok else "fail"
        return JSONResponse(body, status_code=200 if all_ok else 503)

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

    def events(request: Request) -> JSONResponse:
        if request.query_params.get("refresh") == "1":
            # Hard refresh: re-read the event files and drop the cached conversations; the
            # context cache refills in the background so this response isn't held up by it.
            reader.reload()
            context_reader.reset()
            context_reader.warm_in_background()
        raw = request.query_params.get("days_back")
        try:
            days_back = int(raw) if raw is not None else DEFAULT_DAYS_BACK
        except ValueError:
            days_back = DEFAULT_DAYS_BACK
        return JSONResponse(reader.list_event_rows(days_back))

    def event_detail(request: Request) -> JSONResponse:
        record = reader.get_event_detail(request.path_params["event_id"])
        if record is None:
            return _error("not_found", "No such event.", 404)
        return JSONResponse(record)

    def clients_search(request: Request) -> JSONResponse:
        prefix = request.query_params.get("prefix", "")
        return JSONResponse({"clients": reader.search_client_names(prefix)})

    def event_context(request: Request) -> JSONResponse:
        record = reader.raw_event(request.path_params["event_id"])
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

    def clients(request: Request) -> JSONResponse:
        try:
            return JSONResponse(clients_reader.get_report(refresh=request.query_params.get("refresh") == "1"))
        except MorningClientSourceError as exc:
            logger.warning("Morning client-list fetch failed: %s", exc)
            return _error(
                "morning_unavailable",
                "לא ניתן לטעון את רשימת הלקוחות ממורנינג כעת. נסו שוב מאוחר יותר.",
                503,
            )

    async def client_comment(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001 - malformed body is just a bad request
            body = {}
        comment = body.get("comment") if isinstance(body, dict) else None
        if not isinstance(comment, str):
            return _error("bad_request", "comment is required.", 400)
        result = await run_in_threadpool(
            clients_reader.save_comment, request.path_params["client_id"], comment
        )
        return JSONResponse(result)

    async def client_mapping(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            body = {}
        raw_name = body.get("raw_name") if isinstance(body, dict) else None
        official_name = body.get("official_name") if isinstance(body, dict) else None
        note = body.get("note") if isinstance(body, dict) else None
        if not isinstance(raw_name, str) or not raw_name:
            return _error("bad_request", "raw_name is required.", 400)
        if official_name is not None and not isinstance(official_name, str):
            return _error("bad_request", "official_name must be a string.", 400)
        if note is not None and not isinstance(note, str):
            return _error("bad_request", "note must be a string.", 400)
        if official_name is None and note is None:
            return _error("bad_request", "official_name or note is required.", 400)
        result = await run_in_threadpool(
            clients_reader.save_mapping, raw_name, official_name=official_name, note=note
        )
        return JSONResponse(result)

    def media(request: Request) -> Response:
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
            Route("/api/clients", clients, methods=["GET"]),
            Route("/api/clients/{client_id}/comments", client_comment, methods=["POST"]),
            Route("/api/clients/mapping", client_mapping, methods=["POST"]),
            Route("/api/media/{token}", media, methods=["GET"]),
        ]
    )
    app.add_middleware(SessionAuthMiddleware, sessions=sessions)
    # Dev convenience: the Vite dev server runs on a different port. In dev/prod the browser
    # only ever talks to the frontend nginx (same origin), which reverse-proxies /api + /health
    # to this backend, so this wildcard CORS is never actually exercised there.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.sessions = sessions
    app.state.verifier = verifier

    def warm_caches() -> None:
        """Fill the conversation and clients caches in the background so the first click on
        an event / the Clients tab is served from memory. Production entrypoints only - tests
        build the app first and write fixture files afterwards."""
        context_reader.warm_in_background()
        clients_reader.warm_in_background()

    app.state.warm_caches = warm_caches
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
    log_path = setup_logging(level=config.http.log_level)
    start_heartbeat_thread()
    app = build_app(config, log_path=log_path)
    app.state.warm_caches()
    return app


def main() -> None:  # pragma: no cover - container entrypoint
    import sys

    import uvicorn

    config_path = sys.argv[1] if len(sys.argv) > 1 else "config/config.dev.json"
    config = AppConfig.from_file(config_path)
    config.validate()
    if config.denidin_src_path and config.denidin_src_path not in sys.path:
        sys.path.insert(0, config.denidin_src_path)
    log_path = setup_logging(level=config.http.log_level)
    start_heartbeat_thread()
    logger.info("webapp-backend starting: env=%s version=%s", config.environment, read_version())
    app = build_app(config, log_path=log_path)
    app.state.warm_caches()
    uvicorn.run(
        app,
        host=config.http.host,
        port=config.http.port,
        log_level=config.http.log_level.lower(),
    )


if __name__ == "__main__":  # pragma: no cover
    main()
