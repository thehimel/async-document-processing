# Rate Limiting Setup

Protects authentication endpoints from brute-force attacks and registration flooding using
[`slowapi`](https://pypi.org/project/slowapi/), a thin FastAPI/Starlette wrapper around the
[`limits`](https://limits.readthedocs.io/) library.

---

## Why Rate Limiting on Auth Endpoints

Without rate limiting:

- **OAuth abuse** — repeated auth redirect or callback requests can be used for DoS
- **Session probing** — repeated session-check requests can probe for valid sessions

---

## Installation

Run `uv sync` — `slowapi` is already in `pyproject.toml`.

---

## How It Works

`SlowAPIMiddleware` intercepts every incoming request and counts it against the client's
IP address using the `default_limits` defined on the `Limiter` instance. No decorator is
needed on individual route handlers — the limit applies automatically to every route.

When a client exceeds the limit, slowapi returns:

```
HTTP 429 Too Many Requests
```

---

## Current Configuration

The `Limiter` is defined in `app/limiter.py` and registered on the app in `app/main.py`.

| Setting | Value |
|---|---|
| Key function | Client IP (`get_remote_address`) |
| Default limit | `60/minute` (all routes) |
| Storage | In-process memory (default) |

The `60/minute` default covers all endpoints (including auth) without requiring per-route decorators.

---

## Adding Per-Route Limits

For routes defined directly in the codebase, stricter limits can be applied with the
`@limiter.limit()` decorator imported from `app.limiter`. The route handler must also
accept a `Request` parameter for slowapi to extract the client key.

---

## Upgrading to Redis-Backed Storage (Production)

The default in-memory storage resets on every server restart and does not share state
across multiple workers or instances. For production, pass a `storage_uri` to the
`Limiter` in `app/limiter.py` pointing at a Redis instance, and install `limits[redis]`.
Read the URI from `settings` so it stays out of the source code.

---

## References

- [`slowapi` on PyPI](https://pypi.org/project/slowapi/)
- [`slowapi` documentation](https://slowapi.readthedocs.io/)
- [`limits` library](https://limits.readthedocs.io/)
