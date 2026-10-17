# Development Workflow

## Purpose

This document describes how to run and validate the local stack. Product behavior, architecture, and delivery scope belong in [specification.md](specification.md).

## Services

- `frontend`: React application
- `backend`: FastAPI application
- `worker`: Celery worker
- `beat`: Celery beat scheduler
- `sync-dispatcher`: durable-outbox publisher for Celery sync commands
- `postgres`: PostgreSQL
- `redis`: Redis

## Local Setup

- Create the root `.env.secrets` from `.env.secrets.template` before starting the stack.
- Use uv for Python dependency management in `backend` and `worker`. Images install with `uv sync --locked`, so run
  `make lock` (or `.\make.ps1 lock`) after editing a `pyproject.toml` and commit the updated `uv.lock`.
- Use Docker Compose as the default local runtime and validation environment.

Environment configuration:

- Non-secret service configuration is inlined in the `environment` blocks of `docker-compose.yml` and
  `docker-compose.prod.yml`; the worker, beat, and sync-dispatcher services share one `x-worker-environment` block.
- No compose service uses `env_file`. Secrets (`SESSION_SECRET_KEY`, `LLM_API_KEY`, `VITE_MAPYCZ_API_KEY`) are
  interpolated from the root `.env.secrets`, which `make`/`make.ps1` pass as `docker compose --env-file .env.secrets`.
  When calling `docker compose` directly, pass `--env-file .env.secrets` too.
- Log output is written to the Docker console for `backend`, `worker`, and `beat`.
- The backend is started through a small Python Uvicorn runner so application logging remains authoritative in Docker.
- Garmin credentials are not provided through service env files; each athlete enters their Garmin email and password on the landing/login screen and the backend stores only encrypted session tokens after validation.

## Commands

Primary command surface:

- `make lock`
- `make build`
- `make up`
- `make test`
- `make down`

Optional production deployment command surface:

- `make build-prod`
- `make up-prod`
- `make down-prod`
- `make logs-prod`

Windows fallback when `make` is unavailable:

- `.\make.ps1 lock`
- `.\make.ps1 build`
- `.\make.ps1 up`
- `.\make.ps1 test`
- `.\make.ps1 down`
- `.\make.ps1 build-prod`
- `.\make.ps1 up-prod`
- `.\make.ps1 down-prod`
- `.\make.ps1 logs-prod`

AI coaching:

- Set `LLM_API_KEY` in `.env.secrets` to a Google AI Studio API key; model and endpoint settings live in
  `docker-compose.yml`. Without a key, coaching generation is skipped.
- After changing the key, recreate the worker services: `docker compose --env-file .env.secrets up -d worker beat`.
- Queue notes for a user's latest activities: `docker compose exec worker python -m app.coaching_cli enqueue-latest --user-id <id> --count 3`
- Generate pending notes and reviews immediately: `docker compose exec worker python -m app.coaching_cli run --user-id <id> --batch-size 10`
- Print stored notes and reviews: `docker compose exec worker python -m app.coaching_cli show --user-id <id>`

Useful log inspection commands:

- `docker compose logs backend --tail 200`
- `docker compose logs worker --tail 200`
- `docker compose logs beat --tail 200`

## Validation Expectations

- Run `make build` for every meaningful code change.
- After each meaningful fix, run the relevant automated tests.
- Prefer validating behavior through the Docker stack rather than ad hoc host-only execution.
- If a change affects a running service, restart or rebuild the affected Docker service or services before validating the behavior in the stack.
- Do not treat database deletion or recreation as a normal development workflow.
- When persistence changes are needed, add and run migrations.

## Notes

- The legacy Flask/Dash application remains in place during the rebuild.
- The new application lives in `frontend`, `backend`, and `worker`.
- Single-host production deployment guidance lives in [deployment.md](deployment.md).
