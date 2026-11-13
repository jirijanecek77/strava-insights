# Garmin Insights Implementation Plan

## Purpose

This document tracks implementation status against [specification.md](specification.md). It should record what is done, what remains, and what still needs validation. It should not restate the full product specification.

## Status Rules

- Mark work complete only after code is implemented and relevant validation has passed.
- Every meaningful code change must include a successful `make build`.
- Prefer Docker-based validation through the standard command surface in [development.md](development.md).

## Current State

### Completed Foundations

- [x] Created the split application structure for `frontend`, `backend`, and `worker`.
- [x] Added Docker Compose, `Makefile`, and Windows wrapper support for the local stack lifecycle.
- [x] Initialized the React frontend, FastAPI backend, Celery worker, and Poetry-managed Python services.
- [x] Added committed env templates for service-local configuration.

### Completed Backend and Data Work

- [x] Implemented the core PostgreSQL schema and Alembic migrations for users, auth tokens, activities, streams, summaries, sync tracking, and analytics-related tables.
- [x] Added the required indexes described in the specification.
- [x] Replaced legacy source login with Garmin email/password credential login, encrypted Garmin token persistence, MFA handling, and cookie-based session auth.
- [x] Added current-user and sync-status endpoints.
- [x] Added Redis-backed cache utilities needed by current reads and sync behavior.
- [x] Replaced shared env-based source credentials with per-user Garmin credentials entered on the landing screen and
  persisted as encrypted session material in the database.

### Completed Sync and Import Work

- [x] Implemented first-login full historical import.
- [x] Implemented daily incremental sync.
- [x] Added sync checkpoint handling to fetch only newly available activities.
- [x] Persisted normalized activity metadata and required stream data for local detail rendering.
- [x] Persisted sync job status and progress.
- [x] Invalidated or refreshed affected cache entries after sync.
- [x] Ensured normal read endpoints do not depend on synchronous external-source calls.
- [x] Made manual refresh remain incremental when a checkpoint is missing by falling back to the latest stored activity timestamp.
- [x] Tolerated source activity-stream `404` responses by importing the activity without streams.

### Completed Analytics and API Work

- [x] Ported activity-detail derivations for raw sanitized heart-rate and speed samples, adjacent-segment running pace,
  slope, and running-specific detail analytics.
- [x] Implemented reusable backend analytics for activity detail, aggregations, best efforts.
- [x] Implemented dashboard aggregations, comparisons, and best-effort derivation.
- [x] Implemented auth, profile, sync, dashboard, activities, and best-efforts API endpoints.
- [x] Defined stable response payloads for activity summaries, detail views, and interval-analysis data.
- [x] Added admin-only user audit APIs plus admin UI for the configured admin athlete, including user disable/reject actions.
- [x] Added disabled-user enforcement on authenticated requests and blocked disabled users from reconnecting through
  Garmin credentials.
- [x] Added user `last_login_at` persistence for admin audit visibility.

### Completed Frontend Work

- [x] Implemented landing/login, dashboard, calendar, activity list, activity detail, best efforts, and settings/profile screens.
- [x] Added shared sport and date filtering.
- [x] Added an activity list filter by name and KPI rules (`>`, `<`, `=`) with sport-dependent pace or speed.
- [x] Added local activity rename from the detail header, kept by Garmin sync, which sets names only on first import.
- [x] Integrated map rendering for activity detail with local route fallback behavior.
- [x] Restyled the UI toward the intended athlete training visual direction.
- [x] Added sync-status progress refresh behavior in the frontend.
- [x] Refined the calendar daily marker behavior and activity-detail chart presentation.
- [x] Added editable profile inputs for explicit running threshold fields.
- [x] Replaced single threshold profile values with dated threshold snapshots resolved by activity local date.
- [x] Added running-analysis metric tooltips and condition/strain signal icons in activity detail.
- [x] Restored AeT and AnT guides on running pace and heart-rate detail charts while keeping the average lines.
- [x] Added first-pass cycling activity analytics for rides and e-bike rides using speed, heart rate, cadence, and terrain data already stored locally.
- [x] Added landing/login credential capture with saved-credential reconnect behavior after logout.
- [x] Simplified the landing/login flow to a single Garmin connection action that uses saved credentials when available
  and falls back to Garmin credential setup.

