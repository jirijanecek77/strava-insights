# Strava Insights Implementation Plan

## Summary

This plan turns [specification.md](C:\Users\jiri.janecek1\IdeaProjects\strava_insights\docs\specification.md) into a trackable delivery sequence. The new application will be built greenfield alongside the current Flask/Dash app using `Vite + React`, `FastAPI`, `Celery`, `PostgreSQL`, `Redis`, Docker, and simple `make` commands.

## Progress Rules

- Mark items complete only after code is implemented, tested, and validated.
- Every code change must include a successful `make build`.
- Validation should happen through Docker-based commands, not ad hoc local-only steps.

## Phase 1: Foundation

- [ ] Create top-level structure for `frontend`, `backend`, `worker`, and Docker/infrastructure files.
- [ ] Add `Makefile` with `make build`, `make up`, `make test`, and `make down`.
- [ ] Add Docker Compose stack for frontend, backend, worker, PostgreSQL, and Redis.
- [ ] Initialize React frontend with Vite and Tailwind.
- [ ] Initialize FastAPI backend with clean architecture folder layout.
- [ ] Initialize Celery worker and shared configuration.
- [ ] Add environment configuration templates for Strava, Mapy.cz, PostgreSQL, and Redis.
- [ ] Verify the stack builds successfully with `make build`.
- [ ] Verify the stack starts successfully with `make up`.

## Phase 2: Backend Core

- [ ] Add SQLAlchemy models and Alembic migrations for:
- [ ] `users`
- [ ] `oauth_tokens`
- [ ] `activities`
- [ ] `activity_streams`
- [ ] `period_summaries`
- [ ] `best_efforts`
- [ ] `activity_best_efforts`
- [ ] `sync_jobs`
- [ ] `sync_checkpoints`
- [ ] Add required indexes from `specification.md`.
- [ ] Implement Strava OAuth backend flow.
- [ ] Implement secure token persistence.
- [ ] Implement current-user/profile endpoint.
- [ ] Implement sync-status endpoint.
- [ ] Add Redis-backed caching utilities.
- [ ] Add backend unit and integration test scaffolding.

## Phase 3: Sync and Import Pipeline

- [ ] Implement first-login full historical import job.
- [ ] Implement daily incremental sync job.
- [ ] Implement sync checkpoint logic to fetch only new activities after initial import.
- [ ] Persist normalized activity metadata.
- [ ] Persist activity streams required for detail views.
- [ ] Persist sync job status and progress.
- [ ] Invalidate or refresh affected cache entries after sync.
- [ ] Ensure standard read endpoints do not call Strava synchronously.
- [ ] Add tests for first import and incremental sync behavior.

## Phase 4: Analytics Port

- [ ] Port activity detail derivations from the current app:
- [ ] moving-average heart rate
- [ ] moving-average speed
- [ ] derived running pace
- [ ] smoothed running pace
- [ ] slope calculation
- [ ] running interval and pace-zone analysis
- [ ] Implement summary aggregation for dashboard KPIs.
- [ ] Implement monthly, yearly, and rolling-period comparisons.
- [ ] Implement best-effort calculations.
- [ ] Store or precompute period summaries needed for fast reads.
- [ ] Add tests for analytics calculations and aggregations.

## Phase 5: API Surface

- [ ] Implement `/auth/*` endpoints.
- [ ] Implement `/me` endpoint.
- [ ] Implement `/sync/status` endpoint.
- [ ] Implement `/dashboard` endpoint.
- [ ] Implement `/trends` and `/comparisons` endpoints.
- [ ] Implement `/activities` list endpoint with sport and date filters.
- [ ] Implement `/activities/{id}` detail endpoint.
- [ ] Implement `/best-efforts` endpoint.
- [ ] Ensure activity detail payload includes:
- [ ] metadata and KPI values
- [ ] map bounds and route polyline
- [ ] pace or speed series
- [ ] heart rate series
- [ ] elevation series
- [ ] slope series
- [ ] running interval analysis when applicable
- [ ] Add integration tests for all core read endpoints.

## Phase 6: Frontend Application

- [ ] Implement landing/login screen.
- [ ] Implement sync/import status screen or state.
- [ ] Implement dashboard screen.
- [ ] Implement calendar screen.
- [ ] Implement activity list screen.
- [ ] Implement activity detail screen.
- [ ] Implement best efforts screen.
- [ ] Implement settings/profile screen.
- [ ] Add shared sport-type and date-range filters.
- [ ] Integrate Mapy.cz on the activity detail page.
- [ ] Render the activity detail graph with pace/speed, heart rate, elevation, and slope.
- [ ] Add hover-linked map marker behavior.
- [ ] Align activity detail UX with [activity_detail_mockup.svg](C:\Users\jiri.janecek1\IdeaProjects\strava_insights\docs\activity_detail_mockup.svg).
- [ ] Add frontend/component tests for the main flows.

## Phase 7: Validation and Hardening

- [ ] Verify all services build successfully with `make build`.
- [ ] Verify the full stack runs with `make up`.
- [ ] Verify the automated suite passes with `make test`.
- [ ] Validate login, import, dashboard, calendar, activity detail, and best-efforts flows end to end.
- [ ] Validate that cached/database-backed reads meet the expected latency target under normal use.
- [ ] Confirm no normal UI reads depend on live Strava calls.
- [ ] Review code structure against clean architecture requirements in [AGENTS.md](C:\Users\jiri.janecek1\IdeaProjects\strava_insights\AGENTS.md).

## Future-Ready Constraints

- [ ] Keep backend service boundaries reusable for future LLM-style insight features.
- [ ] Keep analytics available in backend-readable form, not only frontend rendering logic.
- [ ] Keep user data access clearly scoped for future natural-language query support.
