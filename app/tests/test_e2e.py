"""End-to-end tests for auth flow (Google OAuth callback + cookie JWT)."""

import uuid

import pytest
from sqlalchemy import select

from app.auth.backend import COOKIE_NAME
from app.tests.helpers import make_auth_cookie, set_auth_cookies
from app.users.models import User, UserRole


class TestE2EAuthFlow:
    """E2E: Google OAuth callback -> cookie -> authenticated requests."""

    @pytest.mark.asyncio
    async def test_google_callback_creates_user_and_sets_cookie(
        self, client_e2e, db_session, mock_google_oauth, routes
    ):
        """Callback creates a new User + Account row and returns a JWT cookie."""
        fake_userinfo = mock_google_oauth

        response = await client_e2e.get(
            routes.auth_google_callback,
            params={"code": "fake-code", "state": "fake-state"},
        )

        assert response.status_code == 302
        assert COOKIE_NAME in response.cookies

        result = await db_session.execute(select(User).where(User.email == fake_userinfo["email"]))
        user = result.scalar_one_or_none()
        assert user is not None
        assert user.name == fake_userinfo["name"]
        assert user.image == fake_userinfo["picture"]
        assert user.role == UserRole.user

    @pytest.mark.asyncio
    async def test_google_callback_returning_user_refreshes_profile(
        self, client_e2e, db_session, mock_google_oauth, routes
    ):
        """Second login via same Google account updates name/image, does not create duplicate."""
        fake_userinfo = mock_google_oauth

        # First login creates user + account.
        await client_e2e.get(
            routes.auth_google_callback,
            params={"code": "fake-code", "state": "fake-state"},
        )

        from unittest.mock import AsyncMock, patch

        from app.auth.backend import oauth

        # Patch profile data for the second callback.
        updated_userinfo = {**fake_userinfo, "name": "Updated Name", "picture": "https://example.com/new.jpg"}
        with patch.object(
            oauth.google,
            "authorize_access_token",
            new_callable=AsyncMock,
            return_value={"userinfo": updated_userinfo},
        ):
            await client_e2e.get(
                routes.auth_google_callback,
                params={"code": "fake-code2", "state": "fake-state2"},
            )

        result = await db_session.execute(select(User).where(User.email == fake_userinfo["email"]))
        users = result.scalars().all()
        # Ensure profile was updated in place (no duplicate user row).
        assert len(users) == 1
        assert users[0].name == "Updated Name"
        assert users[0].image == "https://example.com/new.jpg"

    @pytest.mark.asyncio
    async def test_get_me_returns_current_user(self, client_e2e, db_session, routes):
        """GET /auth/me with valid cookie returns the authenticated user."""
        user = User(
            id=uuid.uuid4(),
            email="me-test@example.com",
            name="Me Test",
            is_active=True,
            role=UserRole.user,
        )
        db_session.add(user)
        await db_session.flush()

        set_auth_cookies(client_e2e, make_auth_cookie(user))
        response = await client_e2e.get(routes.auth_me)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(user.id)
        assert data["email"] == user.email
        assert data["role"] == UserRole.user.value

    @pytest.mark.asyncio
    async def test_logout_clears_cookie(self, client_e2e, db_session, routes):
        """POST /auth/logout clears the session cookie."""
        user = User(
            id=uuid.uuid4(),
            email="logout-test@example.com",
            name="Logout Test",
            is_active=True,
            role=UserRole.user,
        )
        db_session.add(user)
        await db_session.flush()

        set_auth_cookies(client_e2e, make_auth_cookie(user))
        response = await client_e2e.post(routes.auth_logout)

        assert response.status_code == 204
        # Cookie should be cleared (max-age=0 or deleted).
        set_cookie = response.headers.get("set-cookie", "")
        assert COOKIE_NAME in set_cookie

    @pytest.mark.asyncio
    async def test_unauthenticated_get_me_returns_401(self, client_e2e, routes):
        """GET /api/users/me without cookie returns 401."""
        response = await client_e2e.get(routes.users_me)
        assert response.status_code == 401
