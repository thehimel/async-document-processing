"""Shared helpers for E2E tests."""

from app.auth.backend import COOKIE_NAME, create_access_token
from app.users.models import User


def make_auth_cookie(user: User) -> dict[str, str]:
    """Return a cookie dict with a signed JWT for the given user.

    Use set_auth_cookies(client, make_auth_cookie(user)) before requests.
    """
    token = create_access_token(
        {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role.value,
        }
    )
    return {COOKIE_NAME: token}


def set_auth_cookies(client, cookies: dict[str, str]) -> None:
    """Set auth cookies on the httpx client. Use instead of per-request cookies= to avoid deprecation."""
    client.cookies.clear()
    client.cookies.update(cookies)
