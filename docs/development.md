# Development Workflow

## Purpose

This document describes how to run and validate the local stack. Product behavior, architecture, and delivery scope belong in [specification.md](C:/Users/jiri.janecek1/IdeaProjects/strava_insights/docs/specification.md).

## Services

- `frontend`: React application
- `backend`: FastAPI application
- `worker`: Celery worker
- `beat`: Celery beat scheduler
- `postgres`: PostgreSQL
- `redis`: Redis

## Local Setup

- Create real env files from the committed templates before starting the stack.
- Use Poetry for Python dependency management in `backend` and `worker`.
- Use Docker Compose as the default local runtime and validation environment.

Expected env templates:

- `frontend/.env.template`
- `backend/.env.template`
- `backend/.env.secrets.template`
- `worker/.env.template`
- `worker/.env.secrets.template`
- Log output is written to the Docker console for `backend`, `worker`, and `beat`.
- The backend is started through a small Python Uvicorn runner so application logging remains authoritative in Docker.
- Strava app `client_id` and `client_secret` are no longer provided through service env files; each athlete enters their own app credentials on the landing/login screen and the backend stores them in the database after a successful OAuth callback.

## Commands

Primary command surface:

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

- `.\make.ps1 build`
- `.\make.ps1 up`
- `.\make.ps1 test`
- `.\make.ps1 down`
- `.\make.ps1 build-prod`
- `.\make.ps1 up-prod`
- `.\make.ps1 down-prod`
- `.\make.ps1 logs-prod`

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
- Single-host production deployment guidance lives in [deployment.md](C:/Users/jiri.janecek1/IdeaProjects/strava_insights/docs/deployment.md).
