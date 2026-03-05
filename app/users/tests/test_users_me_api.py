"""API integration tests for GET /api/users/me."""

import pytest


class TestUsersMeAPI:
    """Tests for the /me self-service endpoint."""

    @pytest.mark.asyncio
    async def test_get_me_returns_200(self, client_users, test_user, routes):
        """GET /me returns current user."""
        response = await client_users.get(routes.users_me)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_user.id)
        assert data["email"] == test_user.email
        assert data["role"] == test_user.role.value
        assert data["is_active"] is True
        assert data["name"] == test_user.name
