# Deployment Guide

## Recommended Hosting

- Primary recommendation: a single Hetzner Cloud VPS for the whole stack.
- Default size: `CX23` with `2 vCPU`, `4 GB RAM`, and `40 GB SSD`.
- Safer headroom option: `CX33` with `4 vCPU`, `8 GB RAM`, and `80 GB SSD`.
- This repository now includes a production Docker Compose path intended for a single-host deployment.

## Production Stack

The production deployment runs:

- `caddy` for TLS termination and reverse proxy
- `frontend` as a built static site behind Nginx
- `backend` as FastAPI
- `worker` as a Celery worker
- `beat` as the scheduled Celery beat process
- `postgres`
- `redis`

The public site uses one domain. Caddy forwards API and auth routes to `backend` and sends all other requests to the frontend SPA.

## Required Files

Create these files from the templates before deploying:

- `.env.production` from `.env.production.template`
- `backend/.env.secrets` from `backend/.env.secrets.template`
- `worker/.env.secrets` from `worker/.env.secrets.template`

Required values:

- `.env.production`
  - `DOMAIN`
  - `ACME_EMAIL`
  - `POSTGRES_PASSWORD`
  - `FRONTEND_VITE_API_BASE_URL`
  - `FRONTEND_VITE_MAPYCZ_API_KEY`
- `backend/.env.secrets`
  - `SESSION_SECRET_KEY`
- `worker/.env.secrets`
  - `SESSION_SECRET_KEY`

## Garmin Connect Setup

- Each athlete enters their Garmin Connect email and password on the landing/login screen; MFA is completed when Garmin requests it.
- The landing/login screen should link users to `https://intervals.icu/settings` for credential lookup.
- Garmin tokens are encrypted in PostgreSQL and are never placed in environment files.

### Reconnecting an existing account after migration

Back up the database before changing the existing account. The migration keeps all activities and marks them `legacy`; a successful Garmin login updates only the user identity and creates encrypted Garmin session storage.

```sql
-- 1. Backup (run outside psql): pg_dump "$DATABASE_URL" > strava-insights-before-garmin.sql
-- 2. Verify the retained account and legacy data:
SELECT id, source_provider, external_user_id, is_active FROM users ORDER BY id;
SELECT source_provider, count(*) FROM activities GROUP BY source_provider ORDER BY source_provider;
-- 3. After signing in through the Garmin screen, verify the new connection:
SELECT u.id, u.source_provider, u.external_user_id, c.external_user_id
FROM users u JOIN garmin_credentials c ON c.user_id = u.id;
SELECT source_provider, count(*) FROM activities GROUP BY source_provider ORDER BY source_provider;
```

Do not insert Garmin passwords, MFA codes, or token JSON through SQL or environment files. The login flow writes only encrypted session material.
- Keep `FRONTEND_VITE_API_BASE_URL` set to the same public origin, for example `https://app.example.com`.

## Deployment Commands

Build the production images:

```bash
make build-prod
```

Start the production stack:

```bash
make up-prod
```

Show logs:

```bash
make logs-prod
```

Stop the production stack:

```bash
make down-prod
```

Windows PowerShell equivalents:

```powershell
.\make.ps1 build-prod
.\make.ps1 up-prod
.\make.ps1 logs-prod
.\make.ps1 down-prod
```

## Operational Notes

- The backend still runs migrations on startup.
- Postgres and Redis use named Docker volumes and survive container recreation.
- Caddy provisions and renews TLS certificates automatically.
- The production frontend image serves built assets and supports SPA route fallback.
- The production images avoid development reload mode and do not install dev-only dependencies.
