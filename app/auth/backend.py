"""
Auth backend: Authlib Google OAuth client, JWT helpers, and FastAPI dependencies.

Cookie name: access_token (httpOnly, set by the /auth/google/callback endpoint).

Public API:
  oauth                    — Authlib OAuth registry (use oauth.google in auth router)
  create_access_token()    — sign a JWT from a payload dict
  decode_access_token()    — verify and decode a JWT
  get_current_user         — FastAPI dependency: validates cookie JWT, returns active User
  current_active_user      — alias for get_current_user (for consistent naming)
  get_current_user_optional— same, but returns None instead of raising 401
  current_user_optional    — alias for get_current_user_optional
  require_role()           — RBAC factory: returns a dependency enforcing a set of roles
  current_user             — user or admin
  current_admin            — admin only
"""

import uuid
from datetime import datetime, timedelta, timezone

import jwt
from authlib.integrations.starlette_client import OAuth  # type: ignore[import-untyped]
from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.errors import InsufficientPermissionsError
from app.config import settings
from app.database import get_db
from app.users.models import User, UserRole

# Cookie name written by the callback endpoint and read by get_current_user.
COOKIE_NAME = "access_token"

# --- Authlib OAuth client -------------------------------------------------

oauth = OAuth()
oauth.register(
    name="google",
    client_id=settings.google_client_id,
    client_secret=settings.google_client_secret,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

# --- JWT helpers -------------------------------------------------------------


def create_access_token(data: dict) -> str:
    """Return a signed JWT. `data` should contain at minimum `sub` (user id as str)."""
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Verify signature and expiry; return the decoded payload dict."""
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])


# --- Cookie-based auth dependencies ------------------------------------------


async def get_current_user(
    access_token: str | None = Cookie(default=None),
    session: AsyncSession = Depends(get_db),
) -> User:
    """Validate the httpOnly JWT cookie and return the active User."""
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated.",
    )
    if access_token is None:
        raise unauthorized
    try:
        payload = decode_access_token(access_token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired.",
        )
    except jwt.InvalidTokenError:
        raise unauthorized

    user_id_raw: str | None = payload.get("sub")
    if user_id_raw is None:
        raise unauthorized

    try:
        user_id = uuid.UUID(user_id_raw)
    except ValueError:
        raise unauthorized

    user: User | None = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise unauthorized
    return user


async def get_current_user_optional(
    access_token: str | None = Cookie(default=None),
    session: AsyncSession = Depends(get_db),
) -> User | None:
    """Like get_current_user but returns None instead of raising 401."""
    if access_token is None:
        return None
    try:
        payload = decode_access_token(access_token)
    except jwt.InvalidTokenError:
        return None

    user_id_raw: str | None = payload.get("sub")
    if user_id_raw is None:
        return None
    try:
        user_id = uuid.UUID(user_id_raw)
    except ValueError:
        return None

    user: User | None = await session.get(User, user_id)
    if user is None or not user.is_active:
        return None
    return user


# Aliases kept for consistent naming across imports
current_active_user = get_current_user
current_user_optional = get_current_user_optional


# --- Role-based access control -----------------------------------------------


def require_role(*roles: UserRole):
    """Return a dependency that enforces one of the given roles."""

    async def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise InsufficientPermissionsError()
        return user

    return checker


current_user = require_role(UserRole.user, UserRole.admin)
current_admin = require_role(UserRole.admin)
