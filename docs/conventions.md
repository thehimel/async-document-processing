# Coding Conventions

Project-wide conventions.

## Module Layout

Each domain module (e.g. `auth`, `users`) follows this structure when applicable:

- `router.py` - HTTP handlers and dependency wiring
- `routes.py` - `RouteName` enum for `url_path_for`
- `schemas.py` - Pydantic request/response models
- `models.py` - SQLAlchemy ORM models
- `errors/` - Domain-specific error handling (`types.py`, `handlers.py`)
- `tests/` - Tests colocated with the domain

## REST

- `POST` create endpoints return `201 Created`
- `DELETE` endpoints return `204 No Content` when no response body is needed
- Use `response_model` on endpoints
- Use `id` path params as `/{id}`

## Authentication

- `Depends(current_active_user)` for authenticated routes
- `Depends(current_admin)` for admin-only routes
- `Depends(current_user_optional)` for routes that allow anonymous access

## Database

- Use async SQLAlchemy (`AsyncSession`) with `Depends(get_db)`
- Manage schema with Alembic migrations
- Import all models in `alembic/env.py` so `autogenerate` detects schema changes

## Error Handling

- Register exception handlers at startup in `app/main.py`
- Keep domain exceptions in `app/<domain>/errors/`
- Return structured `detail` payloads

## Testing

- Shared fixtures live in [`conftest.py`](../conftest.py)
- Domain tests live in `app/<domain>/tests/`
- Use the `routes` fixture and `app.url_path_for(...)`; do not hardcode API paths
- Test database uses `{POSTGRES_DB}_test` (or `POSTGRES_DB_TEST`)

## API Collection

- `bruno/` mirrors API structure (`auth/`, `users/`)
- Use `{{host}}`, `{{users}}`, and `{{auth}}` from Bruno environment files
