# Strava Insights

### This implementation was built completely with agentic AI assistance.

Strava Insights is a split-stack application for exploring imported Strava activity data without calling the Strava API
on normal dashboard requests.

The current implementation is organized as:

- `frontend`: React + Vite web UI
- `backend`: FastAPI read/auth API
- `worker`: Celery background sync and read-model work
- `postgres`: persisted application data
- `redis`: cache and Celery broker/backend

## Current Features

- Strava OAuth login and session-based authentication
- Dashboard overview with period-to-period comparisons
- Trend Series chart with brush-based range selection
- Activity list with scrollable browsing
- Activity detail page with synced charts and route selection
- Best efforts view
- Profile settings
- Sync status and manual incremental refresh

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

## Notes

- Python dependency management for `backend` and `worker` uses Poetry.
- Docker Compose is the default validation path for meaningful changes.
- Product and architecture rules are documented in `docs/specification.md` and `docs/implementation_plan.md`.
