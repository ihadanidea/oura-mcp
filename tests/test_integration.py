"""End-to-end integration tests at the MCP protocol boundary: real JSON-RPC
requests through the real ASGI app (create_app()), including the real auth
middleware stack. The Oura API is stubbed via respx from the fixture corpus
-- no live PAT, no network. See the request's Integration Test Plan for the
13 scenarios this file implements.
"""

import json

import httpx
import pytest
import respx
from starlette.testclient import TestClient

from oura_mcp.server import create_app

TOKEN = "test-mcp-auth-token"  # matches conftest's MCP_AUTH_TOKEN default
INIT_PARAMS = {
    "protocolVersion": "2025-06-18",
    "capabilities": {},
    "clientInfo": {"name": "test-client", "version": "0.1"},
}
MCP_HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


def _rpc(method: str, params: dict, id_: int = 1) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "method": method, "params": params}


def _sse_json(resp: httpx.Response) -> dict:
    """FastMCP's streamable-HTTP transport replies as SSE; pull the single
    `data:` payload out and parse it as JSON-RPC."""
    for line in resp.text.splitlines():
        if line.startswith("data: "):
            return json.loads(line[len("data: ") :])
    raise AssertionError(f"no SSE data line in response: {resp.text!r}")


def _mock_oura(endpoint: str, fixture: dict) -> respx.Route:
    return respx.get(path__regex=rf"^/v2/usercollection/{endpoint}$").mock(
        return_value=httpx.Response(200, json=fixture)
    )


@pytest.fixture
def app():
    return create_app()


# 1. Protocol handshake
def test_initialize_and_tools_list(app):
    with TestClient(app) as client:
        init = _sse_json(
            client.post("/mcp", json=_rpc("initialize", INIT_PARAMS), headers=MCP_HEADERS)
        )
        assert init["result"]["serverInfo"]["name"] == "oura"

        listing = _sse_json(client.post("/mcp", json=_rpc("tools/list", {}, id_=2), headers=MCP_HEADERS))
        names = {t["name"] for t in listing["result"]["tools"]}
        assert names == {
            "get_daily_activity", "get_daily_readiness", "get_daily_sleep", "get_sleep_periods",
            "get_workouts", "get_activity_summary", "get_heart_rate", "get_daily_stress",
            "get_daily_spo2", "get_sessions", "get_tags",
        }


# 2. Single-page tool call
def test_single_page_tool_call_field_fidelity(app, load_fixture):
    _mock_oura("daily_sleep", load_fixture("daily_sleep"))
    with TestClient(app) as client:
        resp = _sse_json(
            client.post(
                "/mcp",
                json=_rpc("tools/call", {"name": "get_daily_sleep", "arguments": {"date_from": "2026-08-10", "date_to": "2026-08-11"}}),
                headers=MCP_HEADERS,
            )
        )
    records = resp["result"]["structuredContent"]["result"]
    assert records[0]["day"] == "2026-08-10"
    assert isinstance(records[0]["score"], int)
    assert resp["result"]["isError"] is False


# 3. Multi-page pagination end-to-end (highest-value integration scenario)
def test_multi_page_pagination_end_to_end(app, load_fixture):
    page1, page2 = load_fixture("sleep_page1"), load_fixture("sleep_page2")
    route = respx.get(path__regex=r"^/v2/usercollection/sleep$")
    route.side_effect = [httpx.Response(200, json=page1), httpx.Response(200, json=page2)]

    with TestClient(app) as client:
        resp = _sse_json(
            client.post(
                "/mcp",
                json=_rpc("tools/call", {"name": "get_sleep_periods", "arguments": {"date_from": "2026-08-09", "date_to": "2026-08-11"}}),
                headers=MCP_HEADERS,
            )
        )
    records = resp["result"]["structuredContent"]["result"]
    assert [r["day"] for r in records] == ["2026-08-10", "2026-08-11"]
    assert route.call_count == 2


# 4. Unit and timestamp fidelity (golden record)
def test_sleep_periods_unit_and_timestamp_fidelity(app, load_fixture):
    fixture = {**load_fixture("sleep_page1"), "next_token": None}
    _mock_oura("sleep", fixture)
    with TestClient(app) as client:
        resp = _sse_json(
            client.post(
                "/mcp",
                json=_rpc("tools/call", {"name": "get_sleep_periods", "arguments": {"date_from": "2026-08-09", "date_to": "2026-08-10"}}),
                headers=MCP_HEADERS,
            )
        )
    record = resp["result"]["structuredContent"]["result"][0]
    assert record["total_sleep_duration_s"] == 27000
    assert isinstance(record["total_sleep_duration_s"], int)
    assert record["bedtime_start"] == "2026-08-09T23:14:02-07:00"


