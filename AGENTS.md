/# Repository Guidelines

## Project Structure & Module Organization

This project is being rebuilt as a separate frontend and backend application.

- Frontend: React application for the web UI.
- Backend: FastAPI application for auth, read APIs, and sync orchestration.
- Worker: Celery worker for first import and scheduled synchronization.
- Database: PostgreSQL for persisted application data.
- Cache/Broker: Redis for caching and Celery broker/backend support.

The implementation should follow clean architecture principles:

- keep framework code at the edges
- keep business logic in testable domain/application layers
- isolate infrastructure concerns such as Strava API access, database access, cache, and background jobs
- avoid coupling UI, HTTP handlers, and persistence logic directly

Until the new structure is fully created, treat the specification document as the source of truth for the target layout and responsibilities:

- [specification.md](C:\Users\jiri.janecek1\IdeaProjects\strava_insights\docs\specification.md)

## Build, Test, and Development Commands

The target local development workflow should use Docker for repeatable validation.
Build, deploy, and test workflows should be exposed through simple `make` commands.

Windows is the primary local environment, so command design must keep Windows compatibility in mind.

- Provide a `Makefile` as the main task entrypoint.
- Prefer short, predictable commands such as `make build`, `make up`, `make test`, and `make down`.
- If a Windows-specific wrapper is needed later, keep command names aligned with the `make` targets.
- Avoid requiring long manual command sequences for normal development tasks.

- Every meaningful iteration should be validated locally.
- Every meaningful change should be exercised through local Docker deployment before being considered complete.
- Every code change must include a successful build validation.
- Prefer Docker Compose or an equivalent local orchestration setup for frontend, backend, worker, PostgreSQL, and Redis.

Expected local validation flow:

```bash
make build
make up
make test
```

As the new codebase is created, keep commands documented for:

- frontend install, run, lint, and test
- backend install, run, lint, type-check, and test through Poetry
- worker startup and scheduled job execution through Poetry
- local end-to-end validation through Docker
- full local lifecycle through `make` targets

## Coding Style & Naming Conventions

Use clean, explicit, maintainable code.

- Prefer small, composable units with clear responsibilities.
- Keep domain logic deterministic and easy to test.
- Avoid hidden side effects and framework-driven business logic.
- Use `snake_case` for Python modules, functions, and variables.
- Use `PascalCase` for Python classes and React components.
- Follow Black-compatible Python formatting.
- Keep public interfaces narrow and well defined.

## Testing & Validation Guidelines

Testing is a core project requirement.

- All important business logic must be covered by automated tests.
- Add unit tests for domain logic, transformations, and analytics calculations.
- Add integration tests for API, persistence, sync, and background job behavior.
- Add UI/component or end-to-end coverage for the main user flows.
- Validate performance-sensitive paths, especially dashboard and activity-detail reads.

Minimum expectations for significant changes:

- relevant unit tests added or updated
- relevant integration tests added or updated
- local Docker deployment started successfully
- changed behavior validated in the running stack
- validation available through simple `make` targets
- build validation completed successfully after the change
- `docs/implementation_plan.md` updated to reflect completed work and newly discovered remaining work

Do not treat a code change as complete if it has not been tested and validated locally.

## Architecture Constraints

- Do not place live Strava API calls on the normal UI request path.
- Persist imported Strava data locally and serve the UI from database/cache-backed read models.
- Keep first import and later sync work in background jobs.
- Preserve the analytical intent of the current application, especially on the activity detail page.
- Maintain clear separation between auth, sync, analytics, and read APIs.

## Commit & Pull Request Guidelines

Keep commit subjects short, imperative, and lowercase. Group related changes into one commit. Pull requests should describe:

- the user-visible change
- architecture or data-model impact
- testing performed
- Docker validation performed

Include screenshots for UI changes where useful.

## Configuration Tips

Do not commit filled `.env` files or live credentials.

Expected runtime configuration will include at least:

- `STRAVA_CLIENT_ID`
- `STRAVA_CLIENT_SECRET`
- `MAPY_CZ_API_KEY`
- database connection settings
- Redis connection settings
- frontend/backend application URLs as needed
