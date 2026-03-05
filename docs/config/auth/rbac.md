# Role-Based Access Control (RBAC)

RBAC is implemented with a `UserRole` enum on the `User` model and a `require_role` dependency factory in `app/auth/backend.py`. No third-party library is used.

---

## Roles

| Role | Description |
|------|-------------|
| `user` | Default on first Google login. |
| `admin` | Full platform access. Can manage users and roles. |

Roles are **hierarchical** — a higher role includes the permissions of lower roles: `admin ⊇ user`.

The `role` column on `User` uses `server_default=UserRole.user.value` so new users start as regular users.

---

## How It Works

**`require_role`** is a factory that returns a FastAPI dependency. The dependency first validates the session cookie JWT (via `get_current_user`), then checks that the user's role is in the allowed set. If not, it raises `InsufficientPermissionsError`, which is mapped to `403 Forbidden` by the auth exception handler.

**Pre-built dependencies** in `app/auth/backend.py`:

| Dependency | Who can access |
|------------|----------------|
| `current_active_user` | Any authenticated user (no role check) |
| `current_user_optional` | Same, but returns `None` instead of 401 when unauthenticated |
| `current_user` | user or admin |
| `current_admin` | admin only |

---

## Usage

- **Per-route**: Add `user: User = Depends(current_user)` (or `current_admin`, etc.) to the handler.
- **Router-level**: Use `APIRouter(dependencies=[Depends(current_admin)])` so all routes in that router require admin. The users `admin_router` uses this for `GET/PATCH/DELETE /api/users/{id}`.

**Optional auth** for public-ish routes: use `current_user_optional` so the handler receives `User | None`.

---

## HTTP Responses

| Situation | Status |
|-----------|--------|
| No token / invalid token | `401 Unauthorized` |
| Valid token but insufficient role | `403 Forbidden` |
| Admin attempting to delete own account | `403 Forbidden` (`CannotDeleteSelfError`) |

---

## Changing a User's Role

Role changes are admin-only via `PATCH /api/users/{id}`. The `UserAdminUpdate` schema allows `role` and `is_active` only. There is no self-update endpoint; `GET /api/users/me` is read-only.
