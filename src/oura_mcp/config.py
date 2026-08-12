"""Environment parsing and fail-fast validation."""

import os
from dataclasses import dataclass

OURA_BASE = "https://api.ouraring.com/v2/usercollection"


@dataclass(frozen=True)
class Config:
    oura_token: str
    auth_token: str
    timeout: int
    oura_base: str = OURA_BASE


def load_config() -> Config:
    """Read config from the environment. Raises if MCP_AUTH_TOKEN is unset.

    Refusing to start unauthenticated (rather than falling back to open
    access) must hold whether this runs under Compose or via `uvicorn
    oura_mcp.server:app` directly.
    """
    oura_token = os.environ.get("OURA_ACCESS_TOKEN", "")
    auth_token = os.environ.get("MCP_AUTH_TOKEN", "")
    timeout = int(os.environ.get("OURA_TIMEOUT", "30"))

    if not auth_token:
        raise RuntimeError(
            "MCP_AUTH_TOKEN is not set; refusing to start unauthenticated. "
            "Set it to a long random string, e.g. from `openssl rand -hex 32`."
        )

    return Config(oura_token=oura_token, auth_token=auth_token, timeout=timeout)
