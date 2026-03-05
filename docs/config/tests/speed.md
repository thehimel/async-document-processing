# Test Speed Optimizations

Notes on how we increased pytest suite speed.

---

## Dependencies

From [pyproject.toml](../../../pyproject.toml):

| Package | Purpose |
|---------|---------|
| `pytest` | Test framework |
| `pytest-asyncio` | Async test support |
| `pytest-xdist` | Parallel execution (`-n auto`) |

Run `uv sync` to install.

---

## Performance (128+ tests)

| Configuration | Time | Notes |
|---------------|------|-------|
| Before (per-test engine) | ~5.0 s | Each test created/disposed its own engine |
| After (session-scoped engine) | ~4.7 s | **~6% faster** |
| With `-n auto` (parallel) | ~5.4 s | Slower on small suite; overhead outweighs gains |

*Times are approximate; run `pytest --durations=10` to measure on your machine.*

---

## Summary

| Optimization | Effect |
|--------------|--------|
| Session-scoped engine | Reuse SQLAlchemy engine across tests instead of creating/disposing per test |
| pytest-xdist | Optional parallel execution across CPU cores |
| Quiet mode (`-q`) | Less output, slightly faster I/O |

---

## 1. Session-Scoped Engine

**Problem:** Each test using `db_session` was creating a new `AsyncEngine`, connecting, running the test, then disposing the engine. With ~50+ DB-backed tests, that meant 50+ engine create/dispose cycles.

**Solution:** A session-scoped `test_engine` fixture in [conftest.py](../../../conftest.py) creates the engine once per session (or per worker with `-n auto`). Each test still gets its own connection and transaction via `db_session` for isolation.

---

## 2. pytest-xdist (Parallel Execution)

**Install:** `pytest-xdist` is in [pyproject.toml](../../../pyproject.toml).

**Usage:** `pytest -n auto` (workers = CPU count) or `pytest -n 4` (fixed workers).

**Caveat:** On small suites (~128 tests), parallel can be slightly slower due to worker spawn overhead and DB connection contention. Use when the suite grows or for CI with many cores.

---

## 3. Commands

All commands run from the project root: `pytest -q` (quiet), `pytest --durations=10` (slowest tests), `pytest -n auto` (parallel), `pytest -q -n auto` (quiet + parallel).

---

## References

- [commands.md](../../commands.md) — Pytest commands and "Faster runs" section
- [conftest.py](../../../conftest.py) — `test_engine`, `db_session` fixtures
