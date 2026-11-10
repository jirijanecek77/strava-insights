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
  `uv lock` from the affected service directory after editing its `pyproject.toml` and commit the updated `uv.lock`.
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

- `make build`
- `make up`
- `make deploy` (build, then up)
- `make test`
- `make down`

Optional production deployment command surface:

- `make build-prod`
- `make up-prod`
- `make down-prod`
- `make logs-prod`

Windows fallback when `make` is unavailable:

- `.\make.ps1 build`
- `.\make.ps1 up`
- `.\make.ps1 test`
- `.\make.ps1 down`
- `.\make.ps1 build-prod`
- `.\make.ps1 up-prod`
- `.\make.ps1 down-prod`
- `.\make.ps1 logs-prod`

AI coaching:

- Set `LLM_API_KEY` in `.env.secrets` to a Groq API key. The worker uses the official `groq` Python SDK with
  `openai/gpt-oss-120b` by default; override it with `LLM_MODEL` in `.env.secrets` or the shell.
  Timeout and coaching batch/poll settings live in `docker-compose.yml`. Without a key, generation is skipped.
- SDK retries are disabled; the durable coaching queue handles failures and rate limits. Each response is capped at
  2,048 completion tokens. Existing ready notes are preserved when changing provider.
- After dependency changes, run `make build`. After changing the image, key, or model, recreate the worker services:
  `docker compose --env-file .env.secrets up -d worker beat sync-dispatcher`.
- Production uses `.env.production` separately; configure its `LLM_API_KEY` with a Groq key as well.
- To pause generation, clear the key and recreate those services; queued items and existing text remain stored.
- `make ai-notes-enqueue`: queue a note for user `1`'s latest activity (`--count 1`); existing notes are kept.
- `make ai-notes-run`: process at most one pending activity note or period review for user `1` (`--batch-size 1`).
  Both shortcuts require a running worker container. Use the CLI commands below for other users or larger batches.
- Queue notes for a user's latest activities: `docker compose --env-file .env.secrets exec worker python -m app.coaching_cli enqueue-latest --user-id <id> --count 3`
- Generate pending notes and reviews immediately: `docker compose --env-file .env.secrets exec worker python -m app.coaching_cli run --user-id <id> --batch-size 10`
- Print stored notes and reviews: `docker compose --env-file .env.secrets exec worker python -m app.coaching_cli show --user-id <id>`

Useful log inspection commands:

- `docker compose --env-file .env.secrets logs backend --tail 200`
- `docker compose --env-file .env.secrets logs worker --tail 200`
- `docker compose --env-file .env.secrets logs beat --tail 200`

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
