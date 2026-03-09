/# Repository Guidelines

## Project Structure & Module Organization

`app.py` is the main Flask entrypoint and wires the Dash application into the Flask server. UI pages, components,
layouts, models, and utility code live under `dash_apps/app/`. Login and Strava auth routes are isolated in
`blueprints/login/`. MongoDB access helpers live in `connections/`. Static assets are in `static/css/` and
`static/img/`. The current automated tests are in `dash_apps/tests/utils/`.

## Build, Test, and Development Commands

Create a virtual environment and install dependencies:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Run MongoDB locally when working on persistence:

```bash
docker run --name strava-mongo -d -p 27017:27017 mongo:latest
```

Copy `.env.example` to `.env`, fill in Strava and app secrets, then start the app with `python app.py`. For
production-style startup, `gunicorn app:server` is defined in `Procfile`. Format code with `black .` and run static type
checks with `mypy .`.

## Coding Style & Naming Conventions

Follow Black formatting defaults: 4-space indentation, trailing commas where useful, and one import per line when
clarity improves. Use `snake_case` for modules, functions, and variables, and `PascalCase` for classes such as models.
Keep Dash page code in `dash_apps/app/pages/`, reusable UI in `components/`, and pure helpers in `utils/`.

## Testing Guidelines

Tests use `pytest`-style naming with files such as `test_zone_bpm_pace_intervals.py` and functions named `test_*`. Run
the current suite from the repository root with `pytest dash_apps/tests`. Add focused tests next to the relevant area,
especially for interval logic, callback helpers, and data conversion utilities.

## Commit & Pull Request Guidelines

Keep commit subjects short, imperative, and lowercase, matching recent history: `fix slope performance issue`,
`improve modal layout`. Group related changes into one commit. Pull requests should describe the user-visible change,
note any config or data-model impact, link the related issue, and include screenshots for UI updates.

## Configuration Tips

Required local settings are documented in `.env.example`: `STRAVA_CLIENT_ID`, `STRAVA_CLIENT_SECRET`, `WEB_APP_URL`,
`SECRET_KEY`, and `MAPY_CZ_API_KEY`. Never commit filled `.env` files or live API credentials.
