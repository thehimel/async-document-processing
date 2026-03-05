# Async SQLAlchemy + Alembic Setup

How async SQLAlchemy with Alembic is set up using `asyncpg` as the PostgreSQL driver.

---

## Overview: Sync vs Async

| Aspect           | Sync setup                   | Async setup                          |
|------------------|------------------------------|--------------------------------------|
| Driver           | `psycopg2-binary`            | `asyncpg`                            |
| URL scheme       | `postgresql+psycopg2://`     | `postgresql+asyncpg://`              |
| Engine factory   | `create_engine`              | `create_async_engine`                |
| Session class    | `Session`                    | `AsyncSession`                       |
| Session factory  | `sessionmaker`               | `async_sessionmaker`                 |
| `get_db()`       | sync generator               | async generator                      |
| Alembic `env.py` | sync `run_migrations_online` | async via `asyncio.run` + `run_sync` |

---

## How It Works

**Dependencies:** `asyncpg`, `sqlalchemy`, `alembic` in `pyproject.toml`. Run `uv sync`.

**`app/database.py`:** Builds `DATABASE_URL` from settings (`postgresql+asyncpg://...`). Uses `create_async_engine` with `pool_pre_ping=True` and `echo` from `SQL_ECHO`. `async_sessionmaker` creates `AsyncSessionLocal` with `expire_on_commit=False` (important for async — prevents lazy-load errors after commit). `get_db` is an async generator that yields a session.

**Models:** Inherit from `Base`; use `Mapped`/`mapped_column` for SQLAlchemy 2 style. Import all models in `alembic/env.py` so autogenerate detects schema changes.

**`alembic/env.py`:** Overrides `sqlalchemy.url` from settings at runtime. Uses `asyncio.run(run_async_migrations())` to bridge async engine into sync Alembic; `run_sync(do_run_migrations)` runs the migration inside an async connection. Offline mode uses `literal_binds` without a live connection.

**`alembic.ini`:** Placeholder URL uses `postgresql+asyncpg://`; the real URL comes from `env.py`.

---

## Route Handlers

Use `session: AsyncSession = Depends(get_db)` in route handlers. Use `await session.execute(select(...))` instead of sync `session.query()`.

---

## Alembic CLI

| Command | Purpose |
|---------|---------|
| `alembic revision --autogenerate -m "message"` | Create migration from model changes |
| `alembic upgrade head` | Apply all pending migrations |
| `alembic downgrade -1` | Roll back one revision |
| `alembic current` | Show current revision |
| `alembic history` | List migration history |

---

## Data Flow

```
.env → app/config.py (pydantic Settings)
     → app/database.py (async engine, Base, AsyncSessionLocal, get_db)
     → app/*/models.py (inherit Base)

alembic/env.py: imports Base and models, builds URL from settings,
                asyncio.run → run_sync → migrations
```

---

## References

- [SQLAlchemy — Asyncio Extension](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Alembic — Async Migration Support](https://alembic.sqlalchemy.org/en/latest/cookbook.html#using-asyncio-with-alembic)
- [asyncpg — GitHub](https://github.com/MagicStack/asyncpg)
