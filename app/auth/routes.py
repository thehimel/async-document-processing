"""Route names for auth endpoints."""

from enum import StrEnum


class RouteName(StrEnum):
    auth_google = "auth_google"
    auth_google_callback = "auth_google_callback"
    auth_me = "auth_me"
    auth_logout = "auth_logout"
