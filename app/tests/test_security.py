"""Security tests — auth, authorization, rate limiting, input validation."""

import uuid

import pytest
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.main import app
from app.tests.helpers import make_auth_cookie, set_auth_cookies
from app.users.models import User, UserRole


class TestUnauthenticatedAccess:
    """Unauthenticated access to protected routes returns 401."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "method,route_attr,payload",
        [
            ("get", "users_me", None),
            ("get", "users_by_id", None),
            ("patch", "users_update_by_id", {"role": "user"}),
            ("delete", "users_delete_by_id", None),
        ],
        ids=[
            "get_me",
            "get_user",
            "patch_user",
            "delete_user",
        ],
    )
    async def test_protected_routes_return_401_without_cookie(self, client_e2e, routes, method, route_attr, payload):
        """Protected routes return 401 when no auth cookie is provided."""
        route_fn = getattr(routes, route_attr)
        if "by_id" in route_attr:
            url = route_fn(uuid.uuid4())
        else:
            url = route_fn

        if method == "get":
            response = await client_e2e.get(url)
        elif method == "patch":
            response = await client_e2e.patch(url, json=payload or {})
        elif method == "delete":
            response = await client_e2e.delete(url)
        else:
            response = await client_e2e.post(url, json=payload or {})

        assert response.status_code == 401


class TestRateLimiting:
    """Rate limiting returns 429 when limit exceeded."""

    @pytest.mark.asyncio
    async def test_auth_me_rate_limit_returns_429(self, client_e2e, routes):
        """Exceeding the rate limit on an auth endpoint returns 429."""
        strict_limiter = Limiter(
            key_func=get_remote_address,
            default_limits=["2/minute"],
        )
        original = app.state.limiter
        app.state.limiter = strict_limiter

        try:
            for _ in range(2):
                r = await client_e2e.get(routes.auth_me)
                assert r.status_code != 429

            r = await client_e2e.get(routes.auth_me)
            assert r.status_code == 429
        finally:
            app.state.limiter = original


class TestUserCannotAccessAdminRoutes:
    """User role cannot access admin-only routes (403)."""

    @pytest.mark.asyncio
    async def test_user_cannot_access_admin_user_routes(self, client_e2e, db_session, routes):
        """User cannot GET/PATCH/DELETE users."""
        user = User(
            id=uuid.uuid4(),
            email=f"user-sec-{uuid.uuid4().hex[:8]}@example.com",
            name="User",
            is_active=True,
            role=UserRole.user,
        )
        db_session.add(user)
        await db_session.flush()
        cookies = make_auth_cookie(user)

        other_id = uuid.uuid4()

        set_auth_cookies(client_e2e, cookies)
        assert (await client_e2e.get(routes.users_by_id(other_id))).status_code == 403
        assert (
            await client_e2e.patch(
                routes.users_update_by_id(other_id),
                json={"role": UserRole.admin.value},
            )
        ).status_code == 403
        assert (await client_e2e.delete(routes.users_delete_by_id(other_id))).status_code == 403
