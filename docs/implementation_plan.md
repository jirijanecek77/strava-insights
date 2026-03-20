# Strava Insights Implementation Plan

## Purpose

This document tracks implementation status against [specification.md](C:/Users/jiri.janecek1/IdeaProjects/strava_insights/docs/specification.md). It should record what is done, what remains, and what still needs validation. It should not restate the full product specification.

## Status Rules

- Mark work complete only after code is implemented and relevant validation has passed.
- Every meaningful code change must include a successful `make build`.
- Prefer Docker-based validation through the standard command surface in [development.md](C:/Users/jiri.janecek1/IdeaProjects/strava_insights/docs/development.md).

## Current State

### Completed Foundations

- [x] Created the split application structure for `frontend`, `backend`, and `worker`.
- [x] Added Docker Compose, `Makefile`, and Windows wrapper support for the local stack lifecycle.
- [x] Initialized the React frontend, FastAPI backend, Celery worker, and Poetry-managed Python services.
- [x] Added committed env templates for service-local configuration.

### Completed Backend and Data Work

- [x] Implemented the core PostgreSQL schema and Alembic migrations for users, auth tokens, activities, streams, summaries, sync tracking, and analytics-related tables.
- [x] Added the required indexes described in the specification.
- [x] Implemented Strava OAuth, secure token persistence, and cookie-based session auth.
- [x] Added current-user and sync-status endpoints.
- [x] Added Redis-backed cache utilities needed by current reads and sync behavior.
- [x] Replaced shared env-based Strava app credentials with per-user Strava app credentials entered on the landing screen, persisted in the database, and reused for OAuth/token refresh.

### Completed Sync and Import Work

- [x] Implemented first-login full historical import.
- [x] Implemented daily incremental sync.
- [x] Added sync checkpoint handling to fetch only newly available activities.
- [x] Persisted normalized activity metadata and required stream data for local detail rendering.
- [x] Persisted sync job status and progress.
- [x] Invalidated or refreshed affected cache entries after sync.
- [x] Ensured normal read endpoints do not depend on synchronous Strava calls.
- [x] Made manual refresh remain incremental when a checkpoint is missing by falling back to the latest stored activity timestamp.
- [x] Tolerated Strava activity-stream `404` responses by importing the activity without streams.

### Completed Analytics and API Work

- [x] Ported activity-detail derivations for smoothed heart rate, smoothed speed, derived running pace, slope, and running-specific detail analytics.
- [x] Implemented reusable backend analytics for activity detail, aggregations, best efforts, and heart-rate drift.
- [x] Implemented dashboard aggregations, comparisons, and best-effort derivation.
- [x] Implemented auth, profile, sync, dashboard, activities, and best-efforts API endpoints.
- [x] Defined stable response payloads for activity summaries, detail views, and interval-analysis data.
- [x] Added heart-rate drift as an activity KPI derived from stored streams and exposed in activity list/detail payloads.

### Completed Frontend Work

- [x] Implemented landing/login, dashboard, calendar, activity list, activity detail, best efforts, and settings/profile screens.
- [x] Added shared sport and date filtering.
- [x] Integrated map rendering for activity detail with local route fallback behavior.
- [x] Restyled the UI toward the intended Strava-inspired visual direction.
- [x] Added sync-status progress refresh behavior in the frontend.
- [x] Refined the calendar daily marker behavior and activity-detail chart presentation.
- [x] Added editable profile inputs for explicit running threshold fields.
- [x] Replaced single threshold profile values with dated threshold snapshots resolved by activity local date.
- [x] Added running-analysis metric tooltips plus separate activity evaluation and further-training guidance in activity detail.
- [x] Restored AeT and AnT guides on running pace and heart-rate detail charts while keeping the average lines.
- [x] Added first-pass cycling activity analytics for rides and e-bike rides using speed, heart rate, cadence, and terrain data already stored locally.
- [x] Added landing/login credential capture, saved-credential reconnect behavior after logout, and a Strava API settings link for user-managed app credentials.

### Completed Validation and Hardening Work

- [x] Verified the stack builds with `make build`.
- [x] Verified the stack starts with `make up`.
- [x] Verified the automated suite passes with `make test`.
- [x] Fixed frontend/backend local connectivity and credentialed CORS behavior.
- [x] Fixed Docker session-secret handling.
- [x] Fixed local-time calendar day grouping.
- [x] Fixed handling for large Strava activity ids.
- [x] Fixed migration bootstrap for databases created before Alembic tracking.
- [x] Replaced the discontinued Mapy.cz JavaScript SDK integration with the supported current map approach.
- [x] Normalized activity summary metric payloads so the frontend can render pace and speed consistently.
- [x] Isolated backend pytest runs from the development dataset.
- [x] Hardened dated threshold profile saves against duplicate same-date submissions so repeated save clicks do not crash `/me/profile`.
- [x] Removed dead frontend helpers and stale backend-only code paths with no production call sites.
- [x] Added a separate production deployment path with production Dockerfiles, a single-host Docker Compose stack, and reverse-proxy TLS support for low-cost VPS hosting.
- [x] Added backend, worker, and beat logging to Docker console with request and task lifecycle coverage.

## Remaining Work

### End-to-End Validation

- [ ] Validate login, import, dashboard, calendar, activity detail, and best-efforts flows end to end in the running Docker stack.
- [ ] Validate that cache-backed and database-backed reads meet the expected latency target under normal use.

### Architecture and Codebase Cleanup

- [ ] Review the current code structure against the clean-architecture target in the specification and close remaining boundary leaks.
- [ ] Refactor the frontend out of the current single-file `App.jsx` composition into screens, reusable hooks, API utilities, and focused components.

### Local Workflow Hardening

- [ ] Make the Windows wrapper path resilient to default PowerShell execution-policy restrictions, or document an execution-policy-safe invocation path.

### Future-Ready Guardrails

- [ ] Keep backend service boundaries reusable for future insight-oriented features.
- [ ] Keep analytics available in backend-readable form rather than only in frontend presentation code.
- [ ] Keep user data access clearly scoped for future natural-language query support.

## Notes

- The implementation has already expanded best-effort support beyond running-only behavior. The specification is the source of truth for the supported v1 scope.
- Update this document after meaningful implementation work so open items remain actionable and credible.