### Completed Validation and Hardening Work

- [x] Verified the stack builds with `make build`.
- [x] Verified the stack starts with `make up`.
- [x] Verified the automated suite passes with `make test`.
- [x] Fixed frontend/backend local connectivity and credentialed CORS behavior.
- [x] Fixed Docker session-secret handling.
- [x] Fixed local-time calendar day grouping.
- [x] Fixed handling for large external activity ids.
- [x] Fixed migration bootstrap for databases created before Alembic tracking.
- [x] Replaced the discontinued Mapy.cz JavaScript SDK integration with the supported current map approach.
- [x] Normalized activity summary metric payloads so the frontend can render pace and speed consistently.
- [x] Isolated backend pytest runs from the development dataset.
- [x] Hardened dated threshold profile saves against duplicate same-date submissions so repeated save clicks do not crash `/me/profile`.
- [x] Removed dead frontend helpers and stale backend-only code paths with no production call sites.
- [x] Added a separate production deployment path with production Dockerfiles, a single-host Docker Compose stack, and reverse-proxy TLS support for low-cost VPS hosting.
- [x] Added backend, worker, and beat logging to Docker console with request and task lifecycle coverage.
- [x] Standardized backend, worker, and frontend log prefixes with readable timestamps, service labels, and frontend INFO-level filtering.
- [x] Switched the import source to Garmin Connect while preserving existing local activity/stream data and local analytics.
- [x] Removed live source API/OAuth integration code and source-specific env configuration.
- [x] Hardened activity detail reads for Garmin stream compatibility, including scalar-only GPS streams and sparse null
  samples in numeric streams.
- [x] Removed unused heart-rate drift analytics, dead analytics helpers, unused activity metadata columns, user email storage, and the unused activity-level effort table through an explicit migration.
- [x] Added aligned stream sanitation for speed, distance, GPS, altitude, and heart-rate artifacts, including segmented route rendering across missing GPS runs.
- [x] Added current elevation to every activity-detail graph tooltip.
- [x] Kept raw detail samples in tooltips while excluding only abnormal first and last samples from detail-chart line
  rendering and Y-axis scaling, preserving interior interval-session values.
- [x] Made activity-detail chart tooltips choose bounds-safe vertical and horizontal placement for high, low, left-edge,
  and right-edge points.
- [x] Replaced quadratic best-effort scans with linear local calculations over sanitized streams for running and cycling
  activities.
- [x] Persisted and exposed the top five best efforts per sport and distance, with collapsed ranking UI, source activity links, and activity-detail rank badges.
- [x] Removed the unavailable external route-assignment dependency and implemented versioned, direction-aware local GPS
  route matching with additive signature, group, and membership tables.
- [x] Added an icon-led, four-column Best Efforts KPI with rank colors to Activity Detail and kept same-route ranking, attempt history, links, and trend in a separate compact Performance band after the slope chart.
- [x] Made manual sync recalculate analytics while scheduled no-change syncs skip an already-current read-model rebuild.
- [x] Applied migration `20260810_0014` and validated a real manual refresh over 148 activities; the worker completed in about 11 seconds and persisted ranked efforts plus sanitized streams.
- [x] Restored the documented Windows build wrapper, updated vulnerable frontend dependencies to audited versions, and split charting code out of the initial production bundle.
- [x] Aligned Garmin login with the public `garminconnect` flow, added a non-MFA regression seam, corrected saved-token reconnect, and mapped expected Garmin failures to structured HTTP responses.
- [x] Rebuilt and restarted the local backend after the Garmin authentication fix; the health endpoint returned 200.
- [x] Temporarily disabled MFA in the active login flow to keep Garmin non-MFA login deterministic while authentication is stabilized.
- [x] Added migration `20260826_0018` to convert renamed external Garmin identities from PostgreSQL `BIGINT` to the application’s text contract after live login exposed the type mismatch.
- [x] Corrected Garmin activity-detail metric normalization, omitted strength-training activities, and added
  non-destructive stream backfill for existing activities with empty stream JSON.
