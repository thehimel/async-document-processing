"""Unit tests for app.exceptions."""

import pytest

from app.auth.errors import AuthErrorCode
from app.exceptions import error_detail
from app.users.errors import UserErrorCode


class TestErrorDetail:
    """Tests for error_detail helper."""

    def test_returns_code_and_message(self):
        """Basic structure with code and message."""
        result = error_detail(UserErrorCode.user_not_found, "User not found.")
        assert result == {"code": "user_not_found", "message": "User not found."}

    @pytest.mark.parametrize(
        "code,message,extra,expected_keys",
        [
            (
                AuthErrorCode.insufficient_permissions,
                "Invalid permission.",
                {"context": "admin_only"},
                ["code", "message", "context"],
            ),
            (
                AuthErrorCode.insufficient_permissions,
                "Invalid.",
                {"context": "write_action", "count": 2},
                ["code", "message", "context", "count"],
            ),
        ],
        ids=["single_extra", "multiple_extra"],
    )
    def test_includes_extra_kwargs(self, code, message, extra, expected_keys):
        """Extra kwargs are merged into the dict."""
        result = error_detail(code, message, **extra)
        for key in expected_keys:
            assert key in result
        assert result["code"] == code.value
        assert result["message"] == message
        assert result.get("context") == extra.get("context")
        if "count" in extra:
            assert result["count"] == extra["count"]
