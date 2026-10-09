"""Agreements API (Feature 089) - the HTTP surface the webapp BACKEND (never the browser)
uses to read and write the Agreements DB. See specs/repo/features/089-ui-agreement-edits/
contracts/agreements-api.md for the contract.

A thin Starlette layer: every rule (locking, cascade, ledger events, capacity) lives in
`AgreementsManager`; this module only authenticates, parses JSON, maps the manager's typed
errors to HTTP codes, and returns the manager's own dicts. Started from `initialize_app`'s
caller when `config.agreements_api.port` > 0 (0 = off), as a uvicorn server in a daemon
thread; `python -m src.services.agreements_api --config <file> --port <n>` runs the same app
standalone (used by the webapp's Playwright suite against a seeded throwaway data root).
"""
from __future__ import annotations

import argparse
import hmac
import threading
from typing import Any, Awaitable, Callable, Dict, List, Optional

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from src.managers.agreements_manager import AgreementsError, AgreementsManager
from src.utils.logger import get_logger

logger = get_logger(__name__)

_STATUS_BY_CODE = {
    "not_found": 404,
    "locked": 409,
    "illegal_transition": 409,
    "validation": 422,
    "invalid_actor": 422,
    "ledger_busy": 503,
}

_UNAUTHENTICATED_PATHS = {"/is_alive"}


def _error(code: str, message: str, status: int, fields: Optional[Dict[str, str]] = None) -> JSONResponse:
    body: Dict[str, Any] = {"error": {"code": code, "message": message}}
    if fields:
        body["error"]["fields"] = fields
    return JSONResponse(body, status_code=status)


async def _json_body(request: Request) -> Dict[str, Any]:
    try:
        data = await request.json()
    except ValueError as exc:
        raise _BadRequest("request body must be JSON") from exc
    if not isinstance(data, dict):
        raise _BadRequest("request body must be a JSON object")
    return data


class _BadRequest(AgreementsError):
    code = "validation"


def _written(result: Any) -> JSONResponse:
    agreement, event_ids = result
    return JSONResponse({"agreement": agreement, "ledger_event_ids": event_ids})


