"""Oura API v2 client: pagination-following GET, injectable transport."""

from typing import Optional

import httpx

from oura_mcp.config import OURA_BASE


class OuraClient:
    def __init__(
        self,
        token: str,
        timeout: float = 30,
        base_url: str = OURA_BASE,
        transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        self._client = httpx.Client(base_url=base_url, timeout=timeout, transport=transport)
        self._token = token

    def get_collection(self, endpoint: str, params: Optional[dict] = None) -> list:
        """GET an Oura collection endpoint, following next_token pagination."""
        headers = {"Authorization": f"Bearer {self._token}"}
        results: list = []
        params = dict(params or {})
        while True:
            resp = self._client.get(f"/{endpoint}", headers=headers, params=params)
            resp.raise_for_status()
            body = resp.json()
            results.extend(body.get("data", []))
            next_token = body.get("next_token")
            if not next_token:
                return results
            params["next_token"] = next_token

    def get_personal_info(self) -> httpx.Response:
        return self._client.get(
            "/personal_info",
            headers={"Authorization": f"Bearer {self._token}"},
            timeout=5,
        )
