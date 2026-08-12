"""Oura Ring MCP server — FastMCP app assembly.

Exposes daily activity, readiness, sleep, workouts, heart rate, stress,
SpO2, sessions, and tags from the Oura v2 API.
Read-only by design: the Oura API is read-only, so there is nothing to gate.

Env:
    OURA_ACCESS_TOKEN   Personal access token from cloud.ouraring.com
    MCP_AUTH_TOKEN      Required. Auth token for /mcp/<token> or Bearer
                        header; the server refuses to start without it.
    OURA_TIMEOUT        Request timeout seconds (default 30)

Run:
    uvicorn oura_mcp.server:app --host 0.0.0.0 --port 8000
"""

import time
from typing import Optional

from fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.responses import JSONResponse

from oura_mcp.auth import TokenPathAuthMiddleware, token_matches
from oura_mcp.client import OuraClient
from oura_mcp.config import Config, load_config
from oura_mcp.tools import OuraTools, register_tools

_HEALTH_TTL_S = 60


def _make_health_route(client: OuraClient, auth_token: str):
    # Cache is scoped to this app instance (closed over here), not a module
    # global, so repeated create_app() calls in tests don't leak state
    # across each other. Still one process, one app, one cache in production.
    cache: dict = {"ts": None, "ok": False}

    async def health(request):
        # Anonymous callers get process liveness only. Oura connectivity
        # detail reveals whether the token is currently valid, so it
        # requires auth.
        auth_header = request.headers.get("authorization", "")
        if not (auth_header.startswith("Bearer ") and token_matches(auth_header[7:], auth_token)):
            return JSONResponse({"status": "ok"})
        # Cached: at most one upstream call per _HEALTH_TTL_S regardless of
        # traffic.
        now = time.monotonic()
        if cache["ts"] is None or now - cache["ts"] >= _HEALTH_TTL_S:
            try:
                resp = client.get_personal_info()
                ok = resp.status_code == 200
            except Exception:
                ok = False
            cache["ts"] = now
            cache["ok"] = ok
        ok = cache["ok"]
        return JSONResponse({"status": "ok" if ok else "degraded", "oura_api": ok})

    return health


def create_app(config: Optional[Config] = None) -> Starlette:
    config = config or load_config()
    client = OuraClient(token=config.oura_token, timeout=config.timeout, base_url=config.oura_base)
    tools = OuraTools(client)

    mcp = FastMCP("oura")
    register_tools(mcp, tools)
    mcp.custom_route("/health", methods=["GET"])(_make_health_route(client, config.auth_token))

    app = mcp.http_app(stateless_http=True)
    app.add_middleware(TokenPathAuthMiddleware, auth_token=config.auth_token)
    return app


app = create_app()
