import httpx
import pytest

from oura_mcp.client import OuraClient
from oura_mcp.config import OURA_BASE


def _client(handler) -> OuraClient:
    # A custom httpx.MockTransport bypasses respx entirely (it isn't the
    # real HTTPTransport respx patches), so this is a fully offline,
    # controlled double for testing OuraClient's own logic in isolation.
    return OuraClient(token="tok", base_url=OURA_BASE, transport=httpx.MockTransport(handler))


def test_get_collection_follows_pagination_to_exhaustion(load_fixture):
    """The single highest-value test in the suite: concatenates both pages,
    in order, with no duplication and no truncation."""
    page1 = load_fixture("sleep_page1")
    page2 = load_fixture("sleep_page2")
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(dict(httpx.QueryParams(request.url.query)))
        if "next_token" not in request.url.params:
            return httpx.Response(200, json=page1)
        return httpx.Response(200, json=page2)

    client = _client(handler)
    result = client.get_collection("sleep", {"start_date": "2026-08-10", "end_date": "2026-08-11"})

    assert len(calls) == 2
    assert calls[1]["next_token"] == page1["next_token"]
    assert [r["id"] for r in result] == [page1["data"][0]["id"], page2["data"][0]["id"]]
    assert result == page1["data"] + page2["data"]


def test_get_collection_single_page_makes_one_request(load_fixture):
    fixture = load_fixture("daily_activity")
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json=fixture)

    client = _client(handler)
    result = client.get_collection("daily_activity")

    assert len(calls) == 1
    assert result == fixture["data"]


def test_get_collection_raises_on_http_error_status():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "Unauthorized"})

    client = _client(handler)
    with pytest.raises(httpx.HTTPStatusError):
        client.get_collection("daily_activity")


def test_get_collection_propagates_timeout():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out", request=request)

    client = _client(handler)
    with pytest.raises(httpx.TimeoutException):
        client.get_collection("daily_activity")


def test_get_personal_info_hits_expected_path():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"id": "u1"})

    client = _client(handler)
    resp = client.get_personal_info()

    assert resp.status_code == 200
    assert seen["path"].endswith("/personal_info")
    assert seen["auth"] == "Bearer tok"