def build_app(manager: AgreementsManager, auth_token: str) -> Starlette:
    """The ASGI app over `manager`; every route but /is_alive needs the bearer token."""

    def guarded(
        handler: Callable[[Request], Awaitable[Response]],
    ) -> Callable[[Request], Awaitable[Response]]:
        async def wrapper(request: Request) -> Response:
            if request.url.path not in _UNAUTHENTICATED_PATHS:
                supplied = request.headers.get("authorization", "")
                expected = f"Bearer {auth_token}"
                if not auth_token or not hmac.compare_digest(supplied.encode(), expected.encode()):
                    return _error("unauthorized", "missing or wrong bearer token", 401)
            try:
                return await handler(request)
            except AgreementsError as exc:
                status = _STATUS_BY_CODE.get(exc.code, 400)
                if status >= 500:
                    logger.warning("agreements api: %s %s -> %s %s", request.method, request.url.path, exc.code, exc.message)
                return _error(exc.code, exc.message, status, exc.fields)
            except Exception:  # noqa: BLE001 - a 500 with a stable shape beats a stack trace to the caller
                logger.exception("agreements api: unhandled error on %s %s", request.method, request.url.path)
                return _error("internal_error", "unexpected error", 500)
        return wrapper

    def actor_of(body: Dict[str, Any]) -> str:
        return str(body.pop("actor", ""))

    async def is_alive(_: Request) -> Response:
        return JSONResponse({"status": "ok"})

    async def list_for_client(request: Request) -> Response:
        client_name = request.query_params.get("client_name")
        if not client_name:
            return _error("validation", "client_name is required", 422, {"client_name": "required"})
        return JSONResponse({"agreements": manager.find_agreements(client_name)})

    async def totals(_: Request) -> Response:
        return JSONResponse({"totals": manager.totals()})

    async def get_one(request: Request) -> Response:
        return JSONResponse({"agreement": manager.get_agreement(request.path_params["agreement_id"])})

    async def revisions(request: Request) -> Response:
        return JSONResponse({"revisions": manager.revisions(request.path_params["agreement_id"])})

    async def create(request: Request) -> Response:
        body = await _json_body(request)
        actor = actor_of(body)
        components: List[Dict[str, Any]] = body.get("components") or []
        return _written(manager.create_agreement(
            client_name=body.get("client_name", ""), title=body.get("title", ""),
            components=components, actor=actor, payer_name=body.get("payer_name"),
            partner_name=body.get("partner_name"), partner_percent=body.get("partner_percent"),
        ))

    async def edit(request: Request) -> Response:
        body = await _json_body(request)
        actor = actor_of(body)
        return _written(manager.edit_agreement(request.path_params["agreement_id"], body, actor))

    async def agreement_status(request: Request) -> Response:
        body = await _json_body(request)
        actor = actor_of(body)
        return _written(manager.set_agreement_status(request.path_params["agreement_id"], body.get("action", ""), actor))

    async def add_component(request: Request) -> Response:
        body = await _json_body(request)
        actor = actor_of(body)
        return _written(manager.add_component(request.path_params["agreement_id"], body, actor))

    async def edit_component(request: Request) -> Response:
        body = await _json_body(request)
        actor = actor_of(body)
        return _written(manager.edit_component(
            request.path_params["agreement_id"], request.path_params["component_key"], body, actor))

    async def component_status(request: Request) -> Response:
        body = await _json_body(request)
        actor = actor_of(body)
        return _written(manager.set_component_status(
            request.path_params["agreement_id"], request.path_params["component_key"],
            body.get("action", ""), actor))

    async def delete_component(request: Request) -> Response:
        # DELETE carries the actor as a query parameter (some HTTP clients drop DELETE bodies).
        actor = request.query_params.get("actor", "")
        return _written(manager.delete_component(
            request.path_params["agreement_id"], request.path_params["component_key"], actor))

    routes = [
        Route("/is_alive", guarded(is_alive), methods=["GET"]),
        Route("/agreements/totals", guarded(totals), methods=["GET"]),
        Route("/agreements", guarded(list_for_client), methods=["GET"]),
        Route("/agreements", guarded(create), methods=["POST"]),
        Route("/agreements/{agreement_id}", guarded(get_one), methods=["GET"]),
        Route("/agreements/{agreement_id}", guarded(edit), methods=["PATCH"]),
        Route("/agreements/{agreement_id}/revisions", guarded(revisions), methods=["GET"]),
        Route("/agreements/{agreement_id}/status", guarded(agreement_status), methods=["POST"]),
        Route("/agreements/{agreement_id}/components", guarded(add_component), methods=["POST"]),
        Route("/agreements/{agreement_id}/components/{component_key}", guarded(edit_component), methods=["PATCH"]),
        Route("/agreements/{agreement_id}/components/{component_key}", guarded(delete_component), methods=["DELETE"]),
        Route("/agreements/{agreement_id}/components/{component_key}/status",
              guarded(component_status), methods=["POST"]),
    ]
    return Starlette(routes=routes)


def start_agreements_api(manager: AgreementsManager, port: int, auth_token: str,
                         host: str = "0.0.0.0") -> Optional[uvicorn.Server]:  # noqa: S104 - container-internal; compose decides exposure
    """Starts the API in a daemon thread. port 0 = off (returns None)."""
    if port <= 0:
        return None
    if not auth_token:
        raise ValueError("agreements_api.auth_token must be set when agreements_api.port is enabled")
    server = uvicorn.Server(uvicorn.Config(build_app(manager, auth_token), host=host, port=port, log_level="warning"))
    threading.Thread(target=server.run, name="agreements-api", daemon=True).start()
    logger.info("Agreements API listening on %s:%s", host, port)
    return server


def main() -> None:
    """Standalone entry: build the minimal object graph the manager needs and serve."""
    from denidin import DeniDin  # pylint: disable=import-outside-toplevel
    from src.managers.ledger_event_manager import LedgerEventManager  # pylint: disable=import-outside-toplevel
    from src.models.config import AppConfiguration  # pylint: disable=import-outside-toplevel

    parser = argparse.ArgumentParser(description="Run the Agreements API standalone")
    parser.add_argument("--config", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    config = AppConfiguration.from_file(args.config)
    denidin = DeniDin(config)
    denidin.ledger_event_manager = LedgerEventManager(denidin)
    denidin.agreements_manager = AgreementsManager(denidin)
    token = (config.agreements_api or {}).get("auth_token", "")
    uvicorn.run(build_app(denidin.agreements_manager, token), host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