- [x] Derived imported average pace and speed from moving time, excluding pauses from elapsed duration.
- [x] Prefer Garmin's `averageMovingSpeed` field when available, with moving-time derivation as the fallback.
- [x] Added a durable `sync_dispatch_outbox` so accepted API and scheduled sync jobs survive broker outages, plus a
  dedicated dispatcher process that retries Celery publication with backoff.
- [x] Made sync-task delivery idempotent and added bounded exponential retries for temporary import failures.

### Incremental Derived Data

- [x] Replaced the per-sync full recomputation with incremental updates for activities above the `derived_activities`
  watermark plus stream backfills: period summaries from activity rows, best efforts merged into the stored top five,
  and route assignment by complete linkage against candidate signatures loaded from `activity_route_signatures`.
- [x] Kept full recomputation for full imports, derived-model version changes, a missing watermark, and the new
  Settings "Recalculate All" action (`POST /sync/recalculate`, sync source `full_recompute`).
- [x] Added unit tests for route assignment, best-effort merging, and the full-versus-incremental decision.
- [ ] Validate the incremental route and best-effort updates in the running stack after the next daily sync, and compare
  the result with a "Recalculate All" run.

### AI Coaching

- [x] Added backward-safe migration `20261011_0021` with `activity_coaching_notes` and `period_coaching_summaries`.
- [x] Initially added an OpenAI-compatible LLM client for the Gemini API free tier (superseded by the Groq migration below),
  with rate-limit handling based on the provider's retry delay.
- [x] Added versioned English coaching prompts with compact, GPS-free activity and period contexts.
- [x] Queued coaching notes for activities newly imported by incremental syncs, and added a lease-based generator that
  runs after sync and every 15 minutes from `beat`, then plans and refreshes week and month reviews.
- [x] Exposed coaching notes in activity detail and added `GET /coaching/periods`; activity detail renders the note
  below the running or cycling analysis and the calendar renders week and month reviews.
- [x] Added the `python -m app.coaching_cli` operator commands for test runs on a user's latest activities.
- [x] Ran the first live generation with `gemini-3.8-flash` for the latest three activities plus the week of
  2026-10-05 and October 2026; all five items succeeded without rate limiting.
- [x] Switched coaching prompts (`PROMPT_VERSION` 2) from session summaries to analyses of training quality,
  fatigue, and trends.
- [ ] Review coaching quality over the next weeks of real use and tune prompts (`PROMPT_VERSION`) if needed.

### Coaching Context and Period Comparisons

Implemented and locally validated on 2026-11-13; design and calculation rules are in
[coaching_context_plan.md](coaching_context_plan.md). Existing ready text is preserved.

- [x] Reviewed existing activity/period contexts and documented inputs, reusable outputs, missing evidence, and a
  token-conscious flow for activity, weekly, and monthly coaching.
- [x] Add backward-safe versioned activity evidence persistence and deterministic HR-band time/distance with dated
  thresholds, correct AeT/AnT boundaries, explicit unknown coverage, and a bounded local-only evidence population command.
- [x] Extract compact steady/endurance and tempo-block evidence from stored laps; validate comparable-session matching
  and insufficient-data rules against representative local activities.
- [x] Make activity output interpretation-only without repeating displayed KPIs; retain total elevation gain in input
  and add compact lap/final-section terrain aggregates with coverage/noise handling. Test uphill finishes and missing
  altitude so late slowing is not labelled fatigue without supporting evidence; propagate terrain limitations to periods.
- [x] Reuse facts and existing short activity interpretations in compact period contexts; preserve legacy notes
  and avoid sending laps/streams to period models.
- [x] Add weekly absolute band time/distance, structured review metrics, and prior-week comparisons with matched windows.
- [x] Add monthly distance/band comparisons and supported endurance/tempo findings with matched-window handling,
  evidence counts, limitations, and no dependency on generated weekly prose.
