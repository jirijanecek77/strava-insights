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

Frontend-only validation when Docker is unavailable or service startup is explicitly excluded:

```powershell
cd frontend
npm.cmd ci # Only when dependencies are not already installed.
npm.cmd run test -- --run
npm.cmd run build
```

These commands run tests and compile the frontend without starting application services. On other platforms,
use `npm` instead of `npm.cmd`.

Python tests without Docker (from the repository root):

```powershell
uv sync --project worker --locked --system-certs
uv sync --project backend --locked --system-certs
Push-Location worker
.\.venv\Scripts\python.exe -m pytest tests -p no:cacheprovider
Pop-Location
Push-Location backend
.\.venv\Scripts\python.exe -m pytest tests -p no:cacheprovider
Pop-Location
```

Both complete Python suites use mocked database sessions and repositories. Tests must not open PostgreSQL,
SQLite, or another physical database, read the application database URL for test storage, or create/drop schemas.
No database marker, exclusion filter, or service startup is required. Migration and PostgreSQL-specific query contracts
are checked with mocked operations or offline SQL compilation; those checks do not connect to a database.
Backend HTTP tests keep real request validation, serialization, analytics and application services while mocking their
repository boundaries. Worker import/backfill/planning tests mock persistence and retain their behavioral assertions.
The worker's `conftest.py` only establishes the import path; it does not hide or skip database-dependent tests.
Use `--cache-dir .venv/uv-cache` for uv when the default user cache is not writable. If validation is restricted to
only tests, run these test commands and the frontend tests without a build or service restart.

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
- Replace the latest five activity notes and the latest eligible stored week/month reviews:

  ```powershell
  docker compose --env-file .env.secrets exec worker python -m app.coaching_cli regenerate-latest --user-id 1 --activity-count 5 --week-count 1 --month-count 1
  docker compose --env-file .env.secrets exec worker python -m app.coaching_cli run --user-id 1 --batch-size 20
  ```

  `regenerate-latest` only queues work, committing all three levels together without calling the provider or
  requesting a running plan. Defaults are five activities, one stored week and one stored month. Counts are
  independent, each from 0 to 100, and at least one must be positive; zero skips that level. Activities are selected
  by newest start time; reviews by newest period start, independently of the selected activities. Existing text and
  saved evaluations remain visible until a replacement succeeds. Retry counters/delays/errors are reset, while
  actively generating rows and locked reviews are skipped. Missing activity notes are created; this explicit
  period selection only requeues stored reviews. Normal generation also plans affected weeks/months from changed
  child results. The `run` budget is shared with any other queued notes, reviews and running plans for that user;
  rate limits/retry delays may require a later run, or the background worker will continue processing.
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
- There is no separate split task, polling schedule, or retry queue. Refresh and Recalculate All
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
- Each normalized lap also stores nullable `elevation_gain_meters` and `elevation_loss_meters` from Garmin. Detail
  tooltips and activity coaching use these same values, including genuine zeros, without a local estimate fallback.
  Old laps remain readable with missing totals. The existing JSONB column requires no schema migration.

### Explicit Historical Split Backfill

The following is an operator action that reads Garmin and writes the existing database. It is never run by ordinary
refresh, Recalculate All, coaching, or UI reads. Finish active syncs and stop worker, beat, and sync-dispatcher before
running it to avoid simultaneous session refreshes or coaching generation. Keep PostgreSQL and Redis available.
After deploying the updated images, run from the repository root:

```powershell
docker compose --env-file .env.secrets run --rm --no-deps worker python -m app.splits_cli backfill --user-id 1 --batch-size 100 --delay-seconds 1 --after-id 0
```

- The command processes the user's entire stored Garmin history in ID order; the batch size limits each database
  read, not the total number of activities. Repeat for each athlete as needed. Legacy activity IDs are excluded.
- Existing laps must match by number and distance boundaries. Only their elevation totals are enriched; other
  metrics stay intact. Missing splits are populated from a valid response. Empty responses cannot erase recorded laps,
  and omitted provider totals cannot erase previously known totals. Genuine zero values can replace previous totals.
