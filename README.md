# Strava Insights

This repository is being rebuilt from the legacy Flask/Dash application into a separated frontend, backend, and worker stack.

## New Stack

- `frontend`: React + Vite + Tailwind
- `backend`: FastAPI + Poetry
- `worker`: Celery + Poetry
- `postgres`: PostgreSQL
- `redis`: Redis

The default local workflow is Docker-based and driven through `make`.

## Commands

```bash
make build
make up
make test
make down
```

If `make` is not installed on Windows, use:

```powershell
.\make.ps1 build
.\make.ps1 up
.\make.ps1 test
.\make.ps1 down
```

## Environment

Copy `.env.example` to `.env` and fill in the required values.

## Python Tooling

Python package and environment management for the new backend and worker should use Poetry.

## Notes

- The legacy Flask/Dash code remains in the repository during the migration.
- The new implementation lives in `frontend`, `backend`, and `worker`.
- Product and architecture rules are documented in `docs/specification.md` and `docs/implementation_plan.md`.

