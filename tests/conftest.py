import json
import os
from pathlib import Path

import pytest
import respx

# Set before any test module imports oura_mcp.server, since `create_app()`
# (and the module-level `app = create_app()`) raises immediately if
# MCP_AUTH_TOKEN is unset — matching the fail-closed behavior under test.
os.environ.setdefault("OURA_ACCESS_TOKEN", "test-oura-access-token")
os.environ.setdefault("MCP_AUTH_TOKEN", "test-mcp-auth-token")
# FastMCP's default logging renders tool-execution exceptions through rich's
# traceback extractor, which pathologically hangs (observed: 100% CPU,
# multi-GB RSS, never returns) when the exception originates from inside a
# respx side_effect several frames deep in this test stack. Disabling rich
# tracebacks for the test run sidesteps it entirely; FastMCP still logs the
# error, just as a plain traceback. Must be set before fastmcp is imported.
os.environ.setdefault("FASTMCP_ENABLE_RICH_TRACEBACKS", "false")

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(autouse=True)
def _no_real_network(request):
    """No test may reach the real network. respx's own `assert_all_mocked`
    raises on any httpx call that isn't explicitly routed, rather than
    letting it fall through to a real request — this vault had a prior
    incident where a test suite silently issued live API traffic for months
    (log.md 2026-08-11), so this is autouse rather than opt-in per test.

    The one exception is the `docker` marker: the container smoke test
    intentionally hits a real localhost server.
    """
    if request.node.get_closest_marker("docker"):
        yield
        return
    # No parentheses: activates respx's global router (assert_all_mocked=True
    # by default), the same one bare `respx.get(...)` calls in test bodies
    # register against. `respx.mock(...)` *with* parens spins up a separate
    # nested router instead — routes registered on it wouldn't be visible
    # here, and vice versa.
    with respx.mock:
        yield


@pytest.fixture
def load_fixture():
    def _load(name: str) -> dict:
        return json.loads((FIXTURES_DIR / f"{name}.json").read_text())

    return _load
