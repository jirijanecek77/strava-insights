import hashlib
import logging
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Activity, User
from app.repositories import (
    ActivityRepository,
    ActivityStreamRepository,
    SyncCheckpointRepository,
    UserRepository,
)
from app.services.activity_import_writer import ActivityImportWriter
from app.services.cache_invalidator import UserCacheInvalidator
from app.services.local_route_matcher import ROUTE_MODEL_VERSION
from app.services.read_model_builder import ReadModelBuilder
from app.services.route_index_builder import RouteIndexBuilder
from app.services.sync_import import (
    ANALYTICS_CHECKPOINT_TYPE,
    ANALYTICS_MODEL_VERSION,
    ROUTE_CHECKPOINT_TYPE,
)

FIT_IMPORT_PATH = Path("/imports/fit")
DUPLICATE_DISTANCE_TOLERANCE = 0.05
SUPPORTED_FIT_SPORTS = {"Run", "Ride", "EBikeRide"}
logger = logging.getLogger(__name__)


class FitImportError(Exception):
    pass


class UnsupportedFitSportError(FitImportError):
    pass


@dataclass(frozen=True, slots=True)
class ParsedFitActivity:
    source_activity_id: int
    payload: dict[str, Any]
    stream_payload: dict[str, Any] | None


@dataclass(frozen=True, slots=True)
class FitImportFailure:
    path: str
    reason: str


@dataclass(frozen=True, slots=True)
class FitImportDuplicate:
    path: str
    existing_activity_id: int | None
    reason: str


@dataclass(slots=True)
class FitImportSummary:
    scanned_files: int = 0
    imported_count: int = 0
    skipped_duplicate_count: int = 0
    skipped_unsupported_count: int = 0
    failed_count: int = 0
    duplicates: list[FitImportDuplicate] = field(default_factory=list)
    failures: list[FitImportFailure] = field(default_factory=list)


