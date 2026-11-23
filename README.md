# Athlete Insights

> This project was built entirely with agentic AI coding agents.

Athlete Insights is a self-hosted training dashboard for runners and cyclists. Connect your Garmin Connect account once,
and the app imports your activity history and keeps it in sync. Everything then runs from your own local copy of the
data, so dashboards stay fast without live Garmin reads.

## Why Use It

- **See how your training changes.** Compare this week, month, year, or the last 30 days with the previous period.
- **Browse your training on a calendar.** Spot patterns in volume and sport at a glance.
- **Dig into each activity.** Route map, pace or speed, heart rate, elevation, and terrain analysis.
- **Understand effort, not just totals.** Set your own aerobic and anaerobic thresholds to see how hard you really
  worked.
- **Track best efforts.** Your standout performances across key distances in one place.
- **Understand your training with AI coaching.** Activity analysis and next-session advice, with weekly and
  monthly reviews that connect individual sessions to longer-term patterns.
- **Plan your next seven days.** Running sessions with distance, pace, heart-rate targets and a clear
  purpose, balanced with rest and informed by your completed training and configured thresholds.
- **Stays up to date by itself.** Your full history is imported on first login, then new activities sync daily or on
  demand.
- **Your data stays with you.** It runs on your own machine or server, and supports multiple users with separate data.

Supported sports: running, cycling, and e-bike rides.

## Requirements

- [Docker](https://docs.docker.com/get-docker/) with Docker Compose
- A Garmin Connect account
- A [Mapy.cz API key](https://developer.mapy.com/) for route maps
- A [Groq API key](https://console.groq.com/keys) for AI coaching and running plans

## Installation

### 1. Get the code

```bash
git clone https://github.com/jirijanecek77/strava-insights.git
cd strava-insights
```

### 2. Add your settings

Copy the template:

```bash
cp .env.secrets.template .env.secrets
```

Open `.env.secrets` and fill in:

| Setting               | What to put there                                          |
|-----------------------|------------------------------------------------------------|
| `SESSION_SECRET_KEY`  | Any long random string                                     |
| `VITE_MAPYCZ_API_KEY` | Your Mapy.cz API key                                       |
| `LLM_API_KEY`         | Groq key for coaching and plans; leave empty to disable AI |

### 3. Start the app

With `make`:

```bash
make build
make up
```

Or with Docker Compose directly:

```bash
docker compose --env-file .env.secrets up -d --build
```

On Windows without `make`, use `.\make.ps1 build` and `.\make.ps1 up`.

### 4. Open it

Go to [http://localhost:5173](http://localhost:5173) and sign in with your Garmin Connect email and password. If your
account uses two-factor authentication, you will be asked for the code. Your first import starts right away.

## AI Coaching and Running Plans

An AI coach turns your training history, recorded laps, terrain evidence and configured thresholds into:

- **Activity feedback:** session analysis and next-session advice in Activity Detail.
- **Weekly and monthly reviews:** training patterns, comparable performance and recommendations on the calendar.
- **Seven-day running plans:** run and rest days with distance, pace, heart-rate targets and a purpose for each session.
  Cycling load informs recovery decisions.

**LangChain** integrates Groq inference with native strict JSON Schema output and Pydantic contracts. **LangGraph**
orchestrates input preparation, dependent evaluations, validation and publication. Python calculates training bounds
and validates planned volume, intensity and recovery spacing before accepting a plan.

Generation runs in Celery jobs backed by PostgreSQL work items. Leases and input-revision checks reject stale results;
shared call budgets and application-owned retries control provider requests. Local diagnostics record outcomes,
latency and token usage. Existing results remain visible during regeneration.

The default model is `openai/gpt-oss-120b` on Groq; configure `LLM_MODEL` in `.env.secrets` to change it. Only compact
metrics and training summaries are sent to the provider, excluding GPS coordinates and stream samples. Results are
stored locally, so browsing does not call the model.

See the [workflow diagram](docs/specification.md#ai-workflow-architecture) and
[AI commands](docs/development.md#ai-coaching) for details.

## Everyday Commands

| Task          | With `make`  | With Docker Compose                          |
|---------------|--------------|----------------------------------------------|
| Start         | `make up`    | `docker compose --env-file .env.secrets up -d` |
| Stop          | `make down`  | `docker compose --env-file .env.secrets down`  |
| View logs     | `make logs`  | `docker compose --env-file .env.secrets logs -f` |
| Update        | `git pull`, then `make build` and `make up` | `git pull`, then `docker compose --env-file .env.secrets up -d --build` |

Your data lives in Docker volumes, so it survives stopping, restarting, and updating the app.

## Hosting It on a Server

To run Athlete Insights on a public server with your own domain and HTTPS, see
[docs/deployment.md](docs/deployment.md).