- [x] Update canonical source hashes and dependent-period planning for current/previous evidence changes; version prompts
  and provide bounded historical review regeneration while preserving visible ready text and durable retry controls.
- [x] Update read schemas/UI and developer commands for evidence and metrics; measure representative context/token costs.
- [x] Pass targeted tests, `make build`, and `make test`; migrate/recreate affected Docker services and verify activity,
  weekly, and monthly behavior in the local stack before marking this upgrade complete.

Validation: migration `20261113_0025` applied; `make build`, frontend production build, and `make test` passed
(37 backend, 183 worker, 67 frontend tests). Isolated PostgreSQL tests exercise the full scripted-model generation
pipeline, evidence reuse/invalidation, metric persistence, legacy preservation, and bounded operator commands.
Recreated the affected local services and verified real activity/period context preparation and stored-review reads.
Sample current week/month payloads were about 4.7/7.9 KB with no lap arrays or raw streams.

- [ ] Optional live provider quality review and regeneration of the current week/month: automatic approval review
  rejected sending private health-derived context to Groq and replacing existing reviews without explicit approval.
  No provider call or review regeneration occurred; existing summaries remain stored.

### Coaching Payload Token Reduction

- [x] Compact coaching/planning JSON, omit redundant activity fields and equal elapsed/moving time, and round
  activity metrics to useful precision while retaining lap evidence, thresholds, athlete notes, and training history.
- [x] Omit prior plan rationales only from provider payloads, including saved contexts on retry; preserve prior
  session targets, stored planning context, exact validation bounds, and existing ready notes/plans.

### Groq Python SDK Migration

Completed and validated locally on 2026-11-10. Existing Gemini-generated notes remain stored.

- [x] Selected `openai/gpt-oss-120b` after the originally proposed Llama model returned HTTP 404 from the live API.
  Verified model availability and JSON output with the configured Groq credential; pinned the official Python SDK
  (`groq==1.7.0`) in the worker project and lockfile.
- [x] Replaced the raw HTTP adapter with synchronous `GroqLlmClient`, preserving the application protocol, JSON parser,
  prompt validation, and completion metadata. Responses use JSON-object mode with a 2,048-token output cap.
- [x] Disabled SDK retries so durable coaching retries and the per-run call budget remain authoritative. Preserved
  429 deferral without counting attempts or continuing the run, including fractional and HTTP-date `Retry-After`.
- [x] Added lazy SDK creation for missing-key startup, explicit cleanup on successful/failed runs, sanitized errors,
  and tests using the real SDK with a mocked HTTP transport.
- [x] Retained the existing `LLM_API_KEY` name, made it optional in worker settings, removed Gemini endpoint/reasoning
  settings, and made `LLM_MODEL` overridable in both Compose files. Production still loads `.env.production` separately.
- [x] Updated the specification, development/deployment workflow, and secret templates. No schema changes or data reset
  are required; existing ready notes are not regenerated merely because the provider changed.
- [x] Passed targeted coaching tests, `make build`, and `make test` (32 backend, 101 worker, 55 frontend tests).
  Reran all 101 worker tests and rebuilt after correcting the default model. Local Compose configuration and production
  template configuration pass validation; production was not deployed.
- [x] Recreated worker, beat, and sync-dispatcher. Generated the existing pending note for activity `1457` after bringing
  its retry time forward without resetting attempts, plus the week of `2026-11-09` and November 2026 reviews.
  All three succeeded without failures or rate limiting and were verified through authenticated local read APIs.

Recovery: clear the configured key and recreate the worker services to pause generation while keeping queued work
and existing text. A code rollback also needs the matching lockfile, provider configuration, and provider credential.

### AI Running Plans