class FitFileParser:
    def __init__(self, *, local_timezone: str | None = None) -> None:
        self.local_timezone = self._load_timezone(
            local_timezone or settings.fit_import_timezone
        )

    def parse(self, path: Path) -> ParsedFitActivity:
        try:
            from fitparse import FitFile
        except ImportError as exc:
            raise FitImportError(
                "fitparse is not installed in the worker image."
            ) from exc

        fit_file = FitFile(str(path))
        records = [message.get_values() for message in fit_file.get_messages("record")]
        session = self._first_message_values(fit_file, "session")
        sport_payload = self._first_message_values(fit_file, "sport")

        sport_type = self._sport_type(session, sport_payload)
        if sport_type not in SUPPORTED_FIT_SPORTS:
            raise UnsupportedFitSportError(f"Unsupported FIT sport: {sport_type!r}")

        start_utc = self._start_datetime(session, records)
        start_local = start_utc.astimezone(self.local_timezone)
        source_activity_id = self._synthetic_source_activity_id(path)
        time_values = self._time_values(records, start_utc)
        distance_values = self._record_values(records, "distance")

        distance_meters = self._number(session.get("total_distance"))
        if distance_meters is None:
            distance_meters = self._last_numeric(distance_values) or 0.0

        moving_time = self._number(session.get("total_timer_time"))
        if moving_time is None:
            moving_time = self._last_numeric(time_values) or 0.0

        elapsed_time = self._number(session.get("total_elapsed_time"))
        if elapsed_time is None:
            elapsed_time = moving_time

        stream_payload = self._stream_payload(records, time_values)
        payload = {
            "id": source_activity_id,
            "name": self._activity_name(path, sport_type),
            "description": "Imported from local FIT file.",
            "type": sport_type,
            "start_date": start_utc.isoformat(),
            "start_date_local": start_local.isoformat(),
            "distance": distance_meters,
            "moving_time": round(moving_time),
            "elapsed_time": round(elapsed_time),
            "total_elevation_gain": self._number(session.get("total_ascent")),
            "average_speed": self._number(session.get("avg_speed")),
            "max_speed": self._number(session.get("max_speed")),
            "average_heartrate": self._number(session.get("avg_heart_rate")),
            "average_cadence": self._number(session.get("avg_cadence")),
        }
        return ParsedFitActivity(
            source_activity_id=source_activity_id,
            payload=payload,
            stream_payload=stream_payload,
        )

    @staticmethod
    def _first_message_values(fit_file: Any, name: str) -> dict[str, Any]:
        for message in fit_file.get_messages(name):
            return message.get_values()
        return {}

    @staticmethod
    def _load_timezone(value: str) -> ZoneInfo:
        try:
            return ZoneInfo(value)
        except ZoneInfoNotFoundError:
            logger.warning(
                "Invalid FIT import timezone; falling back to UTC.",
                extra={"timezone": value},
            )
            return ZoneInfo("UTC")

    @staticmethod
    def _sport_type(
        session: dict[str, Any], sport_payload: dict[str, Any]
    ) -> str | None:
        sport = FitFileParser._normalized_text(
            session.get("sport") or sport_payload.get("sport")
        )
        sub_sport = FitFileParser._normalized_text(
            session.get("sub_sport") or sport_payload.get("sub_sport")
        )
        if sport in {"running", "run"}:
            return "Run"
        if sport in {"cycling", "biking", "bike"}:
            if sub_sport in {
                "ebike",
                "e_bike",
                "e_biking",
                "electric_bike",
                "electricbike",
            }:
                return "EBikeRide"
            return "Ride"
        return None

    @staticmethod
    def _normalized_text(value: Any) -> str | None:
        if value is None:
            return None
        return str(value).strip().lower().replace(" ", "_").replace("-", "_")

    @staticmethod
    def _start_datetime(
        session: dict[str, Any], records: list[dict[str, Any]]
    ) -> datetime:
        value = session.get("start_time") or session.get("timestamp")
        if value is None and records:
            value = records[0].get("timestamp")
        if not isinstance(value, datetime):
            raise FitImportError(
                "FIT file does not contain a valid activity start time."
            )
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @staticmethod
    def _synthetic_source_activity_id(path: Path) -> int:
        digest = hashlib.sha256(path.read_bytes()).digest()
        positive_value = int.from_bytes(digest[:8], byteorder="big") & ((1 << 63) - 1)
        return -(positive_value or 1)

    @staticmethod
    def _time_values(
        records: list[dict[str, Any]], start_utc: datetime
    ) -> list[float | None]:
        values: list[float | None] = []
        for record in records:
            timestamp = record.get("timestamp")
            if not isinstance(timestamp, datetime):
                values.append(None)
                continue
            timestamp_utc = (
                timestamp.replace(tzinfo=UTC)
                if timestamp.tzinfo is None
                else timestamp.astimezone(UTC)
            )
            values.append(max(0.0, (timestamp_utc - start_utc).total_seconds()))
        return values

    @staticmethod
    def _record_values(
        records: list[dict[str, Any]], field_name: str
    ) -> list[float | None]:
        return [FitFileParser._number(record.get(field_name)) for record in records]

    @staticmethod
    def _stream_payload(
        records: list[dict[str, Any]], time_values: list[float | None]
    ) -> dict[str, Any] | None:
        if not records:
            return None
        distance_values = FitFileParser._record_values(records, "distance")
        speed_values = [
            FitFileParser._number(
                record.get("enhanced_speed")
                if record.get("enhanced_speed") is not None
                else record.get("speed")
            )
            for record in records
        ]
        altitude_values = [
            FitFileParser._number(
                record.get("enhanced_altitude")
                if record.get("enhanced_altitude") is not None
                else record.get("altitude")
            )
            for record in records
        ]
        latlng_values = [
            FitFileParser._latlng(
                record.get("position_lat"), record.get("position_long")
            )
            for record in records
        ]
        return {
            "time": {"data": time_values},
            "distance": {"data": distance_values},
            "latlng": {"data": latlng_values},
            "altitude": {"data": altitude_values},
            "velocity_smooth": {"data": speed_values},
            "heartrate": {"data": FitFileParser._record_values(records, "heart_rate")},
        }

    @staticmethod
    def _latlng(latitude: Any, longitude: Any) -> list[float] | None:
        lat = FitFileParser._coordinate_degrees(latitude)
        lng = FitFileParser._coordinate_degrees(longitude)
        if lat is None or lng is None:
            return None
        return [lat, lng]

    @staticmethod
    def _coordinate_degrees(value: Any) -> float | None:
        numeric = FitFileParser._number(value)
        if numeric is None:
            return None
        if -180 <= numeric <= 180:
            return numeric
        return numeric * (180.0 / (2**31))

    @staticmethod
    def _activity_name(path: Path, sport_type: str) -> str:
        return f"{sport_type} from {path.stem}"

    @staticmethod
    def _number(value: Any) -> float | None:
        if isinstance(value, bool) or value is None:
            return None
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        return numeric

    @staticmethod
    def _last_numeric(values: list[float | None]) -> float | None:
        for value in reversed(values):
            if value is not None:
                return value
        return None


class FitDuplicateMatcher:
    def __init__(self, existing_activities: list[Activity]) -> None:
        self.existing_activities = existing_activities

    def find_duplicate(self, parsed: ParsedFitActivity) -> Activity | None:
        imported_date = self._payload_date(parsed.payload)
        imported_distance = float(parsed.payload.get("distance") or 0)
        imported_sport = parsed.payload.get("type")
        if imported_date is None or imported_distance <= 0:
            return None
        for activity in self.existing_activities:
            if activity.strava_activity_id == parsed.source_activity_id:
                return activity
            if imported_sport and activity.sport_type != imported_sport:
                continue
            if self._activity_date(activity) != imported_date:
                continue
            existing_distance = float(activity.distance_meters or 0)
            if abs(existing_distance - imported_distance) <= (
                imported_distance * DUPLICATE_DISTANCE_TOLERANCE
            ):
                return activity
        return None

    def add_imported(self, activity: Activity) -> None:
        self.existing_activities.append(activity)

    @staticmethod
    def _payload_date(payload: dict[str, Any]) -> date | None:
        parsed = ActivityImportWriter.parse_datetime(
            payload.get("start_date_local") or payload.get("start_date")
        )
        return None if parsed is None else parsed.date()

    @staticmethod
    def _activity_date(activity: Activity) -> date | None:
        value = activity.start_date_local or activity.start_date_utc
        return None if value is None else value.date()