# 5. Heart-rate summarization
def test_heart_rate_summarization_over_full_series(app, load_fixture):
    _mock_oura("heartrate", load_fixture("heartrate"))
    with TestClient(app) as client:
        resp = _sse_json(
            client.post(
                "/mcp",
                json=_rpc("tools/call", {"name": "get_heart_rate", "arguments": {"date_from": "2026-08-10", "date_to": "2026-08-11"}}),
                headers=MCP_HEADERS,
            )
        )
    records = resp["result"]["structuredContent"]["result"]
    day1 = next(r for r in records if r["day"] == "2026-08-10")
    assert day1["readings"] == 5
    assert day1["bpm_min"] == 46
    assert day1["bpm_max"] == 128
    assert "bpm" not in day1


# 6. Auth: path token accepted
def test_auth_path_token_accepted(app):
    with TestClient(app) as client:
        resp = client.post(f"/mcp/{TOKEN}", json=_rpc("initialize", INIT_PARAMS), headers={
            "Content-Type": "application/json", "Accept": "application/json, text/event-stream",
        })
    assert resp.status_code == 200
    assert _sse_json(resp)["result"]["serverInfo"]["name"] == "oura"


# 7. Auth: Bearer header accepted
def test_auth_bearer_header_accepted(app):
    with TestClient(app) as client:
        resp = client.post("/mcp", json=_rpc("initialize", INIT_PARAMS), headers=MCP_HEADERS)
    assert resp.status_code == 200
    assert _sse_json(resp)["result"]["serverInfo"]["name"] == "oura"


# 8. Auth: rejection matrix -- and no Oura call leaks through on rejection
def test_auth_rejection_matrix_makes_no_oura_call(app):
    route = respx.get(path__regex=r"^/v2/usercollection/.*$").mock(return_value=httpx.Response(200, json={"data": [], "next_token": None}))
    with TestClient(app) as client:
        wrong_path = client.post(f"/mcp/wrong-token", json=_rpc("initialize", {}), headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"})
        wrong_header = client.post("/mcp", json=_rpc("initialize", {}), headers={**MCP_HEADERS, "Authorization": "Bearer wrong"})
        absent_header = client.post("/mcp", json=_rpc("initialize", {}), headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream"})

    assert wrong_path.status_code == 401
    assert wrong_header.status_code == 401
    assert absent_header.status_code == 401
    assert route.call_count == 0


# 9. Auth: fail closed on unset token -- asserted against the ASGI app directly.
# server.py's module-level `app = create_app()` (the object `uvicorn
# oura_mcp.server:app` imports) is what makes this hold at import time too,
# not just via this direct call -- the standalone uvicorn path is where
# upstream's original gap (3c) lived.
def test_fails_closed_when_auth_token_unset(monkeypatch):
    monkeypatch.delenv("MCP_AUTH_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="MCP_AUTH_TOKEN"):
        create_app()


# 10. Health endpoint
def test_health_anonymous_liveness_only(app):
    with TestClient(app) as client:
        resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_health_authenticated_reports_oura_connectivity(app):
    _mock_oura("personal_info", {"id": "u1"})
    with TestClient(app) as client:
        resp = client.get("/health", headers={"Authorization": f"Bearer {TOKEN}"})
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "oura_api": True}


def test_health_degraded_when_oura_errors(app):
    respx.get(path__regex=r"^/v2/usercollection/personal_info$").mock(return_value=httpx.Response(500))
    with TestClient(app) as client:
        resp = client.get("/health", headers={"Authorization": f"Bearer {TOKEN}"})
    assert resp.json() == {"status": "degraded", "oura_api": False}


# 11. Upstream error propagation -- no silent failures
@pytest.mark.parametrize("status_code", [401, 429])
def test_upstream_error_surfaces_explicitly(app, status_code):
    respx.get(path__regex=r"^/v2/usercollection/daily_sleep$").mock(
        return_value=httpx.Response(status_code, json={"detail": "error"})
    )
    with TestClient(app) as client:
        resp = _sse_json(
            client.post(
                "/mcp",
                json=_rpc("tools/call", {"name": "get_daily_sleep", "arguments": {}}),
                headers=MCP_HEADERS,
            )
        )
    assert resp["result"]["isError"] is True
    assert str(status_code) in resp["result"]["content"][0]["text"]


# 12. Timeout behavior
def test_upstream_timeout_surfaces_explicitly(app):
    def _timeout(request):
        raise httpx.TimeoutException("timed out", request=request)

    respx.get(path__regex=r"^/v2/usercollection/daily_sleep$").mock(side_effect=_timeout)
    with TestClient(app) as client:
        resp = _sse_json(
            client.post(
                "/mcp",
                json=_rpc("tools/call", {"name": "get_daily_sleep", "arguments": {}}),
                headers=MCP_HEADERS,
            )
        )
    assert resp["result"]["isError"] is True
