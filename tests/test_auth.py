from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from oura_mcp.auth import TokenPathAuthMiddleware, token_matches

TOKEN = "correct-token"


async def _mcp(request):
    return JSONResponse({"ok": True})


async def _health(request):
    return JSONResponse({"status": "ok"})


def _client() -> TestClient:
    app = Starlette(routes=[Route("/mcp", _mcp, methods=["POST"]), Route("/health", _health, methods=["GET"])])
    app.add_middleware(TokenPathAuthMiddleware, auth_token=TOKEN)
    return TestClient(app)


def test_token_matches_constant_time_compare():
    assert token_matches("abc", "abc") is True
    assert token_matches("abc", "xyz") is False


def test_path_token_accepted():
    resp = _client().post(f"/mcp/{TOKEN}")
    assert resp.status_code == 200


def test_path_token_wrong_rejected():
    resp = _client().post("/mcp/wrong-token")
    assert resp.status_code == 401


def test_bearer_header_accepted():
    resp = _client().post("/mcp", headers={"Authorization": f"Bearer {TOKEN}"})
    assert resp.status_code == 200


def test_bearer_header_wrong_rejected():
    resp = _client().post("/mcp", headers={"Authorization": "Bearer wrong-token"})
    assert resp.status_code == 401


def test_bearer_header_absent_rejected():
    resp = _client().post("/mcp")
    assert resp.status_code == 401


def test_health_open_no_auth():
    resp = _client().get("/health")
    assert resp.status_code == 200


def test_unknown_path_not_found():
    resp = _client().get("/anything-else")
    assert resp.status_code == 404
