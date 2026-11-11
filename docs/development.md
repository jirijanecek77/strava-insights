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
- SDK retries are disabled; the durable queue handles failures and rate limits. Notes/reviews are capped at 2,048
  completion tokens and seven-day running plans at 4,096. Existing ready notes/plans remain stored when changing provider.
- After dependency changes, run `make build`. After changing the image, key, or model, recreate the worker services:
  `docker compose --env-file .env.secrets up -d worker beat sync-dispatcher`.
- Production uses `.env.production` separately; configure its `LLM_API_KEY` with a Groq key as well.
- To pause generation, clear the key and recreate those services; queued items and existing text remain stored.
- `make ai-notes-enqueue`: queue a note for user `1`'s latest activity (`--count 1`); existing notes are kept.
- `make ai-notes-run`: process at most one pending AI call for user `1` (`--batch-size 1`). Pending running plans get
  the first call; activity notes and period reviews use the remaining budget in larger runs.
- `make ai-plan-replan`: explicitly request and attempt a fresh seven-day running plan for user `1`, even without a
  newly imported activity. Use `make ai-plan-replan AI_USER_ID=2` for another user, or
  `.\make.ps1 ai-plan-replan -AiUserId 2` on Windows. The athlete must exist and be active.
  These shortcuts require a running worker container. Use the CLI commands below for other users or larger batches.
- Queue notes for a user's latest activities: `docker compose --env-file .env.secrets exec worker python -m app.coaching_cli enqueue-latest --user-id <id> --count 3`
- Generate pending plans, notes, and reviews immediately: `docker compose --env-file .env.secrets exec worker python -m app.coaching_cli run --user-id <id> --batch-size 10`
- Request and attempt a new running plan: `docker compose --env-file .env.secrets exec worker python -m app.coaching_cli replan --user-id <id>`
- Print stored plans, notes, and reviews: `docker compose --env-file .env.secrets exec worker python -m app.coaching_cli show --user-id <id>`
- Automatic running plans are requested once per successful import batch containing new running/cycling/e-bike
  activities, including the initial import. Durable intent is recorded alongside the first newly inserted activity;
  a successful retry/later sync releases pending work after partial import failure. No-change syncs, backfills,
  threshold changes, calendar visits, and date rollover do not request plans. Future coverage shrinks during inactivity.
- Planning uses recent local training, thresholds, and prior plans to develop endurance, AeT/AnT, and speed with
  bounded load and recovery. Insufficient running/HR evidence yields `insufficient_data`, not invented targets.
  The application chooses a build/maintain/recover objective before the model assigns workouts. CLI `replan` and
  `show` explain its weekly volume range, running frequency, reason, and review date; the read API includes the
  same objective metadata. Replanning continues the current training block, while new substantial recovery
  evidence can lower its load. Prompt version 2 replaces the earlier broad cutback allowance with objective-specific
  volume/long-run bounds. Existing ready plans remain stored until a new activity or explicit manual replan.
  Each automatic/manual request is durable. Active syncs, missing API configuration, and retry delays may postpone
  the CLI's immediate attempt; its printed status distinguishes queued work from a ready plan. Invalid responses
  retry with validation feedback and stop after five attempts. A manual replan supersedes older pending requests.
- `PLANNING_TIMEZONE` defaults to `Europe/Prague` in both Compose stacks and can be overridden in their environment
  file. The timezone is captured on each request; changing it applies to the next activity-triggered/manual request.
  Normal calendar reads only retrieve stored rows and never call Garmin or the model.

Useful log inspection commands:

- `docker compose --env-file .env.secrets logs backend --tail 200`
- `docker compose --env-file .env.secrets logs worker --tail 200`
- `docker compose --env-file .env.secrets logs beat --tail 200`

## Recorded Activity Splits

- Recorded Garmin laps are fetched once as part of importing each new activity, using the existing Garmin session,
  before coaching is queued. Full-history imports also fetch laps for newly inserted activities.
- There is no separate split task, polling schedule, historical backfill, or retry queue. Refresh and Recalculate All
  fetch splits only for new activities, never for existing activities or stream-only backfills.
- Empty responses and non-authentication failures are stored as `unavailable` without blocking activity import.
  Authentication failures use the normal sync reconnect flow before the new activity is inserted.
- Migration `20261111_0024` preserves existing laps, finalizes old pending rows, and removes `version`,
  `attempt_count`, `next_attempt_at`, and `fetched_at`. The table retains `activity_id`, `status`, and `laps`.
  Stop worker, beat, and sync-dispatcher before deploying this cleanup; start/recreate the backend to apply the
  migration, then recreate the workers and scheduler. Do not run old worker code against the reduced table.
- Legacy source IDs are never used to fetch Garmin laps. Activity-detail reads use stored data only and show
  an unavailable state when splits are absent.
- New activity coaching uses recorded lap distance/duration, average pace or speed, and average HR, without stream
  excerpts or an elevation profile. Missing splits produce an explicit limitation. Existing notes and plans remain
  stored; elevation remains in the chart.

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
