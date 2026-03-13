# Strava Insights Implementation Plan

## Summary

This plan turns [specification.md](C:\Users\jiri.janecek1\IdeaProjects\strava_insights\docs\specification.md) into a trackable delivery sequence. The new application will be built greenfield alongside the current Flask/Dash app using `Vite + React`, `FastAPI`, `Celery`, `PostgreSQL`, `Redis`, Docker, Poetry for Python package management, and simple `make` commands.

## Progress Rules

- Mark items complete only after code is implemented, tested, and validated.
- Every code change must include a successful `make build`.
- Validation should happen through Docker-based commands, not ad hoc local-only steps.

## Phase 1: Foundation

- [x] Create top-level structure for `frontend`, `backend`, `worker`, and Docker/infrastructure files.
- [x] Add `Makefile` with `make build`, `make up`, `make test`, and `make down`.
- [x] Add Docker Compose stack for frontend, backend, worker, PostgreSQL, and Redis.
- [x] Initialize React frontend with Vite and Tailwind.
- [x] Initialize FastAPI backend with clean architecture folder layout.
- [x] Initialize Celery worker and shared configuration.
- [x] Add Poetry configuration for backend and worker dependency management.
- [x] Add environment configuration templates for Strava, Mapy.cz, PostgreSQL, and Redis.
- [x] Verify the stack builds successfully with `make build`.
- [x] Verify the stack starts successfully with `make up`.

## Phase 2: Backend Core

- [x] Add SQLAlchemy models and Alembic migrations for:
- [x] `users`
- [x] `oauth_tokens`
- [x] `activities`
- [x] `activity_streams`
- [x] `period_summaries`
- [x] `best_efforts`
- [x] `activity_best_efforts`
- [x] `sync_jobs`
- [x] `sync_checkpoints`
- [x] Add required indexes from `specification.md`.
- [x] Model imported activity fields required by the spec:
- [x] `name`, `description`, `start_date_local`, `type`
- [x] `distance`, `moving_time`, `elapsed_time`
- [x] `total_elevation_gain`, `elev_high`, `elev_low`
- [x] `average_speed`, `max_speed`
- [x] `average_heartrate`, `max_heartrate`
- [x] `average_cadence`, `start_latlng`
- [x] Model activity streams required for local detail rendering:
- [x] `time`
- [x] `distance`
- [x] `latlng`
- [x] `altitude`
- [x] `velocity_smooth`
- [x] `heartrate`
- [x] Implement Strava OAuth backend flow.
- [x] Implement secure token persistence.
- [x] Implement server-side session auth with secure cookie-based session management.
- [x] Implement current-user/profile endpoint.
- [x] Implement sync-status endpoint.
- [x] Add Redis-backed caching utilities.
- [x] Add backend DTOs for raw activity data, derived activity KPIs, and activity-detail analytics payloads.
- [x] Add backend unit and integration test scaffolding.

## Phase 3: Sync and Import Pipeline

- [x] Implement first-login full historical import job.
- [x] Implement daily incremental sync job.
- [x] Implement sync checkpoint logic to fetch only new activities after initial import.
- [x] Persist normalized activity metadata.
- [x] Persist activity streams required for detail views.
- [x] Persist or derive normalized activity fields used across reads:
- [x] `distance_km`
- [x] formatted moving time
- [x] sport-specific display pace or speed fields
- [x] difficulty inputs needed for activity list and calendar read models
- [x] Persist sync job status and progress.
- [x] Invalidate or refresh affected cache entries after sync.
- [x] Ensure standard read endpoints do not call Strava synchronously.
- [x] Add tests for first import and incremental sync behavior.

## Phase 4: Analytics Port

- [x] Port activity detail derivations from the current app as explicit backend analytics services:
- [x] moving-average heart rate with `range_points = 10`
- [x] moving-average speed from `velocity_smooth * 3.6` with `range_points = 10`
- [x] derived running pace from stream `time` and `distance` with `range_points = 20`
- [x] formatted running pace output in both numeric and `MM:SS` forms
- [x] slope calculation over a 30-point window with clamp to `[-45, 45]`
- [x] running interval and pace-zone analysis
- [x] running compliance score and explanatory summary for dominant pace zone
- [x] Port the user-relative running pace / heart-rate zone model:
- [x] `bpm_max = 220 - 0.7 * age`
- [x] pace and bpm anchors for `100m`, `5km`, `10km`, `Half-Marathon`, `Marathon`, `Active Jogging`, `Slow Jogging`, `Walk`
- [x] midpoint-based pace and bpm zone boundaries
- [x] Implement the derived activity difficulty heuristic from the current app as a reusable analytics function.
- [x] Implement summary aggregation for dashboard KPIs.
- [x] Implement monthly, yearly, and rolling-period comparisons.
- [x] Implement best-effort calculations.
- [x] Store or precompute period summaries needed for fast reads.
- [x] Add tests for analytics calculations and aggregations.

## Phase 5: API Surface

