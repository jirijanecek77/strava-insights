"""PostgreSQL adapter for durable planning requests and atomic plan publication."""

import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import and_, exists, or_, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import aliased

from app.models import (
    Activity,
    ActivityCoachingNote,
    SyncJob,
    TrainingPlanDay,
    TrainingPlanRequest,
    User,
    UserThresholdProfile,
)
from app.services.planning.policy import PROMPT_VERSION, training_bounds


class PlanningRepository:
    def __init__(self, session):
        self.session = session

    def _lock_user(self, user_id):
        # Enqueue and publication serialize per athlete, including across worker processes.
        self.session.execute(
            text("SELECT pg_advisory_xact_lock(74022, :user_id)"), {"user_id": user_id}
        )

    def enqueue(
        self, *, user_id: int, timezone: str, sync_job_id: int | None = None
    ) -> int:
        ZoneInfo(timezone)
        self._lock_user(user_id)
        key = f"sync:{sync_job_id}" if sync_job_id else f"manual:{uuid4()}"
        self.session.execute(
            insert(TrainingPlanRequest)
            .values(
                user_id=user_id,
                sync_job_id=sync_job_id,
                source_key=key,
                timezone=timezone,
                status="pending",
                attempt_count=0,
            )
            .on_conflict_do_nothing(index_elements=["user_id", "source_key"])
        )
        return self.session.scalar(
            select(TrainingPlanRequest.id).where(
                TrainingPlanRequest.user_id == user_id,
                TrainingPlanRequest.source_key == key,
            )
        )

    def claim(self, *, user_id: int | None = None):
        now = datetime.now(UTC)
        newer = aliased(TrainingPlanRequest)
        active_sync = exists().where(
            SyncJob.user_id == TrainingPlanRequest.user_id,
            SyncJob.status.in_(["queued", "running"]),
        )
        successful_sync = exists().where(
            SyncJob.user_id == TrainingPlanRequest.user_id,
            SyncJob.status == "completed",
            or_(
                SyncJob.id == TrainingPlanRequest.sync_job_id,
                SyncJob.finished_at >= TrainingPlanRequest.created_at,
            ),
        )
        query = (
            self.session.query(TrainingPlanRequest)
            .join(User, User.id == TrainingPlanRequest.user_id)
            .filter(
                User.is_active.is_(True),
                ~active_sync,
                or_(TrainingPlanRequest.sync_job_id.is_(None), successful_sync),
                ~exists().where(
                    newer.user_id == TrainingPlanRequest.user_id,
                    newer.id > TrainingPlanRequest.id,
                ),
                or_(
                    and_(
                        TrainingPlanRequest.status == "pending",
                        or_(
                            TrainingPlanRequest.next_attempt_at.is_(None),
                            TrainingPlanRequest.next_attempt_at <= now,
                        ),
                    ),
                    and_(
                        TrainingPlanRequest.status == "generating",
                        TrainingPlanRequest.lease_expires_at <= now,
                    ),
                ),
            )
        )
        if user_id is not None:
            query = query.filter(TrainingPlanRequest.user_id == user_id)
        row = (
            query.order_by(TrainingPlanRequest.id)
            .with_for_update(of=TrainingPlanRequest, skip_locked=True)
            .first()
        )
        if row is None:
            self.session.commit()
            return None
        row.status = "generating"
        row.lease_token = str(uuid4())
        row.lease_expires_at = now + timedelta(minutes=5)
        self.session.commit()
        # Return detached values: another worker must not replace our lease token through ORM refresh.
        return {
            "id": row.id,
            "user_id": row.user_id,
            "timezone": row.timezone,
            "lease_token": row.lease_token,
            "attempt_count": row.attempt_count,
            "context": row.context_json,
            "last_error": row.last_error,
        }

    def build_context(self, request: dict, today: date) -> dict:
        if request["context"]:
            if request["context"].get("policy_version") == PROMPT_VERSION:
                return request["context"]
            # Upgrade a queued legacy context without moving its requested dates or creating new work.
            context = dict(request["context"])
            return self._apply_objective(request, context)
        user_id = request["user_id"]
        since = datetime.combine(
            today - timedelta(days=41),
            datetime.min.time(),
            tzinfo=ZoneInfo(request["timezone"]),
        )
        until = datetime.combine(
            today + timedelta(days=1),
            datetime.min.time(),
            tzinfo=ZoneInfo(request["timezone"]),
        )
        rows = (
            self.session.query(Activity, ActivityCoachingNote.summary)
            .outerjoin(
                ActivityCoachingNote, ActivityCoachingNote.activity_id == Activity.id
            )
            .filter(
                Activity.user_id == user_id,
                Activity.start_date_utc >= since,
                Activity.start_date_utc < until,
                Activity.sport_type.in_(["Run", "Ride", "EBikeRide"]),
            )
            .order_by(Activity.start_date_utc)
            .all()
        )
        activities = []
        for a, summary in rows:
            local_date = (
                a.start_date_local
                or a.start_date_utc.astimezone(ZoneInfo(request["timezone"]))
            ).date()
            activities.append(
                {
                    "date": local_date.isoformat(),
                    "sport": a.sport_type,
                    "distance_km": round(float(a.distance_meters) / 1000, 2),
                    "moving_minutes": round(a.moving_time_seconds / 60, 1),
                    "elevation_gain_meters": (
                        float(a.total_elevation_gain_meters)
                        if a.total_elevation_gain_meters is not None
                        else None
                    ),
                    "pace_seconds_per_km": (
                        float(a.average_pace_seconds_per_km)
                        if a.average_pace_seconds_per_km
                        else (
                            a.moving_time_seconds * 1000 / float(a.distance_meters)
                            if a.distance_meters
                            else None
                        )
                    ),
                    "hr_bpm": (
                        float(a.average_heartrate_bpm)
                        if a.average_heartrate_bpm
                        else None
                    ),
                    "coaching_summary": summary,
                }
            )
        profiles = (
            self.session.query(UserThresholdProfile)
            .filter(
                UserThresholdProfile.user_id == user_id,
                UserThresholdProfile.effective_from <= today,
            )
            .order_by(UserThresholdProfile.effective_from.desc())
            .all()
        )
        fields = (
            "aet_heart_rate_bpm",
            "ant_heart_rate_bpm",
            "aet_pace_min_per_km",
            "ant_pace_min_per_km",
        )
        profile = profiles[0] if profiles else None
        thresholds = {
            field: (
                float(getattr(profile, field))
                if profile and getattr(profile, field) is not None
                else None
            )
            for field in fields
        }
        dates = [(today + timedelta(days=i)).isoformat() for i in range(1, 8)]
        prior = (
            self.session.query(TrainingPlanDay)
            .filter(
                TrainingPlanDay.user_id == user_id,
                TrainingPlanDay.planned_date >= today - timedelta(days=14),
            )
            .order_by(TrainingPlanDay.planned_date)
            .all()
        )
        return self._apply_objective(
            request,
            {
                "today": today.isoformat(),
                "dates": dates,
                "timezone": request["timezone"],
                "thresholds": thresholds,
                "activities": activities,
                "previous_plans": [
                    {
                        "date": d.planned_date.isoformat(),
                        "kind": d.kind,
                        "focus": d.focus,
                        "distance_km": (
                            float(d.distance_meters) / 1000
                            if d.distance_meters
                            else None
                        ),
                        "pace_seconds_per_km": d.pace_seconds_per_km,
                        "heart_rate_bpm": d.heart_rate_bpm,
                        "rationale": d.rationale,
                    }
                    for d in prior
                ],
            },
        )

    def _apply_objective(self, request, context):
        previous = (
            self.session.query(TrainingPlanRequest)
            .filter(
                TrainingPlanRequest.user_id == request["user_id"],
                TrainingPlanRequest.id < request["id"],
                TrainingPlanRequest.status == "ready",
                TrainingPlanRequest.prompt_version == PROMPT_VERSION,
            )
            .order_by(TrainingPlanRequest.id.desc())
            .first()
        )
        previous_objective = (
            (previous.context_json or {}).get("weekly_objective") if previous else None
        )
        bounds = training_bounds(
            context["activities"],
            context["thresholds"],
            date.fromisoformat(context["today"]),
            previous_objective=previous_objective,
        )
        objective = bounds.pop("weekly_objective")
        return {
            **context,
            "policy_version": PROMPT_VERSION,
            "bounds": bounds,
            "weekly_objective": objective,
        }

    def _owned(self, request):
        self._lock_user(request["user_id"])
        row = (
            self.session.query(TrainingPlanRequest)
            .filter(TrainingPlanRequest.id == request["id"])
            .populate_existing()
            .with_for_update()
            .one()
        )
        if (
            row.status != "generating"
            or row.lease_token != request["lease_token"]
            or row.lease_expires_at <= datetime.now(UTC)
        ):
            self.session.commit()
            return None
        newer = self.session.scalar(
            select(TrainingPlanRequest.id)
            .where(
                TrainingPlanRequest.user_id == row.user_id,
                TrainingPlanRequest.id > row.id,
            )
            .limit(1)
        )
        if newer:
            row.status = "superseded"
            row.lease_token = row.lease_expires_at = None
            self.session.commit()
            return None
        return row

    def save_context(self, request, context):
        row = self._owned(request)
        if row is None:
            return False
        row.context_json = context
        row.target_start = date.fromisoformat(context["dates"][0])
        row.source_hash = hashlib.sha256(
            json.dumps(context, sort_keys=True).encode()
        ).hexdigest()
        row.prompt_version = PROMPT_VERSION
        self.session.commit()
        return True

    def finish(self, request, *, status, error=None, delay=None, attempts=None):
        row = self._owned(request)
        if row is None:
            return
        row.status = status
        row.last_error = error[:1000] if error else None
        row.attempt_count = attempts if attempts is not None else row.attempt_count
        row.next_attempt_at = (
            datetime.now(UTC) + timedelta(seconds=delay) if delay else None
        )
        row.lease_token = row.lease_expires_at = None
        self.session.commit()

    def publish(self, request, days, *, model, today):
        row = self._owned(request)
        if row is None:
            return False
        # Any import that began during the model request invalidates publication until it finishes.
        active = self.session.scalar(
            select(SyncJob.id)
            .where(
                SyncJob.user_id == row.user_id,
                SyncJob.status.in_(["queued", "running"]),
            )
            .limit(1)
        )
        if active:
            row.status = "pending"
            row.context_json = None
            row.lease_token = row.lease_expires_at = None
            self.session.commit()
            return False
        now = datetime.now(UTC)
        for day in days:
            planned_date = date.fromisoformat(day["date"])
            if planned_date <= today:
                continue
            values = dict(
                user_id=row.user_id,
                request_id=row.id,
                planned_date=planned_date,
                kind=day["kind"],
                focus=day["focus"],
                distance_meters=(
                    round(day["distance_km"] * 1000, 2)
                    if day["distance_km"] is not None
                    else None
                ),
                pace_seconds_per_km=day["pace_seconds_per_km"],
                heart_rate_bpm=day["heart_rate_bpm"],
                rationale=day["rationale"].strip(),
                generated_at=now,
            )
            self.session.execute(
                insert(TrainingPlanDay)
                .values(**values)
                .on_conflict_do_update(
                    index_elements=["user_id", "planned_date"],
                    set_={
                        k: v
                        for k, v in values.items()
                        if k not in ("user_id", "planned_date")
                    },
                )
            )
        row.status = "ready"
        row.model = model
        row.generated_at = now
        row.last_error = None
        row.next_attempt_at = None
        row.lease_token = row.lease_expires_at = None
        self.session.commit()
        return True
