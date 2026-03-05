"""Shared pytest fixtures for the test suite."""

import asyncio
import logging
import os
import subprocess
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import asyncpg
import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

# Disable rate limiting in tests to avoid 429 when many requests hit the same IP
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

from app.auth.backend import current_active_user, current_admin, current_user, current_user_optional
from app.auth.routes import RouteName as AuthRouteName
from app.database import get_db
from app.main import app
from app.users.models import User, UserRole
from app.users.routes import RouteName as UserRouteName


# Base URL for ASGI test client — host is ignored; requests go to app via ASGITransport.
TEST_CLIENT_BASE_URL = "http://test.server"

_log = logging.getLogger(__name__)


def _get_test_db_name() -> str:
    from app.config import settings

    return settings.postgres_db_test or f"{settings.postgres_db}_test"


async def _ensure_test_db() -> None:
    """Create test database if it does not exist, then run migrations."""
    from app.config import settings

    test_db = _get_test_db_name()
    conn_params = {
        "host": settings.postgres_host,
        "port": int(settings.postgres_port),
        "user": settings.postgres_user,
        "password": settings.postgres_password,
    }

    try:
        await asyncpg.connect(database=test_db, **conn_params)
        _log.info("Test database exists: %s", test_db)
    except asyncpg.InvalidCatalogNameError:
        sys_conn = await asyncpg.connect(database="template1", **conn_params)
        await sys_conn.execute(f'CREATE DATABASE "{test_db}"')
        await sys_conn.close()
        _log.info("Created test database: %s", test_db)

    _log.info("Running migrations on %s", test_db)
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        env={**os.environ, "POSTGRES_DB": test_db},
        cwd=Path(__file__).resolve().parent,
        check=True,
        capture_output=True,
    )


async def _drop_test_db() -> None:
    """Drop the test database after all tests (terminates connections first)."""
    from app.config import settings

    test_db = _get_test_db_name()
    conn_params = {
        "host": settings.postgres_host,
        "port": int(settings.postgres_port),
        "user": settings.postgres_user,
        "password": settings.postgres_password,
    }

    sys_conn = await asyncpg.connect(database="template1", **conn_params)
    await sys_conn.execute(
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = $1 AND pid <> pg_backend_pid()",
        test_db,
    )
    await sys_conn.execute(f'DROP DATABASE IF EXISTS "{test_db}"')
    await sys_conn.close()
    _log.info("Dropped test database: %s", test_db)


def pytest_addoption(parser):
    parser.addoption(
        "--drop-test-db",
        action="store_true",
        default=False,
        help="Drop the test database after the test run",
    )


def pytest_sessionstart(session):
    """Create test database and run migrations before any tests."""
    asyncio.run(_ensure_test_db())


def pytest_sessionfinish(session, exitstatus):
    """Optionally drop the test database after all tests."""
    if session.config.getoption("--drop-test-db", default=False):
        asyncio.run(_drop_test_db())


@pytest.fixture
def routes():
    """API paths via app.url_path_for — app defines paths, tests stay in sync."""

    def users_by_id(user_id: uuid.UUID) -> str:
        return app.url_path_for(UserRouteName.users_get_by_id, id=user_id)

    def users_update_by_id(user_id: uuid.UUID) -> str:
        return app.url_path_for(UserRouteName.users_update_by_id, id=user_id)

    def users_delete_by_id(user_id: uuid.UUID) -> str:
        return app.url_path_for(UserRouteName.users_delete_by_id, id=user_id)

    return SimpleNamespace(
        users_me=app.url_path_for(UserRouteName.users_get_me),
        users_by_id=users_by_id,
        users_update_by_id=users_update_by_id,
        users_delete_by_id=users_delete_by_id,
        auth_me=app.url_path_for(AuthRouteName.auth_me),
        auth_logout=app.url_path_for(AuthRouteName.auth_logout),
        auth_google_callback=app.url_path_for(AuthRouteName.auth_google_callback),
    )


def _get_test_db_url() -> str:
    """Use a separate test database to avoid affecting development data."""
    from app.config import settings

    test_db = settings.postgres_db_test or f"{settings.postgres_db}_test"
    return (
        f"postgresql+asyncpg://{settings.postgres_user}:{settings.postgres_password}"
        f"@{settings.postgres_host}:{settings.postgres_port}/{test_db}"
    )