class FitImportService:
    def __init__(
        self,
        session: Session,
        *,
        parser: FitFileParser | None = None,
        cache_invalidator: UserCacheInvalidator | None = None,
        read_model_builder: ReadModelBuilder | None = None,
        route_index_builder: RouteIndexBuilder | None = None,
    ) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.activities = ActivityRepository(session)
        self.activity_streams = ActivityStreamRepository(session)
        self.checkpoints = SyncCheckpointRepository(session)
        self.writer = ActivityImportWriter(
            activities=self.activities, activity_streams=self.activity_streams
        )
        self.parser = parser or FitFileParser()
        self.cache_invalidator = cache_invalidator or UserCacheInvalidator()
        self.read_model_builder = read_model_builder or ReadModelBuilder(session)
        self.route_index_builder = route_index_builder or RouteIndexBuilder(session)

    def run(self, *, import_path: Path = FIT_IMPORT_PATH) -> FitImportSummary:
        user = self._single_user()
        files = sorted(import_path.rglob("*.fit"))
        summary = FitImportSummary(scanned_files=len(files))
        matcher = FitDuplicateMatcher(self.activities.list_for_user(user.id))

        logger.info(
            "Starting local FIT import.",
            extra={"user.id": user.id, "fit.file_count": len(files)},
        )
        for path in files:
            try:
                parsed = self.parser.parse(path)
                duplicate = matcher.find_duplicate(parsed)
                if duplicate is not None:
                    summary.skipped_duplicate_count += 1
                    summary.duplicates.append(
                        FitImportDuplicate(
                            path=str(path),
                            existing_activity_id=duplicate.id,
                            reason="same date, sport, and distance within 5%",
                        )
                    )
                    continue
                activity = self.writer.upsert_activity(
                    user_id=user.id, payload=parsed.payload
                )
                if parsed.stream_payload is not None:
                    self.writer.upsert_stream(
                        activity=activity, payload=parsed.stream_payload
                    )
                self.session.commit()
                matcher.add_imported(activity)
                summary.imported_count += 1
                logger.info(
                    "Imported local FIT activity.",
                    extra={
                        "user.id": user.id,
                        "activity.id": activity.id,
                        "fit.path": str(path),
                    },
                )
            except UnsupportedFitSportError as exc:
                self.session.rollback()
                summary.skipped_unsupported_count += 1
                summary.failures.append(
                    FitImportFailure(path=str(path), reason=str(exc))
                )
            except Exception as exc:
                self.session.rollback()
                summary.failed_count += 1
                summary.failures.append(
                    FitImportFailure(path=str(path), reason=str(exc))
                )
                logger.exception(
                    "Failed to import local FIT file.",
                    extra={"user.id": user.id, "fit.path": str(path)},
                )

        self._rebuild_read_models(user.id)
        self.session.commit()
        logger.info(
            "Completed local FIT import.",
            extra={
                "user.id": user.id,
                "fit.scanned_files": summary.scanned_files,
                "fit.imported_count": summary.imported_count,
                "fit.skipped_duplicate_count": summary.skipped_duplicate_count,
                "fit.skipped_unsupported_count": summary.skipped_unsupported_count,
                "fit.failed_count": summary.failed_count,
            },
        )
        return summary

    def _single_user(self) -> User:
        users = self.users.list_all()
        if len(users) != 1:
            raise FitImportError(
                f"Expected exactly one user in the database, found {len(users)}."
            )
        return users[0]

    def _rebuild_read_models(self, user_id: int) -> None:
        self.read_model_builder.rebuild_for_user(user_id, source_run_efforts={})
        self.checkpoints.upsert(
            user_id=user_id,
            sync_type=ANALYTICS_CHECKPOINT_TYPE,
            checkpoint_value=ANALYTICS_MODEL_VERSION,
            last_synced_at=datetime.now(UTC),
        )
        try:
            self.route_index_builder.rebuild_for_user(user_id)
            self.checkpoints.upsert(
                user_id=user_id,
                sync_type=ROUTE_CHECKPOINT_TYPE,
                checkpoint_value=ROUTE_MODEL_VERSION,
                last_synced_at=datetime.now(UTC),
            )
        except Exception:
            logger.exception(
                "Local route index rebuild failed after FIT import.",
                extra={"user.id": user_id},
            )
        self.cache_invalidator.invalidate_user(user_id)