Implemented and validated locally on 2026-11-10. Product behavior and training policy are defined in
[Calendar Requirements](specification.md#ai-running-plans).

- [x] Added additive migration `20261110_0022` for durable plan requests and daily run/rest targets, separate from
  imported activities and historical analytics.
- [x] Persisted one planning intent per import job alongside newly inserted activities, including running, cycling,
  and e-bike imports. Claims wait for successful sync completion; a later successful sync can release intent from
  a partially failed import. Existing-activity backfills, no-change syncs, threshold/configuration edits, date
  rollover, and calendar reads do not request new plans. Coverage shrinks during inactivity.
- [x] Added compact local training context, previous-plan continuity, and a versioned prompt targeting endurance,
  AeT/AnT, and speed. Added deterministic volume/frequency/intensity, aerobic pace/HR, and recovery-spacing bounds,
  including protection against unexplained volume collapse and easy-only return after inactivity.
- [x] Integrated generation into the existing coaching worker with one reserved planning call per run, a shared call
  budget, leases/tokens, stale-result rejection, atomic publication, rate-limit deferral, and bounded retries with
  validation feedback. Notes/reviews retain their 2,048-token cap; seven-day plans use 4,096 tokens.
- [x] Added authenticated user-scoped `GET /training-plans`, full visible-calendar range loading, daily target/rest
  cards with rationales always visible above targets, sport filtering, and pending/failure/previous-target states.
- [x] Hide planned run/rest sessions before today in the calendar using the browser's local date, preserving
  stored targets and completed activity markers.
- [x] Added CLI `replan --user-id <id>`, plan output in `show`, `make ai-plan-replan` with optional `AI_USER_ID`, and
  Windows `.\make.ps1 ai-plan-replan -AiUserId <id>`. Manual replanning explicitly permits generation without new activity.
- [x] Added history-based `build`/`maintain`/`recover` objectives before daily workout generation, with explicit
  volume, usual frequency, and long-run ranges. Comparable aerobic pace/HR evidence distinguishes isolated
  fatigue from repeated strain; cycling load contributes to recovery decisions. Activity-triggered forecasts
  retain the block objective and review date, with new recovery evidence allowed to lower load mid-block.
  Versioned request context preserves legacy plans and exposes the objective/explanation through the API and CLI.
- [x] Passed `make build`, `make test` (33 backend, 154 worker, 58 frontend), and frontend production compilation.
  Coverage includes import/backfill trigger behavior, manual CLI, leases/stale results, partial failure recovery,
  volume/recovery rules, objective selection/continuity, terrain-aware comparisons, legacy context upgrades,
  inactivity, missing HR/history, retry feedback, user isolation, and DST/month/year boundaries.
- [x] Applied the migration to the existing local database and verified live Groq generation through
  `make ai-plan-replan`. Authenticated local API reads returned seven stored days for 2026-11-11 through 2026-11-17;
  repeat reads created no generation request. After restarting affected services, objective version 2 generated
  57 km across five runs, including an 18 km long run, two spaced threshold sessions, and two rest days. The
  `maintain` objective consolidates a recent volume increase within its 54.27–59.99 km range. Authenticated API
  checks confirmed objective metadata and volume/frequency/long-run bounds. Existing activity count, distance,
  and moving-time totals remained unchanged (1,065 activities).

Operational workflow and configuration are documented in [development.md](development.md). Continue reviewing
training-plan quality during real use alongside the existing coaching-quality review; generated targets are training
recommendations and do not update measured threshold settings.

### Recorded Activity Splits for AI Coaching and Detail Chart

Behavior is defined in [specification.md](specification.md#recorded-splits-chart).

- [x] Verified real `/splits` responses for auto-lapped runs, a workout with unequal warmup/interval/cooldown laps,
  and a ride. `get_activity_splits()` supplies chronological `lapDTOs`; typed/grouped summaries are unnecessary.
- [x] Added migrations `20261111_0023` and `20261111_0024` with aligned backend/worker mappings. The final table
  retains activity ID, ready/unavailable status, and normalized laps; obsolete retry/version/timestamp columns are removed.
- [x] Fetch splits once inline for each new activity using the existing Garmin session, before insertion and coaching.
  Removed separate Celery task/schedule, post-sync batches, historical backfill, retries, and split-pending coaching gate.
  Empty/non-authentication failures are unavailable; authentication failures use the normal reconnect flow.
- [x] Exposed locally stored splits through the authenticated activity-detail response with ownership checks and
  ready/unavailable states. No provider requests occur on UI read paths.
- [x] Replaced coaching's computed distance splits with recorded Garmin laps containing distance, duration,
  average pace/speed, and HR. Removed the obsolete segmentation code and stream-excerpt prompt wording.
  Activity prompt version 3 explains lap-average limitations; period prompt version 2 remains unchanged so stored
  period reviews are not regenerated by this change. Coaching uses an explicit
  limitation when recorded splits are unavailable. Existing ready notes and plans remain stored.
- [x] Added Splits immediately above Slope, with filled distance-proportional pace/speed steps on the left axis,
  continuous local elevation with its gray right axis, HR only in tooltips, exact lap boundaries, and linked map/graph
  focus. Kept only the Splits title above the graph. Preserved short final laps, zero-distance lap records, and gaps.
- [x] Added normalization/inline-import tests, local API and ownership coverage, coaching-payload checks, and
  chart boundary, focus, formatting, missing-data, and placement tests.
- [x] Passed `make build`, the frontend production build, and `make test` after simplification (37 backend,
  171 worker, 65 frontend). Tested migration upgrade/downgrade preservation and pending-state finalization.
  Applied migration `20261111_0024` with old workers stopped, then recreated affected services. Verified the reduced
  live schema, absence of the split task/schedule, and local detail reads for activity 1455 with all 13 laps.
- [x] Previously verified real regular-run, interval-run, and ride charts in Chrome, including filled areas, gray
  elevation axis, tooltip-only HR, label removal, placement, and desktop/mobile tooltip bounds; no runtime errors occurred.
- [x] Previously completed backfill for all 54 local Garmin activities; stored laps remain available after simplification.
  Activity count/distance/moving-time totals remained unchanged (1,065 activities, 19,273,921.85 meters, 4,593,867 seconds), and representative split-only imports left
  existing coaching notes and training plans unchanged. Added import, API, and coaching guards so legacy source IDs
  cannot be used for Garmin splits; legacy activities show an unavailable state.
- [x] Confirmed before/after fingerprints match for all stored split laps, activity coaching notes, and training-plan
  days during cleanup. Activity 1455's existing coaching summary was preserved.

## Remaining Work

### End-to-End Validation

- [ ] Apply migration `20260817_0016`, rebuild the local route index over real development activities, and calibrate matching results against representative routes.
- [ ] Validate login, import, dashboard, calendar, activity detail, and best-efforts flows end to end in the running Docker stack.
- [ ] Validate the admin user audit and disable flow end to end in the running Docker stack.
- [ ] Validate that cache-backed and database-backed reads meet the expected latency target under normal use.

### Garmin-only migration completed

- [x] Added backward-safe migration `20260826_0017` with generic external identity fields, provider-aware activity uniqueness, legacy markers, and encrypted Garmin credentials.
- [x] Added Garmin Connect authentication, saved-session reconnect, short-lived MFA challenge handling, and sensitive-token encryption.
- [x] Persisted refreshed Garmin worker sessions, added controlled reauthentication state after final Garmin 401
  responses, paused scheduled syncs for disconnected credentials, and required a manual sync after reconnect.
- [x] Added Garmin activity/detail normalization and removed imported source pace-curve dependencies; best efforts are local.
- [x] Removed active legacy source clients, credentials, settings, and provider-specific tests.

### Architecture and Codebase Cleanup

- [ ] Review the current code structure against the clean-architecture target in the specification and close remaining boundary leaks.
- [x] Refactor the frontend out of the current single-file `App.jsx` composition into screens, reusable hooks, API utilities, and focused components.

### Local Workflow Hardening

- [ ] Make the Windows wrapper path resilient to default PowerShell execution-policy restrictions, or document an execution-policy-safe invocation path.

### Future-Ready Guardrails

- [ ] Keep backend service boundaries reusable for future insight-oriented features.
- [ ] Keep analytics available in backend-readable form rather than only in frontend presentation code.
- [ ] Keep user data access clearly scoped for future natural-language query support.

## Notes

- The implementation has already expanded best-effort support beyond running-only behavior. The specification is the source of truth for the supported v1 scope.
- Update this document after meaningful implementation work so open items remain actionable and credible.
