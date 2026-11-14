"""Persistence boundary for explicitly enriching existing Garmin laps."""

from math import isclose

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Activity, ActivitySplits, GarminCredential, SyncJob, User
from app.services.split_backfill import (
    SplitBackfillTarget,
    SplitBackfillValidationError,
)

ELEVATION_FIELDS = ("elevation_gain_meters", "elevation_loss_meters")


def enrich_laps(stored: list[dict], fetched: list[dict]) -> list[dict]:
    if not stored:
        return fetched
    if len(stored) != len(fetched):
        raise SplitBackfillValidationError(
            "Recorded lap counts changed; review this activity before retrying."
        )
    result = []
    for old, new in zip(stored, fetched, strict=True):
        if old["number"] != new["number"] or any(
                not isclose(old[field], new[field], rel_tol=0, abs_tol=0.01)
                for field in (
                        "start_distance_meters",
                        "end_distance_meters",
                        "distance_meters",
                )
        ):
            raise SplitBackfillValidationError(
                "Recorded lap boundaries changed; review this activity before retrying."
            )
        # Copy the JSON tree so SQLAlchemy detects updates; preserve other recorded metrics and metadata.
        result.append(
            {
                **old,
                **{
                    field: (
                        new.get(field) if new.get(field) is not None else old.get(field)
                    )
                    for field in ELEVATION_FIELDS
                },
            }
        )
    return result


class SplitBackfillRepository:
    def __init__(self, session: Session):
        self.session = session

    def _credential(self, user_id: int) -> GarminCredential:
        credential = self.session.scalar(
            select(GarminCredential).where(GarminCredential.user_id == user_id)
        )
        if credential is None:
            raise SplitBackfillValidationError("Garmin credentials are missing.")
        return credential

    def _ensure_idle(self, user_id: int) -> None:
        active = self.session.scalar(
            select(SyncJob.id)
            .where(
                SyncJob.user_id == user_id, SyncJob.status.in_(("queued", "running"))
            )
            .limit(1)
        )
        if active is not None:
            raise SplitBackfillValidationError(
                "Finish the athlete's active sync before running a split backfill."
            )

    def get_token(self, user_id: int) -> str:
        user = self.session.get(User, user_id)
        if user is None or not user.is_active:
            raise SplitBackfillValidationError("The athlete is missing or disabled.")
        self._ensure_idle(user_id)
        credential = self._credential(user_id)
        if credential.connection_status != "connected":
            raise SplitBackfillValidationError(
                "Reconnect Garmin before running a split backfill."
            )
        return credential.token_json_encrypted

    def list_batch(
            self, user_id: int, after_id: int, batch_size: int
    ) -> list[SplitBackfillTarget]:
        self._ensure_idle(user_id)
        rows = self.session.execute(
            select(Activity.id, Activity.source_activity_id)
            .where(
                Activity.user_id == user_id,
                Activity.source_provider == "garmin",
                Activity.id > after_id,
            )
            .order_by(Activity.id)
            .limit(batch_size)
        )
        return [SplitBackfillTarget(row.id, row.source_activity_id) for row in rows]

    def save_token(self, user_id: int, encrypted_token: str) -> None:
        self._credential(user_id).token_json_encrypted = encrypted_token
        self.session.commit()

    def save_laps(
            self,
            user_id: int,
            target: SplitBackfillTarget,
            laps: list[dict],
            encrypted_token: str,
    ) -> bool:
        activity = self.session.get(Activity, target.activity_id)
        if (
                activity is None
                or activity.user_id != user_id
                or activity.source_provider != "garmin"
                or activity.source_activity_id != target.source_activity_id
        ):
            raise SplitBackfillValidationError(
                "The Garmin activity does not belong to this athlete."
            )
        row = self.session.get(ActivitySplits, target.activity_id)
        merged = enrich_laps(row.laps if row else [], laps)
        status = "ready" if merged else "unavailable"
        changed = row is None or row.laps != merged or row.status != status
        if row is None:
            self.session.add(
                ActivitySplits(
                    activity_id=target.activity_id, status=status, laps=merged
                )
            )
        else:
            row.laps = merged
            row.status = status
        self._credential(user_id).token_json_encrypted = encrypted_token
        self.session.commit()
        return changed

    def require_reauthentication(self, user_id: int) -> None:
        self._credential(user_id).connection_status = "reauthentication_required"
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()
