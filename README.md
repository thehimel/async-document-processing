# Core

[![Python](https://img.shields.io/badge/Python-3.14+-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Pydantic](https://img.shields.io/badge/Pydantic-E92063?logo=pydantic&logoColor=white)](https://docs.pydantic.dev/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-1a1a1a?logo=sqlalchemy&logoColor=white)](https://www.sqlalchemy.org/)
[![Alembic](https://img.shields.io/badge/Alembic-Migrations-000000?logo=alembic&logoColor=white)](https://alembic.sqlalchemy.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![uv](https://img.shields.io/badge/uv-Package%20Manager-00C853)](https://docs.astral.sh/uv/)
[![Ruff](https://img.shields.io/badge/Ruff-linter-FFE873?logo=ruff&logoColor=000)](https://docs.astral.sh/ruff/)
[![Vercel](https://img.shields.io/badge/Vercel-Deploy-000000?logo=vercel&logoColor=white)](https://vercel.com/)

## Tech Stack

- **Framework:** FastAPI
- **Database:** PostgreSQL (async via asyncpg)
- **ORM:** SQLAlchemy 2.0 (async)
- **Auth:** Authlib (Google OAuth), JWT in httpOnly cookie
- **Rate limiting:** slowapi

## Features

- **Auth** — Google OAuth, session cookie, logout
- **Users** — `GET /me`; admin CRUD for users

## Prerequisites

- Python 3.14+
- PostgreSQL
- Docker (optional, for running PostgreSQL)

## Quick Start

### 1. Clone and install

```shell
uv sync
```

### 2. Configure environment

Copy `.env.example` to `.env` and set required variables:

```shell
cp .env.example .env
```

Required: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `JWT_SECRET_KEY`, `SESSION_SECRET_KEY`. Generate secrets with `openssl rand -hex 32`.

### 3. Start PostgreSQL

```shell
docker compose up -d
```

### 4. Run migrations

```shell
alembic upgrade head
```

### 5. Start the API

```shell
uv run uvicorn app.main:app --reload
```

API: http://localhost:8000  
Docs: http://localhost:8000/docs

## Commands

| Command | Purpose |
|---------|---------|
| `uv sync` | Install dependencies (from pyproject.toml) |
| `uv run uvicorn app.main:app --reload` | Run API (dev) |
| `alembic upgrade head` | Apply migrations |
| `alembic revision --autogenerate -m "message"` | Create migration |
| `pytest` | Run tests |
| `pytest -n auto` | Run tests in parallel (pytest-xdist) |
| `pytest --drop-test-db` | Run tests and drop test DB after |
| `ruff check .` | Lint |
| `ruff format .` | Format |

See [docs/commands.md](docs/commands.md) for Docker, pre-commit, and more.

## API Overview

Interactive API docs: http://localhost:8000/docs

## Testing

Tests use a separate DB (`{postgres_db}_test`). Migrations run automatically before tests.

```shell
pytest -v
pytest -n auto   # Parallel execution (pytest-xdist)
```

Unit, integration, E2E, security, and smoke tests. See [docs/commands.md](docs/commands.md#pytest) for Pytest commands.
