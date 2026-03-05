# Authentication Testing

How to test the Google OAuth + cookie-based JWT authentication. See [README](README.md) for auth overview and endpoints.

---

## 1. Automated Tests

```bash
# Auth flow tests (Google callback, cookie, /me, logout)
uv run pytest app/tests/test_e2e.py::TestE2EAuthFlow -v

# Security tests (401, rate limit, RBAC)
uv run pytest app/tests/test_security.py -v
```

**Covered:** Google callback creates/updates users and sets JWT cookie; `GET /api/auth/me` with valid cookie returns user; `POST /api/auth/logout` clears cookie; unauthenticated access returns 401; rate limiting on `/api/auth/me`.

---

## 2. Manual Testing (Browser)

**Prerequisites:** See [README](README.md) for Google Cloud setup. Ensure `.env` has `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `JWT_SECRET_KEY`, `SESSION_SECRET_KEY`.

1. Start the API: `uv run uvicorn app.main:app --reload`
2. Open `http://localhost:8000/api/auth/google?redirect_url=http://localhost:8000/docs`
3. Sign in with Google; you should be redirected to `/docs` with a session cookie set.
4. Call `GET /api/auth/me` from Swagger UI (with credentials enabled).
5. Call `POST /api/auth/logout` to clear the cookie.

---

## 3. Manual Testing (curl)

```bash
curl -c cookies.txt -L "http://localhost:8000/api/auth/google?redirect_url=http://localhost:8000/docs"
curl -b cookies.txt http://localhost:8000/api/auth/me
curl -b cookies.txt -c cookies.txt -X POST http://localhost:8000/api/auth/logout
```

---

## 4. Frontend Integration

1. Link "Sign in with Google" to `/api/auth/google?redirect_url=https://example.com/dashboard`
2. After redirect, call `GET /api/auth/me` with `credentials: 'include'`
3. Use `POST /api/auth/logout` to sign out

CORS: Set `CORS_ORIGINS` in `.env` for production. Default redirect when no `redirect_url` is provided: `/` (see `app/auth/router.py`).
