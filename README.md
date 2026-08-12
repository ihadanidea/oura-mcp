# Oura Ring MCP Server

A self-hosted [MCP](https://modelcontextprotocol.io) server that exposes your
Oura Ring data — daily activity, readiness, sleep, workouts, heart rate,
stress, SpO2, sessions, and tags — to Claude (claude.ai connectors or Claude
Code) over HTTP.

**Change type: Feature.** This is a fork of
[`camji55/oura-mcp`](https://github.com/camji55/oura-mcp) at commit
[`c8db34f`](https://github.com/camji55/oura-mcp/commit/c8db34f) (2026-08-12),
MIT © 2026 Cameron Ingham (see [LICENSE](LICENSE)). Upstream's 494-line
server exists only as a Python string embedded in `docker-compose.yml`
(`configs.oura_server_py.content`) — nothing can import it, so it had zero
tests and no CI. This fork extracts it into an importable package with a
pytest suite, without changing behavior at the MCP tool boundary.

## What changed vs. upstream

- **Package extraction.** The inline server is now `src/oura_mcp/` —
  `config.py`, `client.py`, `auth.py`, `tools.py`, `server.py`. All 11 tools
  keep identical names, signatures, field names, units, and docstrings.
  `docker-compose.yml` mounts `./src` and a `requirements.lock` instead of
  embedding the server as a Compose `config`.
- **Test harness.** 42 tests: unit tests for pagination, field-mapping
  fidelity, and the auth accept/reject matrix, plus a 13-scenario
  integration suite at the real MCP protocol boundary (real JSON-RPC over
  HTTP through the real ASGI app, including the auth middleware). See
  [Testing](#testing).
- **What this fork did *not* do:** the four deployment security gaps this
  fork set out to check (loopback-only bind, constant-time token compare,
  fail-closed on missing `MCP_AUTH_TOKEN`, pinned dependency lockfile) were
  **already fixed upstream** by commit `c8db34f`, two commits after the SHA
  originally targeted for this fork. This change verifies and test-locks
  that inherited hardening — see [Security posture](#security-posture) — it
  did not implement it from scratch.

## Tools

| Tool | Description |
|---|---|
| `get_daily_activity` | Steps, calories, MET minutes by intensity, sedentary/resting time, activity score |
| `get_daily_readiness` | Readiness score, temperature deviation from baseline, contributor scores (HRV balance, resting HR, etc.) |
| `get_daily_sleep` | Daily sleep scores and contributors |
| `get_sleep_periods` | Detailed sleep periods: bedtimes, stage durations, efficiency, avg HR/HRV, lowest HR |
| `get_workouts` | Logged workouts with type, intensity, calories, and start/end times |
| `get_activity_summary` | Compact multi-day summary with per-day rows and period averages |
| `get_heart_rate` | Per-day HR summaries from the intraday timeseries: min/avg/max bpm and averages by source |
| `get_daily_stress` | Time in high-stress and high-recovery zones, plus Oura's day classification |
| `get_daily_spo2` | Nightly average SpO2 and breathing disturbance index |
| `get_sessions` | Meditation, breathing, nap, and relaxation sessions with type, mood, and times |
| `get_tags` | User-entered tags and notes (illness, travel, alcohol, custom) |

Date-range tools default to the last 7 days when called without arguments.
Fields are raw Oura values with explicit unit suffixes and full ISO 8601
timestamps — never human-formatted durations or times.

## Requirements

- Docker with Compose v2 (to run the server)
- [`uv`](https://docs.astral.sh/uv/) (to run tests / develop locally)
- An Oura account with a [personal access token](https://cloud.ouraring.com/personal-access-tokens)

## Quick start

1. Clone the repo and create your `.env`:

   ```bash
   cp .env.example .env
   ```

2. Edit `.env`:
   - `OURA_ACCESS_TOKEN` — your personal access token from
     [cloud.ouraring.com/personal-access-tokens](https://cloud.ouraring.com/personal-access-tokens)
   - `MCP_AUTH_TOKEN` — a long random secret that gates access to the server.
     Generate one:

     ```bash
     openssl rand -hex 32
     ```

3. Start it:

   ```bash
   docker compose up -d
   ```

   First start takes ~30s while pip installs dependencies from
   `requirements.lock` (cached in a volume afterwards). The server listens
   on `127.0.0.1:8000`; override with `OURA_MCP_PORT` / `OURA_MCP_BIND` in
   `.env`.

4. Check health:

   ```bash
   curl http://localhost:8000/health
   ```

   `{"status": "ok"}` means the server is up. To also verify your Oura token
   works, authenticate the same endpoint:

   ```bash
   source .env && curl -H "Authorization: Bearer $MCP_AUTH_TOKEN" http://localhost:8000/health
   ```

   `{"status": "ok", "oura_api": true}` means the server can reach the Oura
   API with your token.

## Connecting Claude

**claude.ai (custom connector):** add a connector with the URL

```
https://<your-host>/mcp/<MCP_AUTH_TOKEN>
```

**Claude Code:**

```bash
claude mcp add --transport http oura https://<your-host>/mcp --header "Authorization: Bearer <MCP_AUTH_TOKEN>"
```

## Configuration

All configuration is via environment variables, loaded from `.env` by Docker
Compose:

| Variable | Required | Description |
|---|---|---|
| `OURA_ACCESS_TOKEN` | yes | Oura personal access token |
| `MCP_AUTH_TOKEN` | yes | Secret gating all `/mcp` requests (path segment or Bearer header) |
| `OURA_TIMEOUT` | no | Oura API request timeout in seconds (default `30`) |
| `OURA_MCP_PORT` | no | Host port the server is published on (default `8000`) |
| `OURA_MCP_BIND` | no | Host interface to bind (default `127.0.0.1`; set `0.0.0.0` to expose beyond this machine) |

Compose fails fast with a clear error if either required variable is
missing; the server itself also refuses to start (`RuntimeError`) if
`MCP_AUTH_TOKEN` is unset, whether run under Compose or via
`uvicorn oura_mcp.server:app` directly.

## Testing

```bash
uv sync
uv run pytest
```

Runs in CI on every push and PR to `main` via
[`.github/workflows/test.yml`](.github/workflows/test.yml) (`uv sync --locked && uv run pytest`,
Python 3.12 — matching the container's `python:3.12-slim`). The `docker`-marked
container smoke test is excluded from the default run (see below) and does
not run in CI.

42 tests, ~99% coverage on `client.py`/`tools.py` (gate held at 98%). Every
Oura API call is stubbed from synthetic fixtures in `tests/fixtures/`
(generated against Oura's public OpenAPI spec, vendored as
`openapi-1.37.json` — no real health data, no live PAT). An autouse fixture
wraps every test in `respx`'s network guard, which raises immediately on any
unmocked HTTP call rather than letting it reach the network.

- `tests/test_client.py` — `OuraClient` pagination, including the two-page
  concatenation test (the single highest-value test in the suite).
- `tests/test_tools.py` — per-tool field-mapping fidelity, including a
  golden-record check for `get_sleep_periods`.
- `tests/test_auth.py` — the auth middleware accept/reject matrix.
- `tests/test_fixtures_validate.py` — fixtures validated against the
  vendored OpenAPI spec (`scripts/validate_fixtures.py`).
- `tests/test_integration.py` — 13 end-to-end scenarios at the real MCP
  protocol boundary (JSON-RPC over HTTP through the real ASGI app and auth
  middleware): handshake, single- and multi-page tool calls, unit/timestamp
  fidelity, heart-rate summarization, the full auth matrix including
  fail-closed-on-unset-token, health endpoint behavior, and explicit error
  propagation on upstream 401/429/timeout (no silent failures).

The container smoke test (`docker compose up` + one real `initialize`
against `127.0.0.1:8000`) is marked `@pytest.mark.docker` and skipped by
default — run it explicitly with `uv run pytest -m docker`. It was not run
as part of this change: **Docker isn't installed on the machine this fork
was built on.** The equivalent app-level behavior (auth-gated `/health`,
path-token and Bearer auth, `initialize` handshake) was instead verified
manually by running `uvicorn oura_mcp.server:app` directly and `curl`-ing it
— see the change history for that session. Verify the container path itself
before relying on it in production.

## Security posture

All of the following were already present in upstream at the `c8db34f` fork
point — this fork verifies them with tests and preserves them through the
package extraction, it did not introduce them:

- **Loopback-only by default.** `docker-compose.yml` binds
  `127.0.0.1:8000:8000` unless you set `OURA_MCP_BIND=0.0.0.0`.
- **Fail-closed auth.** The server refuses to start if `MCP_AUTH_TOKEN` is
  unset — `RuntimeError` at import time, so this holds under `uvicorn`
  directly, not just under Compose's `${VAR:?}` guard.
- **Constant-time token comparison** (`hmac.compare_digest`), so response
  timing leaks nothing about the token.
- **Pinned dependencies.** `requirements.lock` is fully pinned (via
  `uv pip compile`); the container installs from it at start rather than
  resolving version ranges fresh each time.
- **Auth-gated health detail.** `/health` answers anonymous callers with
  bare liveness (`{"status": "ok"}`) only. Oura connectivity detail —
  which would reveal whether your token is currently valid — requires the
  auth token, and the upstream check behind it is cached 60s so it can't be
  used to burn your Oura API quota.
- Container hardening carried over unchanged: `no-new-privileges`, 256 MB
  memory limit, log rotation.

**Still the operator's responsibility:** TLS termination. The auth token
travels in the URL path (for claude.ai connectors) or a header — put the
server behind a TLS-terminating reverse proxy (Caddy, nginx, Cloudflare
Tunnel, Tailscale) before exposing it beyond `localhost`. Path-based tokens
can end up in proxy access logs — treat those logs as sensitive. Keep `.env`
out of version control (already covered by `.gitignore`); if a token leaks,
revoke it at cloud.ouraring.com and generate a new `MCP_AUTH_TOKEN`.

## Known gaps / follow-ups

- **`health()` blocks the event loop.** The handler is `async def` but
  calls synchronous `httpx` under the hood via `OuraClient` — a pre-existing
  upstream characteristic, carried over unchanged rather than fixed inline,
  per this fork's behavior-preserving-extraction scope. Worth a dedicated
  follow-up if `/health` latency ever matters under load.
- **Container smoke test unverified on this machine** — see
  [Testing](#testing) above.

## How it works

`docker-compose.yml` starts a stock `python:3.12-slim` container, bind-mounts
`src/oura_mcp` and `requirements.lock`, installs dependencies from the
lockfile at boot, and runs `uvicorn oura_mcp.server:app`. Auth is a small
Starlette middleware (`oura_mcp.auth.TokenPathAuthMiddleware`) that accepts
either `POST /mcp/<token>` (claude.ai) or `POST /mcp` with a Bearer header
(Claude Code), and `OuraClient` transparently follows `next_token`
pagination to exhaustion on every collection endpoint.

## License

[MIT](LICENSE) © 2026 Cameron Ingham (upstream). Fork point: `c8db34f`.
