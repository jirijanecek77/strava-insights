"""Operator commands for AI coaching notes.

Examples:
    python -m app.coaching_cli enqueue-latest --user-id 1 --count 3
    python -m app.coaching_cli run --user-id 1 --batch-size 10
    python -m app.coaching_cli show --user-id 1
    python -m app.coaching_cli replan --user-id 1
"""

import argparse
import textwrap

from app.config import settings
from app.db import SessionLocal
from app.logging import configure_logging
from app.models import (
    ActivityCoachingNote,
    PeriodCoachingSummary,
    TrainingPlanDay,
    TrainingPlanRequest,
    User,
)
from app.repositories import CoachingRepository
from app.tasks.coaching import run_coaching_generation, run_planning_generation
from app.services.planning.repository import PlanningRepository


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.coaching_cli")
    commands = parser.add_subparsers(dest="command", required=True)

    enqueue = commands.add_parser(
        "enqueue-latest", help="Queue coaching notes for a user's latest activities."
    )
    enqueue.add_argument("--user-id", type=int, required=True)
    enqueue.add_argument("--count", type=int, default=3)

    run = commands.add_parser(
        "run", help="Generate pending coaching notes and period reviews now."
    )
    run.add_argument("--user-id", type=int)
    run.add_argument("--batch-size", type=int)

    show = commands.add_parser(
        "show", help="Print stored coaching notes and period reviews."
    )
    show.add_argument("--user-id", type=int, required=True)

    replan = commands.add_parser(
        "replan",
        help="Request and generate a new seven-day AI running plan, even without new activities.",
    )
    replan.add_argument("--user-id", type=int, required=True)

    args = parser.parse_args(argv)
    configure_logging(log_level=settings.log_level)
    if args.command == "enqueue-latest":
        _enqueue_latest(user_id=args.user_id, count=args.count)
    elif args.command == "run":
        stats = run_coaching_generation(
            user_id=args.user_id, batch_size=args.batch_size
        )
        print(
            f"activity notes: {stats.activity_notes_generated}, "
            f"period reviews: {stats.period_summaries_generated}, failures: {stats.failures}, "
            f"running plans: {stats.training_plans_generated}, "
            f"rate limited: {stats.rate_limited}, skipped: {stats.skipped_reason}"
        )
    elif args.command == "replan":
        with SessionLocal() as session:
            user = session.get(User, args.user_id)
            if user is None or not user.is_active:
                parser.error("The athlete does not exist or is disabled.")
            request_id = PlanningRepository(session).enqueue(
                user_id=args.user_id, timezone=settings.planning_timezone
            )
            session.commit()
        stats = run_planning_generation(user_id=args.user_id)
        with SessionLocal() as session:
            request = session.get(TrainingPlanRequest, request_id)
            print(
                f"Running plan request {request_id}: {request.status}; generated: {stats.generated}, skipped: {stats.skipped_reason or 'none'}"
            )
            if request.last_error:
                print(request.last_error)
            _print_objective(request)
            if request.status == "pending":
                print(
                    "Queued for background processing; active syncs, missing API configuration, and retry delays may postpone generation."
                )
    else:
        _show(user_id=args.user_id)


def _print_objective(request) -> None:
    objective = (request.context_json or {}).get("weekly_objective")
    if objective:
        print(
            f"Objective: {objective['mode']} — {objective['distance_min_km']:g}–{objective['distance_max_km']:g} km over the next seven days; about {objective['target_running_days']} runs."
        )
        print(f"Review on {objective['review_date']}: {objective['reason']}")


def _enqueue_latest(*, user_id: int, count: int) -> None:
    session = SessionLocal()
    try:
        repository = CoachingRepository(session)
        activity_ids = repository.list_latest_activity_ids(user_id=user_id, count=count)
        for activity_id in activity_ids:
            repository.enqueue_activity_note(user_id=user_id, activity_id=activity_id)
        session.commit()
        print(
            f"Queued coaching notes for activities {activity_ids} (existing notes are kept)."
        )
    finally:
        session.close()


def _show(*, user_id: int) -> None:
    session = SessionLocal()
    try:
        request = (
            session.query(TrainingPlanRequest)
            .filter_by(user_id=user_id)
            .order_by(TrainingPlanRequest.id.desc())
            .first()
        )
        if request:
            print(
                f"\n=== Running plan request {request.id} [{request.status}] {request.timezone}"
            )
            if request.last_error:
                print(request.last_error)
            _print_objective(request)
        for day in (
            session.query(TrainingPlanDay)
            .filter_by(user_id=user_id)
            .order_by(TrainingPlanDay.planned_date)
            .all()
        ):
            targets = (
                "Rest"
                if day.kind == "rest"
                else f"{float(day.distance_meters)/1000:g} km / {day.pace_seconds_per_km//60}:{day.pace_seconds_per_km%60:02d} min/km / {day.heart_rate_bpm} bpm"
            )
            print(f"{day.planned_date}: {targets} ({day.focus}) — {day.rationale}")
        notes = (
            session.query(ActivityCoachingNote)
            .filter(ActivityCoachingNote.user_id == user_id)
            .order_by(ActivityCoachingNote.activity_id.desc())
            .all()
        )
        for note in notes:
            print(
                f"\n=== Activity {note.activity_id} [{note.status}] {note.model or ''}"
            )
            if note.last_error:
                print(f"last error: {note.last_error}")
            for label, text in (
                ("Description", note.description),
                ("Summary", note.summary),
                ("Next", note.recommendation),
            ):
                if text:
                    print(
                        f"{label}:\n{textwrap.indent(textwrap.fill(text, 110), '  ')}"
                    )
        periods = (
            session.query(PeriodCoachingSummary)
            .filter(PeriodCoachingSummary.user_id == user_id)
            .order_by(
                PeriodCoachingSummary.period_start.desc(),
                PeriodCoachingSummary.period_type.asc(),
            )
            .all()
        )
        for period in periods:
            final = "final" if period.is_final else "in progress"
            print(
                f"\n=== {period.period_type} {period.period_start} [{period.status}, {final}]"
            )
            if period.last_error:
                print(f"last error: {period.last_error}")
            for label, text in (
                ("Summary", period.summary),
                ("Next", period.recommendation),
            ):
                if text:
                    print(
                        f"{label}:\n{textwrap.indent(textwrap.fill(text, 110), '  ')}"
                    )
    finally:
        session.close()


if __name__ == "__main__":
    main()