- Each activity commits independently. Progress and errors print `--after-id N`; use the last reported cursor to resume.
  Errors stop without advancing past the failed activity. Resolve boundary mismatches before resuming. Reconnect Garmin
  if authentication is rejected. Refreshed session tokens are encrypted and saved during processing.
- Transient requests retry at most three times with backoff. Honor numeric/date `Retry-After`; a requested cooldown
  longer than 60 seconds stops the command so it can be resumed later instead of retrying early.
- Caches are invalidated after successful activity writes. Existing notes, reviews, plans, and activity totals are
  retained; no AI calls are queued. Rebuild local evidence with the existing `prepare-evidence` command below if needed,
  then restart worker, beat, and sync-dispatcher. Evidence fingerprints also refresh changed facts on their next use.

## Coaching Evidence and Period Reviews

- Migration `20261113_0025` adds `activity_coaching_evidence` and nullable period-review `metrics`; it preserves all
  existing activities and coaching text. Stop worker/beat/sync-dispatcher, build, run
  `docker compose --env-file .env.secrets run --rm backend python -m alembic upgrade head`, then recreate backend,
  frontend, worker, beat, and sync-dispatcher. Use `python -m alembic` so the backend package is importable.
- Evidence is calculated locally for activity coaching and reused by source fingerprint. Week/month context reads
  saved child evaluations only; it never prepares activity evidence or reads source streams. It is
  independent of model configuration and note availability. Populate older facts without Garmin/AI calls:
  `docker compose --env-file .env.secrets exec worker python -m app.coaching_cli prepare-evidence --user-id 1 --after-id 0 --limit 100`.
  Repeat with the printed `--after-id` to resume; the maximum batch is 1,000. Context preparation refreshes changed facts.
- Inspect context size without an AI call:
  `docker compose --env-file .env.secrets exec worker python -m app.coaching_cli inspect-context --user-id 1 --period-type month --period-start 2026-11-01`.
  Counts estimate the actual compact provider payload at four characters/token, including the system prompt.
  Period inspection is read-only and does not prepare evidence, query Garmin, or call the model.
- Existing ready notes/reviews remain visible. Explicitly queue a bounded historical review update:
  `docker compose --env-file .env.secrets exec worker python -m app.coaching_cli regenerate-periods --user-id 1 --period-type month --date-from 2026-11-01 --date-to 2026-11-01 --limit 1`.
  The dates filter period starts inclusively; `--period-type` is optional and `--limit` is capped at 100. Generating
  rows are skipped, old text is preserved, and this command queues work without calling the provider. Run the existing
  coaching `run` command to consume it; the background queue may also process it. That step sends context to the
  configured model. Deployment alone does not queue a mass replacement of legacy ready reviews.
- Activity prompt version 6 describes endurance/tempo stimulus, Garmin lap elevation totals, local terrain coverage,
  and qualified fatigue evidence. Period prompt
  version 4 uses the activity-to-week-to-month hierarchy, with at most seven preceding activity summaries and three
  preceding same-type period reviews. Week metrics store date-grouped numeric handoffs outside the provider payload.
- The hierarchy reuses existing JSON storage (`activity_coaching_evidence.facts.evaluation` and period
  `metrics.hierarchy`),
  so no additional migration is required beyond `20261113_0025`. Successful activity prose and its numeric handoff are
  published together; failed replacement attempts keep the previous consistent result. Old activity text is not
  regenerated
  automatically. Ready legacy weekly text can retain its prose while receiving a handoff from already cached facts.

## Validation Expectations

- Run `make build` for every meaningful code change; for frontend-only changes without Docker, use the frontend
  test and production-build commands above.
- After each meaningful fix, run the relevant automated tests.
- Prefer validating behavior through the Docker stack rather than ad hoc host-only execution.
- If a change affects a running service, restart or rebuild the affected Docker service or services before validating the behavior in the stack.
- Do not treat database deletion or recreation as a normal development workflow.
- When persistence changes are needed, add and run migrations.

## Notes

- The legacy Flask/Dash application remains in place during the rebuild.
- The new application lives in `frontend`, `backend`, and `worker`.
- Single-host production deployment guidance lives in [deployment.md](deployment.md).
