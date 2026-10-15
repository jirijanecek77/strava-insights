# Athlete Insights

> This project was built entirely with agentic AI coding agents.

Athlete Insights is a self-hosted training dashboard for runners and cyclists. Connect your Garmin Connect account once,
and the app imports your activity history and keeps it in sync. Everything then runs from your own local copy of the
data, so it stays fast and private.

## Why Use It

- **See how your training changes.** Compare this week, month, year, or the last 30 days with the previous period.
- **Browse your training on a calendar.** Spot patterns in volume and sport at a glance.
- **Dig into each activity.** Route map, pace or speed, heart rate, elevation, and terrain analysis.
- **Understand effort, not just totals.** Set your own aerobic and anaerobic thresholds to see how hard you really
  worked.
- **Track best efforts.** Your standout performances across key distances in one place.
- **Get AI coaching notes (optional).** Short feedback on new activities plus weekly and monthly reviews.
- **Stays up to date by itself.** Your full history is imported on first login, then new activities sync daily or on
  demand.
- **Your data stays with you.** It runs on your own machine or server, and supports multiple users with separate data.

Supported sports: running, cycling, and e-bike rides.

## Requirements

- [Docker](https://docs.docker.com/get-docker/) with Docker Compose
- A Garmin Connect account
- A [Mapy.cz API key](https://developer.mapy.com/) for route maps
- Optional: a [Google AI Studio](https://aistudio.google.com/) API key for AI coaching notes

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

| Setting               | What to put there                                         |
|-----------------------|-----------------------------------------------------------|
| `SESSION_SECRET_KEY`  | Any long random string                                    |
| `VITE_MAPYCZ_API_KEY` | Your Mapy.cz API key                                      |
| `LLM_API_KEY`         | Optional Google AI Studio key; leave empty to skip AI tips |

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
