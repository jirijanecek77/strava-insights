"""Explicit historical Garmin lap enrichment; no activity import or AI generation."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from math import isfinite
from time import sleep as time_sleep
from typing import Protocol

import requests
from garminconnect import (
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

from app.garmin_client import GarminAuthenticationError, GarminSession


@dataclass(frozen=True, slots=True)
class SplitBackfillTarget:
    activity_id: int
    source_activity_id: int


@dataclass(frozen=True, slots=True)
class SplitBackfillProgress:
    after_id: int = 0
    processed: int = 0
    updated: int = 0


class SplitBackfillError(RuntimeError):
    def __init__(self, message: str, *, after_id: int, activity_id: int | None = None):
        super().__init__(message)
        self.after_id = after_id
        self.activity_id = activity_id


class SplitBackfillValidationError(ValueError):
    """An operator-facing validation message containing no provider response data."""


class SplitBackfillStore(Protocol):
    def get_token(self, user_id: int) -> str: ...

    def list_batch(
            self, user_id: int, after_id: int, batch_size: int
    ) -> list[SplitBackfillTarget]: ...

    def save_token(self, user_id: int, encrypted_token: str) -> None: ...

    def save_laps(
            self,
            user_id: int,
            target: SplitBackfillTarget,
            laps: list[dict],
            encrypted_token: str,
    ) -> bool: ...

    def require_reauthentication(self, user_id: int) -> None: ...

    def rollback(self) -> None: ...


class SplitBackfillGarmin(Protocol):
    def connect(self, token_json: str) -> GarminSession: ...

    def get_activity_splits(
            self, session: GarminSession, activity_id: int
    ) -> list[dict]: ...


class TokenEncryption(Protocol):
    def encrypt(self, value: str) -> str: ...

    def decrypt(self, value: str) -> str: ...


class SplitCacheInvalidator(Protocol):
    def invalidate_user(self, user_id: int) -> int: ...


class SplitBackfillService:
    def __init__(
            self,
            repository: SplitBackfillStore,
            garmin: SplitBackfillGarmin,
            cipher: TokenEncryption,
            cache: SplitCacheInvalidator,
            *,
            sleep: Callable[[float], None] = time_sleep,
            on_progress: Callable[[SplitBackfillProgress], None] | None = None,
    ):
        self.repository = repository
        self.garmin = garmin
        self.cipher = cipher
        self.cache = cache
        self.sleep = sleep
        self.on_progress = on_progress

    def run(
            self,
            *,
            user_id: int,
            batch_size: int = 100,
            delay_seconds: float = 1,
            after_id: int = 0,
    ) -> SplitBackfillProgress:
        if user_id < 1 or after_id < 0 or not 1 <= batch_size <= 1000:
            raise ValueError(
                "Use a positive user ID, nonnegative cursor, and batch size between 1 and 1000."
            )
        if not isfinite(delay_seconds) or delay_seconds < 0:
            raise ValueError("The request delay must be finite and nonnegative.")
        progress = SplitBackfillProgress(after_id=after_id)
        target = None
        try:
            token = self.cipher.decrypt(self.repository.get_token(user_id))
            garmin_session = self.garmin.connect(token)
            self.repository.save_token(
                user_id, self.cipher.encrypt(garmin_session.token_json())
            )
            while batch := self.repository.list_batch(
                    user_id, progress.after_id, batch_size
            ):
                for target in batch:
                    if progress.processed and delay_seconds:
                        self.sleep(delay_seconds)
                    laps = self._fetch(
                        user_id, garmin_session, target.source_activity_id
                    )
                    changed = self.repository.save_laps(
                        user_id,
                        target,
                        laps,
                        self.cipher.encrypt(garmin_session.token_json()),
                    )
                    # Invalidate even on a repeated lap import so resuming also repairs a failed cache invalidation.
                    self.cache.invalidate_user(user_id)
                    progress = SplitBackfillProgress(
                        target.activity_id,
                        progress.processed + 1,
                        progress.updated + int(changed),
                    )
                    if self.on_progress:
                        self.on_progress(progress)
            return progress
        except Exception as exc:
            self.repository.rollback()
            if isinstance(exc, GarminAuthenticationError):
                self.repository.require_reauthentication(user_id)
            raise SplitBackfillError(
                "Garmin split backfill stopped; existing activity data was preserved.",
                after_id=progress.after_id,
                activity_id=target.activity_id if target else None,
            ) from exc

    def _fetch(
            self, user_id: int, session: GarminSession, source_id: int
    ) -> list[dict]:
        for attempt in range(3):
            try:
                return self.garmin.get_activity_splits(session, source_id)
            except (
                    requests.ConnectionError,
                    requests.Timeout,
                    requests.HTTPError,
                    GarminConnectConnectionError,
                    GarminConnectTooManyRequestsError,
            ) as exc:
                # A request can refresh the session before failing; preserve rotated tokens before retrying.
                self.repository.save_token(
                    user_id, self.cipher.encrypt(session.token_json())
                )
                if attempt == 2:
                    raise
                response = getattr(exc, "response", None)
                status = getattr(response, "status_code", None)
                if isinstance(exc, requests.HTTPError) and status is None:
                    raise
                if status is not None and 400 <= status < 500 and status != 429:
                    raise
                retry_after = str(
                    getattr(response, "headers", {}).get("Retry-After", "")
                )
                try:
                    delay = float(retry_after)
                except (TypeError, ValueError):
                    try:
                        delay = (
                                parsedate_to_datetime(retry_after) - datetime.now(UTC)
                        ).total_seconds()
                    except (TypeError, ValueError, OverflowError):
                        delay = 2 ** (attempt + 1)
                if not isfinite(delay) or delay > 60:
                    # Leave the cursor unchanged for a later operator retry, honoring a long provider cooldown.
                    raise
                self.sleep(max(2 ** (attempt + 1), delay))
        raise AssertionError("Unreachable retry state")
