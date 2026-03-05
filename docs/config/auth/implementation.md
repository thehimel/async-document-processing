# Auth Implementation

Backend implementation details. See [README](README.md) for auth architecture overview.

---

## Dependencies

```
authlib
httpx
PyJWT[cryptography]
```

- **Authlib** uses `authlib.integrations.starlette_client.OAuth`. Requires `SessionMiddleware` during the OAuth handshake to store temporary `state`/`code`.
- **PyJWT[cryptography]** is the [official FastAPI recommendation](https://github.com/tiangolo/fastapi/pull/11589) since 2024. `python-jose` is abandoned — do not use it.

---

## Key Logic

1. **GET /api/auth/google**: `oauth.google.authorize_redirect(request, redirect_uri)` — Authlib builds Google URL and stores `state` in session.
2. **GET /api/auth/google/callback**: `oauth.google.authorize_access_token(request)` — Authlib exchanges `code`, fetches user info. Upsert User and Account, create JWT with `{ sub, email, role }`, set httpOnly cookie, redirect.
3. **GET /api/auth/me**: Read JWT from cookie, validate with PyJWT, return user (only if `is_active`).
4. **POST /api/auth/logout**: Clear cookie.
