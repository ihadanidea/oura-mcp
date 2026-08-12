"""Auth via token in URL path or Bearer header."""

import hmac

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


def token_matches(candidate: str, expected: str) -> bool:
    """Constant-time comparison to avoid timing side channels."""
    return hmac.compare_digest(candidate.encode(), expected.encode())


class TokenPathAuthMiddleware(BaseHTTPMiddleware):
    """Auth via token in URL path: /mcp/<token> or Bearer header.

    Accepts:
      - POST /mcp/<token>  (for Claude.ai connectors)
      - POST /mcp with Authorization: Bearer <token>  (for Claude Code CLI)
      - GET /health  (open; liveness only unless a valid Bearer token is sent)
    """

    def __init__(self, app, auth_token: str) -> None:
        super().__init__(app)
        self._auth_token = auth_token

    async def dispatch(self, request, call_next):
        path = request.url.path

        if path == "/health":
            return await call_next(request)

        if path.startswith("/mcp/"):
            token = path[len("/mcp/") :]
            if token_matches(token, self._auth_token):
                request.scope["path"] = "/mcp"
                return await call_next(request)
            return JSONResponse({"error": "Unauthorized"}, status_code=401)

        if path == "/mcp":
            auth_header = request.headers.get("authorization", "")
            if auth_header.startswith("Bearer ") and token_matches(auth_header[7:], self._auth_token):
                return await call_next(request)
            return JSONResponse({"error": "Unauthorized"}, status_code=401)

        return JSONResponse({"error": "Not Found"}, status_code=404)
