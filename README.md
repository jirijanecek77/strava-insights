# Strava Insights

> This project was fully implemented through collaboration with agentic AI coding agents. It is a practical demonstration of shipping a complete product with AI-assisted software delivery.

Strava Insights is a web application for athletes who want a clearer view of their training history than the standard Strava experience provides. It imports your Strava data into a local application database, then serves dashboards, comparisons, and activity analysis from that local dataset so the app stays fast and usable without depending on live Strava API reads during everyday use.

## Who It Is For

Strava Insights is designed for runners and cyclists who want to:

- understand training progression over time
- compare current performance with previous weeks, months, and years
- review individual activities in more detail
- track best efforts across key distances
- use their own threshold settings to interpret effort and intensity

## What Customers Can Do With It

### Get a training dashboard that explains change

The dashboard summarizes key metrics such as distance, moving time, activity count, pace, and speed, then compares them across meaningful windows:

- this week vs previous week
- this month vs previous month
- this year vs previous year
- rolling 30 days vs previous rolling 30 days

### Explore trends without waiting on Strava

Because activity data is imported and stored locally, normal app screens do not need live Strava API calls. That makes the experience better suited for repeated analysis, historical browsing, and responsive dashboards.

### Browse training on a calendar

The calendar gives a visual training overview by day, using activity volume and dominant sport to make patterns easy to spot.

### Review every activity in detail

Each activity page can show:

- route map based on stored GPS data
- distance, moving time, elevation, pace, or speed
- heart-rate and elevation charts when available
- slope and terrain-derived analysis when available
- linked charts and route focus for deeper inspection

### Analyze effort, not just totals

For running activities, the app can use configured aerobic and anaerobic thresholds to interpret:

- pace distribution
- heart-rate distribution
- agreement or mismatch between pace and heart rate
- sustained threshold blocks

For cycling activities, it can summarize:

- speed distribution
- terrain split across climbing, flat, and descending sections
- cadence and heart-rate patterns when the data exists

### Track best efforts

The app keeps a dedicated best-efforts view for supported sports so athletes can quickly see standout performances across their imported history.

### Stay synced in the background

First login starts a historical import. After that, the system supports incremental syncs, daily refresh behavior, visible sync progress, and manual refresh without forcing a full reimport.

## Why This Product Is Different

- It is built for athlete insight, not generic reporting.
- It avoids live Strava reads on normal dashboard and analysis pages.
- It keeps imported data available for richer derived metrics and faster repeat usage.
- It combines dashboard summaries, day-level training views, and deep single-activity analysis in one place.

## Supported Scope

Current v1 scope includes:

- Strava OAuth login
- multi-user data isolation
- running, ride, and e-bike ride support
- dashboard, calendar, activity list, activity detail, best efforts, profile/settings, and sync status views
- locally rendered activity analytics based on imported activity metadata and streams

## Docker Run

Docker is the default local workflow.

### 1. Create env files

Copy the templates into real env files before starting the stack:

```bash
cp frontend/.env.template frontend/.env
cp backend/.env.template backend/.env
cp backend/.env.secrets.template backend/.env.secrets
cp worker/.env.template worker/.env
cp worker/.env.secrets.template worker/.env.secrets
```

PowerShell:

```powershell
Copy-Item frontend/.env.template frontend/.env
Copy-Item backend/.env.template backend/.env
Copy-Item backend/.env.secrets.template backend/.env.secrets
Copy-Item worker/.env.template worker/.env
Copy-Item worker/.env.secrets.template worker/.env.secrets
```

Fill in at least:

- `frontend/.env`: `VITE_MAPYCZ_API_KEY`
- `backend/.env.secrets`: `SESSION_SECRET_KEY`, `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`
- `worker/.env.secrets`: `SESSION_SECRET_KEY`, `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`

### 2. Build and start

```bash
make build
make up
```

Windows fallback when `make` is not installed:

```powershell
.\make.ps1 build
.\make.ps1 up
```

### 3. Run tests

```bash
make test
```

PowerShell:

```powershell
.\make.ps1 test
```

### 4. Stop the stack

```bash
make down
```

PowerShell:

```powershell
.\make.ps1 down
```

### Docker service URLs

- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8000`
- PostgreSQL: `localhost:5433`

## Local Install

You can also run the services locally. The simplest setup is:

- run `postgres` and `redis` via Docker
- run `frontend`, `backend`, and `worker` on the host machine

### Prerequisites

- Node.js 22+
- Python 3.13
- Poetry 2.x
- Docker Desktop

### 1. Start infrastructure

```bash
docker compose up -d postgres redis
```

### 2. Configure env files

Create the same env files as in the Docker workflow.

If `backend` or `worker` run outside Docker, update these values to host-based addresses:

- `DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5433/strava_insights`
- `REDIS_URL=redis://localhost:6379/0`

Keep:

- `BACKEND_PUBLIC_URL=http://localhost:8000`
- `FRONTEND_PUBLIC_URL=http://localhost:5173`
- `VITE_API_BASE_URL=http://localhost:8000`

### 3. Install frontend

```bash
cd frontend
npm install
```

Run:

```bash
npm run dev
```

### 4. Install backend

```bash
cd backend
poetry install --with dev
poetry run alembic upgrade head
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Install worker

```bash
cd worker
poetry install --with dev
poetry run celery -A app.celery_app.celery_app worker --loglevel=info
```

Optional beat process:

```bash
cd worker
poetry run celery -A app.celery_app.celery_app beat --loglevel=info
```

## Test Commands

- Frontend: `docker compose run --rm frontend npm run test -- --run`
- Backend: `docker compose run --rm backend pytest`
- Worker: `docker compose run --rm worker pytest`

## Production Deployment

The repository includes a production deployment path for a single-host VPS:

- `docker-compose.prod.yml`
- `frontend/Dockerfile.prod`
- `backend/Dockerfile.prod`
- `worker/Dockerfile.prod`
- `deploy/Caddyfile`

Recommended host shape for v1:

- one small Hetzner VPS
- `2 vCPU`, `4 GB RAM`, `40 GB SSD` minimum

See [docs/deployment.md](docs/deployment.md) for the full setup.
