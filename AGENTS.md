# Repository Guidelines

## Agent Scope

- Treat [specification.md](C:/Users/jiri.janecek1/IdeaProjects/strava_insights/docs/specification.md) as the source of truth for product requirements, architecture, constraints, and target structure.
- Treat [implementation_plan.md](C:/Users/jiri.janecek1/IdeaProjects/strava_insights/docs/implementation_plan.md) as the source of truth for delivery status, completed work, and remaining work.
- Keep [development.md](C:/Users/jiri.janecek1/IdeaProjects/strava_insights/docs/development.md) aligned with the actual local developer workflow and commands.

## Documentation Rules

- Keep `AGENTS.md` limited to instructions for the coding agent working in this repository.
- Put project-specific behavior, architecture, requirements, and workflow expectations into `docs`, not into `AGENTS.md`.
- Update `docs/specification.md` when the intended product behavior, architecture, or operational constraints change.
- Update `docs/implementation_plan.md` after significant implementation work so completed and remaining tasks stay accurate.
- Remove contradictions and duplicated guidance when editing repository documentation.

## Implementation Rules

- Follow clean architecture boundaries described in the specification.
- Keep framework code at the edges and business logic in testable application or domain layers.
- Do not add live Strava API calls to normal UI read paths.
- Do not solve feature work by deleting application data or resetting the database.
- When persistence changes are required, use explicit backward-safe migrations.

## Validation Rules

- Validate meaningful changes locally.
- Use the repository command surface documented in `docs/development.md`.
- After each meaningful fix, run the relevant automated tests before treating the change as complete.
- If a change affects a running service, restart or rebuild the affected Docker service or services and verify the behavior in the stack.
- Treat a change as incomplete if build or relevant tests have not been run successfully.
