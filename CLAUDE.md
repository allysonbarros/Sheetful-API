# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Sheetful API is a FastAPI-based REST wrapper around Google Sheets (via `gspread`), turning any Google Sheet into a CRUD REST API. It is a Python port of the original Node.js Sheetful project and aims for API compatibility with it.

## Commands

Most common development tasks are wrapped in the `Makefile`:

```bash
make setup          # Create .venv and install requirements
make dev            # Run via python main.py (uvicorn with reload if DEBUG=true)
make run            # Run with uvicorn main:app --host 0.0.0.0 --port 8000
make test           # pytest
make test-cov       # pytest with coverage (HTML + terminal)
make format         # black + isort
make lint           # flake8 + mypy
make docker-build   # Build the Docker image
make docker-compose-up
```

Run a single test: `pytest path/to/test_file.py::TestClass::test_name`

### Known Makefile gotcha
The `lint`, `format`, and `format-check` targets reference `server.py` and `dev_utils.py`, which **do not exist** in this repo. Running those targets as-is will fail. When linting/formatting, either scope commands to the real paths:

```bash
black app/ main.py
isort app/ main.py
flake8 app/ main.py
mypy app/ main.py
```

...or fix the Makefile. Similarly, `make validate` calls a missing `dev_utils.py`, and `pytest.ini_options.testpaths` in `pyproject.toml` points at a `tests/` directory that doesn't exist yet — new tests need to live under `tests/` (or you'll need to adjust `testpaths`).

### Environment
Copy `.env.example` to `.env` and configure before running. At least one of `GOOGLE_API_KEY` or `GOOGLE_SERVICE_ACCOUNT_KEY` **must** be set — `Settings.validate_config()` is called during app startup in `app/main.py:create_app`, so the app will refuse to boot without credentials. Other env vars: `PORT` (default 8000), `HOST` (default 0.0.0.0), `DEBUG` (enables uvicorn reload), `LOG_LEVEL`.

## Architecture

### Entry points
- `main.py` (root): thin shim that imports `app` from `app.main` and runs uvicorn. Uvicorn is told to load `main:app`, so this file is both the script entry point *and* the ASGI module target.
- `app/main.py`: `create_app()` builds the FastAPI instance, validates settings, adds CORS, and mounts routers. The module-level `app = create_app()` is what uvicorn imports.

### Layering
The codebase follows a clean three-layer split. Respect it when adding features:

1. **Routes (`app/api/`)** — FastAPI routers (`health.py`, `sheets.py`). These are thin: parse/validate params, delegate to the service, log, wrap unexpected exceptions as HTTP 500. Routers are aggregated in `app/api/__init__.py` and mounted in `app/main.py`. Shared route helpers (authenticated worksheet lookup, request/success logging) live in `app/api/utils.py`.

2. **Services (`app/services/sheets.py`)** — `GoogleSheetsService` owns *all* Google Sheets interaction. A module-level singleton `sheets_service` is imported by routes. Key concerns handled here (not in routes):
   - Auth via `_get_client()` — OAuth2 bearer token (from `x-google-access-token` header) takes precedence over the `GOOGLE_API_KEY` env var (which is read-only).
   - Sheet resolution in `get_sheet()` — `sheet_id` is tried as numeric gspread ID → index → title, in that order. Route params are typed as `str` for this reason.
   - Header hygiene in `_get_safe_headers()` / `_get_all_records_safe()` — gspread's `get_all_records()` throws on empty or duplicate headers; the service falls back to reading raw rows and synthesizing `Column_N` / suffixed header names. Any new read path should go through these helpers, not call gspread directly.
   - Row indexing convention: the API exposes **0-based row indices** (excluding the header). Internally this maps to gspread's 1-based cells as `row_id + 2` (+1 for 1-indexing, +1 for the header row). See `update_row` / `update_rows_bulk`.

3. **Models (`app/models.py`)** — Pydantic v2 models for request/response shapes. `SheetRow` uses `extra="allow"` because sheet columns are arbitrary. `SheetInfo` uses camelCase aliases (`sheetId`, `headerValues`, etc.) to match the Node.js API's response shape — preserve this when changing it.

### Config (`app/config.py`)
Plain class-based `Settings` populated from env via `python-dotenv` — not `pydantic-settings`. The global `settings` instance is imported everywhere; don't instantiate a second one.

### Error handling convention
Routes catch `HTTPException` and re-raise, catch everything else and wrap as 500. The service layer raises `HTTPException` directly with appropriate status codes (401 auth, 400 document access, 404 sheet/row not found, 500 otherwise). Custom exceptions `GoogleSheetsAuthError` / `GoogleSheetsNotFoundError` are defined in `app/services/sheets.py` but currently unused outside the module.

### Route ordering gotcha
In `app/api/sheets.py`, `/{document_id}/{sheet_id}/info` is declared **before** `/{document_id}/{sheet_id}/{row_id}` so that `info` isn't swallowed by the `row_id: int` path. Keep this order when adding new sub-routes — or use more specific prefixes.

## Code style

- Python 3.11, black (line-length 88), isort (`profile = "black"`, `known_first_party = ["app"]`).
- mypy is configured strictly (`disallow_untyped_defs`, `no_implicit_optional`, etc.) with `gspread.*` and `google.*` ignored. New code should be fully type-annotated.
- pytest is configured with `asyncio_mode = "auto"` — async test functions don't need an explicit marker.