- [x] Implement `/auth/*` endpoints.
- [x] Implement `/me` endpoint.
- [x] Implement `/sync/status` endpoint.
- [x] Implement `/dashboard` endpoint.
- [x] Implement `/trends` and `/comparisons` endpoints.
- [x] Implement `/activities` list endpoint with sport and date filters.
- [x] Implement `/activities/{id}` detail endpoint.
- [x] Implement `/best-efforts` endpoint.
- [x] Define stable response contracts for:
- [x] activity summary cards
- [x] activity list rows
- [x] activity-detail metadata and KPI header
- [x] activity-detail graph series
- [x] running interval-analysis payloads
- [x] Ensure activity detail payload includes:
- [x] metadata and KPI values
- [x] map bounds and route polyline
- [x] pace or speed series
- [x] heart rate series
- [x] elevation series
- [x] slope series
- [x] running interval analysis when applicable
- [x] Add integration tests for all core read endpoints.

## Phase 6: Frontend Application

- [x] Implement landing/login screen.
- [x] Implement sync/import status screen or state.
- [x] Implement dashboard screen.
- [x] Implement calendar screen.
- [x] Refine the calendar screen to use one aggregated daily circle marker with distance-scaled diameter.
- [x] Apply calendar day colors: yellow for running, orange for cycling, based on summed daily distance.
- [x] Implement activity list screen.
- [x] Implement activity detail screen.
- [x] Implement best efforts screen.
- [x] Implement settings/profile screen.
- [x] Add shared sport-type and date-range filters.
- [x] Integrate Mapy.cz on the activity detail page.
- [x] Restyle the frontend visual language to be closer to Strava web: light surfaces, restrained neutrals, orange emphasis, and data-first layouts.
- [x] Render the activity detail graph with pace/speed, heart rate, elevation, and slope.
- [x] Add hover-linked map marker behavior.
- [x] Render the canonical activity KPI header:
- [x] distance
- [x] moving time
- [x] average running pace or cycling speed
- [x] total elevation gain
- [x] average heart rate when available
- [x] Render running-only activity analysis using backend interval and compliance outputs.
- [x] Add frontend/component tests for the main flows.
- [x] Remove the duplicate main-layout logout control and place the manual sync action in the sidebar status card.
- [x] Auto-refresh sync status progress in the frontend while sync jobs are queued or running, without requiring a manual page reload.
- [x] Refine calendar day-bubble sizing to use sport-specific distance buckets that better separate short, medium, and long training days.

## Phase 7: Validation and Hardening

- [x] Verify all services build successfully with `make build`.
- [x] Verify the full stack runs with `make up`.
- [x] Verify the automated suite passes with `make test`.
- [x] Fix default local Docker/browser connectivity by pointing the frontend to the published backend URL and allowing credentialed CORS from the frontend origin.
- [x] Fix session-secret handling in Docker Compose so `.env` values are not overridden by a known constant.
- [x] Fix calendar day grouping to compare activity dates in local time instead of UTC.
- [x] Fix Strava activity import for modern large Strava activity ids by migrating `activities.strava_activity_id` to `BIGINT` and rolling back failed worker sessions before marking sync jobs failed.
- [x] Fix migration bootstrap so pre-Alembic scaffold databases are stamped at revision `20260309_0002` and still run later corrective migrations on startup.
- [x] Replace the discontinued Mapy.cz JavaScript SDK integration with a supported Mapy REST tiles + Leaflet frontend implementation, while keeping the local route-preview fallback.
- [x] Align the React Mapy.cz tile URL with the working Dash Leaflet implementation and make the frontend dev container refresh dependencies on startup so new packages are available in the mounted workspace.
- [x] Split frontend public env files from backend and worker secret env files, add committed templates for each, and wire Docker Compose to the service-local real files.
- [ ] Validate login, import, dashboard, calendar, activity detail, and best-efforts flows end to end.
- [x] Validate that activity list, calendar, and detail screens match the KPI and analytics definitions in `specification.md`.
- [x] Validate running detail parity for smoothing windows, pace zones, interval grouping, and compliance scoring.
- [x] Prevent worker incremental sync jobs from failing when Strava returns `404 Not Found` for an activity streams endpoint; import the activity and continue without streams.
- [x] Ensure manual refresh remains incremental even if the sync checkpoint is missing by falling back to the latest locally stored activity timestamp instead of refetching full history.
- [ ] Validate that cached/database-backed reads meet the expected latency target under normal use.
- [x] Confirm no normal UI reads depend on live Strava calls.
- [ ] Review code structure against clean architecture requirements in [AGENTS.md](C:\Users\jiri.janecek1\IdeaProjects\strava_insights\AGENTS.md).
- [ ] Refactor the frontend out of the single-file `App.jsx` composition into separate screens, reusable hooks, API client utilities, and map/calendar components.
- [ ] Make the Windows wrapper execution path resilient to default PowerShell execution-policy restrictions or document an execution-policy-safe invocation path.

## Future-Ready Constraints

- [ ] Keep backend service boundaries reusable for future LLM-style insight features.
- [ ] Keep analytics available in backend-readable form, not only frontend rendering logic.
- [ ] Keep user data access clearly scoped for future natural-language query support.