@pytest.fixture(scope="session")
def test_engine():
    """Session-scoped engine — reused across tests to avoid per-test engine creation."""
    engine = create_async_engine(
        _get_test_db_url(),
        poolclass=NullPool,
        echo=False,
    )
    yield engine
    asyncio.run(engine.dispose())


@pytest.fixture
async def db_session(test_engine):
    """
    Provide an async DB session with transaction rollback for isolation.

    Uses a separate test DB ({postgres_db}_test) to avoid affecting development data.
    NullPool + join_transaction_mode='create_savepoint' so app commits are rolled back.
    """
    async with test_engine.connect() as connection:
        transaction = await connection.begin()

        async with AsyncSession(
            bind=connection,
            expire_on_commit=False,
            autoflush=False,
            join_transaction_mode="create_savepoint",
        ) as session:
            yield session

        await transaction.rollback()


def _unique_email(prefix: str) -> str:
    """Unique email per fixture invocation to avoid conflicts when tests overlap."""
    return f"{prefix}-{uuid.uuid4().hex[:8]}@test.example"


@pytest.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create and return a regular user for tests."""
    user = User(
        id=uuid.uuid4(),
        email=_unique_email("user"),
        name="Test User",
        is_active=True,
        role=UserRole.user,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def test_admin(db_session: AsyncSession) -> User:
    """Create and return an admin user for tests."""
    user = User(
        id=uuid.uuid4(),
        email=_unique_email("admin"),
        name="Test Admin",
        is_active=True,
        role=UserRole.admin,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def client_users(db_session, test_user):
    """HTTP client with current_active_user override for /api/users/me routes."""

    async def override_get_db():
        yield db_session

    async def override_current_active_user():
        return test_user

    app.dependency_overrides[get_db] = override_get_db  # type: ignore[attr-defined]
    app.dependency_overrides[current_active_user] = override_current_active_user  # type: ignore[attr-defined]

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url=TEST_CLIENT_BASE_URL,
    ) as http_client:
        yield http_client

    app.dependency_overrides.clear()  # type: ignore[attr-defined]


@pytest.fixture
async def client_admin(db_session, test_admin):
    """HTTP client with current_admin override for /api/users/{id} admin routes."""

    async def override_get_db():
        yield db_session

    async def override_current_admin():
        return test_admin

    async def override_current_active_user():
        return test_admin

    async def override_current_user():
        return test_admin

    async def override_current_user_optional():
        return test_admin

    app.dependency_overrides[get_db] = override_get_db  # type: ignore[attr-defined]
    app.dependency_overrides[current_active_user] = override_current_active_user  # type: ignore[attr-defined]
    app.dependency_overrides[current_admin] = override_current_admin  # type: ignore[attr-defined]
    app.dependency_overrides[current_user] = override_current_user  # type: ignore[attr-defined]
    app.dependency_overrides[current_user_optional] = override_current_user_optional  # type: ignore[attr-defined]

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url=TEST_CLIENT_BASE_URL,
    ) as http_client:
        yield http_client

    app.dependency_overrides.clear()  # type: ignore[attr-defined]


@pytest.fixture
async def client(db_session, test_user):
    """
    Async HTTP client with overridden get_db, current_active_user, and current_user.

    Uses httpx.AsyncClient so the request runs in the same event loop as fixtures,
    avoiding "attached to a different loop" errors with the async DB session.
    """

    async def override_get_db():
        yield db_session

    async def override_current_active_user():
        return test_user

    async def override_current_user():
        return test_user

    async def override_current_user_optional():
        return test_user

    app.dependency_overrides[get_db] = override_get_db  # type: ignore[attr-defined]
    app.dependency_overrides[current_active_user] = override_current_active_user  # type: ignore[attr-defined]
    app.dependency_overrides[current_user] = override_current_user  # type: ignore[attr-defined]
    app.dependency_overrides[current_user_optional] = override_current_user_optional  # type: ignore[attr-defined]

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url=TEST_CLIENT_BASE_URL,
    ) as http_client:
        yield http_client

    app.dependency_overrides.clear()  # type: ignore[attr-defined]


@pytest.fixture
async def client_unauthenticated(db_session):
    """HTTP client with get_db and current_user_optional=None (unauthenticated view)."""

    async def override_get_db():
        yield db_session

    async def override_current_user_optional():
        return None

    app.dependency_overrides[get_db] = override_get_db  # type: ignore[attr-defined]
    app.dependency_overrides[current_user_optional] = override_current_user_optional  # type: ignore[attr-defined]

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url=TEST_CLIENT_BASE_URL,
    ) as http_client:
        yield http_client

    app.dependency_overrides.clear()  # type: ignore[attr-defined]


@pytest.fixture
async def client_e2e(db_session):
    """
    E2E HTTP client — only get_db overridden (test DB); real cookie-based JWT auth.

    Use set_auth_cookies(client_e2e, make_auth_cookie(user)) before requests.
    """

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db  # type: ignore[attr-defined]

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url=TEST_CLIENT_BASE_URL,
        follow_redirects=False,
    ) as http_client:
        yield http_client

    app.dependency_overrides.clear()  # type: ignore[attr-defined]


@pytest.fixture
def mock_google_oauth():
    """
    Patch oauth.google.authorize_access_token to return fake Google userinfo.

    Allows testing the /auth/google/callback endpoint without hitting Google.
    Yields the fake userinfo dict.
    """
    from app.auth.backend import oauth

    fake_userinfo = {
        "sub": "google-test-sub-123",
        "email": "google-oauth-test@example.com",
        "name": "Google Test User",
        "picture": "https://example.com/photo.jpg",
    }

    with patch.object(
        oauth.google,
        "authorize_access_token",
        new_callable=AsyncMock,
        return_value={"userinfo": fake_userinfo},
    ):
        yield fake_userinfo


def _e2e_user(role: UserRole, name: str, email_prefix: str) -> User:
    """Create a User for E2E tests (not persisted). No password — OAuth only."""
    return User(
        id=uuid.uuid4(),
        email=f"{email_prefix}-e2e-{uuid.uuid4().hex[:8]}@test.example",
        name=name,
        is_active=True,
        role=role,
    )


@pytest.fixture
async def admin_e2e(db_session: AsyncSession) -> tuple[User, dict]:
    """Admin user + auth cookies for E2E tests."""
    from app.tests.helpers import make_auth_cookie

    admin = _e2e_user(UserRole.admin, "E2E Admin", "admin")
    db_session.add(admin)
    await db_session.flush()
    return admin, make_auth_cookie(admin)


@pytest.fixture
async def admin_other_e2e(db_session: AsyncSession) -> tuple[User, User, dict]:
    """Admin user, other regular user, and admin auth cookies for E2E tests."""
    from app.tests.helpers import make_auth_cookie

    admin = _e2e_user(UserRole.admin, "E2E Admin", "admin")
    other = _e2e_user(UserRole.user, "E2E Other", "other")
    db_session.add(admin)
    db_session.add(other)
    await db_session.flush()
    return admin, other, make_auth_cookie(admin)


@pytest.fixture
async def user_e2e(db_session: AsyncSession) -> tuple[User, dict]:
    """Regular user + auth cookies for E2E tests."""
    from app.tests.helpers import make_auth_cookie

    user = _e2e_user(UserRole.user, "E2E User", "user")
    db_session.add(user)
    await db_session.flush()
    return user, make_auth_cookie(user)


@pytest.fixture
async def other_user_e2e(db_session: AsyncSession) -> tuple[User, dict]:
    """A second regular user + auth cookies (for tests needing two users)."""
    from app.tests.helpers import make_auth_cookie

    user = _e2e_user(UserRole.user, "E2E Other User", "other-user")
    db_session.add(user)
    await db_session.flush()
    return user, make_auth_cookie(user)


@pytest.fixture
async def user_other_e2e(db_session: AsyncSession) -> tuple[User, User, dict]:
    """Regular user, other regular user, and user auth cookies for E2E tests."""
    from app.tests.helpers import make_auth_cookie

    user = _e2e_user(UserRole.user, "E2E User", "user")
    other = _e2e_user(UserRole.user, "E2E Other", "other")
    db_session.add(user)
    db_session.add(other)
    await db_session.flush()
    return user, other, make_auth_cookie(user)
