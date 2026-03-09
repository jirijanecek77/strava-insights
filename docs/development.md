# Development Workflow

## Stack

- `frontend`: React + Vite + Tailwind
- `backend`: FastAPI + Poetry
- `worker`: Celery + Poetry
- `postgres`: PostgreSQL
- `redis`: Redis

## Commands

- `make build`
- `make up`
- `make test`
- `make down`

Windows fallback when `make` is not installed:

- `.\make.ps1 build`
- `.\make.ps1 up`
- `.\make.ps1 test`
- `.\make.ps1 down`

## Notes

- The legacy Flask/Dash app remains in place during the rebuild.
- The new application lives in `frontend`, `backend`, and `worker`.
- The Docker Compose stack is the default local entrypoint for validation.
- Python dependency management for `backend` and `worker` should use Poetry rather than direct `pip` installs.
