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

## Strava OAuth Setup

- Each athlete must create or reuse their own Strava developer application and enter that app's `client_id` and `client_secret` on the landing/login screen before connecting.
- The landing/login screen should link users to `https://www.strava.com/settings/api` for app creation and credential lookup.
- Set the Strava authorization callback URL to `https://<your-domain>/auth/strava/callback`.
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
