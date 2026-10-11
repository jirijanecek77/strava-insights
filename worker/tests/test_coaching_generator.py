from dataclasses import dataclass
from datetime import UTC, date, datetime

from app.services.coaching.context_builder import PeriodContext
from app.services.coaching.generator import MAX_ATTEMPTS, CoachingGenerator
from app.services.coaching.llm_client import LlmCompletion, LlmError, LlmRateLimitedError

TODAY = date(2026, 10, 11)


@dataclass
class Row:
    user_id: int
    status: str = "pending"
    attempt_count: int = 0
    activity_id: int | None = None
    period_type: str | None = None
    period_start: date | None = None
    description: str | None = None
    summary: str | None = None
    recommendation: str | None = None
    source_hash: str | None = None
    is_final: bool = False
    last_error: str | None = None
    retry_delay: int | None = None


class InMemoryCoachingRepository:
    def __init__(self, notes: list[Row], activity_dates: dict[int, datetime]) -> None:
        self.notes = notes
        self.periods: list[Row] = []
        self.activity_dates = activity_dates

    def claim_next_activity_note(self, *, user_id=None):
        return self._claim(self.notes, user_id)

    def claim_next_period(self, *, user_id=None):
        weeks_first = sorted(self.periods, key=lambda row: (row.period_type != "week", row.period_start))
        return self._claim(weeks_first, user_id)

    def mark_activity_note_ready(self, note, *, description, summary, recommendation, model, prompt_version):
        note.status, note.description, note.summary, note.recommendation = "ready", description, summary, recommendation

    def mark_period_ready(self, period, *, summary, recommendation, source_hash, is_final, model, prompt_version):
        period.status, period.summary, period.recommendation = "ready", summary, recommendation
        period.source_hash, period.is_final = source_hash, is_final

    def release_for_retry(self, row, *, error_message, delay_seconds, attempt_count):
        row.status, row.last_error, row.retry_delay, row.attempt_count = "deferred", error_message, delay_seconds, attempt_count

    def mark_failed(self, row, *, error_message, attempt_count, source_hash=None):
        row.status, row.last_error, row.attempt_count = "failed", error_message, attempt_count
        if source_hash is not None:
            row.source_hash = source_hash

    def list_users_with_recent_notes(self, *, since, user_id=None):
        return sorted({note.user_id for note in self.notes if note.status == "ready"})

    def list_recent_note_activity_dates(self, *, user_id, since):
        return [
            self.activity_dates[note.activity_id]
            for note in self.notes
            if note.user_id == user_id and note.status == "ready"
        ]

    def get_or_create_period(self, *, user_id, period_type, period_start):
        for period in self.periods:
            if (period.user_id, period.period_type, period.period_start) == (user_id, period_type, period_start):
                return period
        period = Row(user_id=user_id, period_type=period_type, period_start=period_start)
        self.periods.append(period)
        return period

    def mark_period_pending(self, period):
        period.status, period.attempt_count = "pending", 0

    def commit(self):
        return None

    @staticmethod
    def _claim(rows, user_id):
        for row in rows:
            if row.status == "pending" and (user_id is None or row.user_id == user_id):
                row.status = "generating"
                return row
        return None


class ContextBuilderStub:
    def __init__(self, repository: InMemoryCoachingRepository) -> None:
        self.repository = repository
        self.source_hash = "hash-1"
        self.is_final = False

    def build_activity_context(self, *, user_id, activity_id):
        return {"activity": {"id": activity_id}}

    def build_period_context(self, *, user_id, period_type, period_start, today):
        notes = [note for note in self.repository.notes if note.user_id == user_id]
        return PeriodContext(
            context={"period_type": period_type, "in_progress": not self.is_final},
            source_hash=self.source_hash,
            is_final=self.is_final,
            has_pending_notes=any(note.status in {"pending", "generating", "deferred"} for note in notes),
            has_ready_notes=any(note.status == "ready" for note in notes),
        )


class ScriptedLlm:
    model = "gemini-test"

    def __init__(self, *responses) -> None:
        self.responses = list(responses)
        self.prompts: list[str] = []

    def complete_json(self, *, system_prompt, user_prompt):
        self.prompts.append(system_prompt)
        response = self.responses.pop(0) if self.responses else _default_response(system_prompt)
        if isinstance(response, Exception):
            raise response
        return LlmCompletion(payload=response, model=self.model)


def _default_response(system_prompt: str) -> dict:
    if "one training activity" in system_prompt:
        return {"description": "Solid run.", "summary": "Easy 10 km.", "recommendation": "Rest tomorrow."}
    return {"summary": "Good period.", "recommendation": "Keep it up."}


def _generator(repository, llm, *, configured=True, batch_size=10):
    builder = ContextBuilderStub(repository)
    return CoachingGenerator(
        repository=repository,
        llm_client=llm,
        context_builder=builder,
        is_configured=configured,
        batch_size=batch_size,
        today=lambda: TODAY,
    ), builder


def _repository(*notes: Row) -> InMemoryCoachingRepository:
    return InMemoryCoachingRepository(
        list(notes), {note.activity_id: datetime(2026, 10, 7, 7, tzinfo=UTC) for note in notes}
    )


def test_generates_activity_note_then_week_and_month_reviews() -> None:
    repository = _repository(Row(user_id=1, activity_id=10))
    llm = ScriptedLlm()
    generator, _ = _generator(repository, llm)

    stats = generator.run()

    note = repository.notes[0]
    assert (note.status, note.summary, note.recommendation) == ("ready", "Easy 10 km.", "Rest tomorrow.")
    assert sorted((period.period_type, period.period_start, period.status) for period in repository.periods) == [
        ("month", date(2026, 10, 1), "ready"),
        ("week", date(2026, 10, 5), "ready"),
    ]
    assert all(period.summary == "Good period." for period in repository.periods)
    assert stats.activity_notes_generated == 1
    assert stats.period_summaries_generated == 2
    assert "one training week" in llm.prompts[1]
    assert "one training month" in llm.prompts[2]


def test_unchanged_periods_are_not_regenerated_until_they_end() -> None:
    repository = _repository(Row(user_id=1, activity_id=10))
    generator, builder = _generator(repository, ScriptedLlm())
    generator.run()

    assert generator.run().period_summaries_generated == 0

    builder.is_final = True
    stats = generator.run()
    assert stats.period_summaries_generated == 2
    assert all(period.is_final for period in repository.periods)

    builder.source_hash = "hash-2"
    assert generator.run().period_summaries_generated == 2


def test_period_reviews_wait_for_pending_activity_notes() -> None:
    repository = _repository(Row(user_id=1, activity_id=10), Row(user_id=1, activity_id=11))
    generator, _ = _generator(repository, ScriptedLlm(), batch_size=1)

    stats = generator.run()

    assert stats.activity_notes_generated == 1
    assert repository.periods == []


def test_rate_limit_defers_without_counting_an_attempt_and_stops_the_run() -> None:
    repository = _repository(Row(user_id=1, activity_id=10), Row(user_id=1, activity_id=11))
    llm = ScriptedLlm(LlmRateLimitedError("quota", retry_after_seconds=37))
    generator, _ = _generator(repository, llm)

    stats = generator.run()

    first, second = repository.notes
    assert stats.rate_limited is True
    assert (first.status, first.attempt_count, first.retry_delay) == ("deferred", 0, 37)
    assert second.status == "pending"
    assert len(llm.prompts) == 1


def test_repeated_failures_back_off_and_finally_fail() -> None:
    note = Row(user_id=1, activity_id=10)
    repository = _repository(note)
    generator, _ = _generator(repository, ScriptedLlm(LlmError("boom")))

    generator.run()
    assert (note.status, note.attempt_count, note.retry_delay) == ("deferred", 1, 300)

    note.status, note.attempt_count = "pending", MAX_ATTEMPTS - 1
    generator.llm_client = ScriptedLlm(LlmError("boom"))
    stats = generator.run()
    assert (note.status, note.attempt_count, note.last_error) == ("failed", MAX_ATTEMPTS, "boom")
    assert stats.failures == 1


def test_invalid_model_answer_is_retried() -> None:
    note = Row(user_id=1, activity_id=10)
    repository = _repository(note)
    generator, _ = _generator(repository, ScriptedLlm({"description": "Only a description."}))

    generator.run()

    assert note.status == "deferred"
    assert "summary" in (note.last_error or "")


def test_failed_period_is_not_requeued_until_its_inputs_change() -> None:
    repository = _repository(Row(user_id=1, activity_id=10))
    week_error = [LlmError("boom")] * MAX_ATTEMPTS
    generator, builder = _generator(repository, ScriptedLlm())
    repository.notes[0].status = "ready"
    repository.notes[0].summary = "Easy 10 km."
    repository.periods.append(
        Row(user_id=1, period_type="week", period_start=date(2026, 10, 5), attempt_count=MAX_ATTEMPTS - 1)
    )
    generator.llm_client = ScriptedLlm(*week_error)

    generator.run()
    week = repository.periods[0]
    assert (week.status, week.source_hash) == ("failed", "hash-1")

    generator.llm_client = ScriptedLlm()
    generator.run()
    assert week.status == "failed"

    builder.source_hash = "hash-2"
    generator.run()
    assert week.status == "ready"


def test_missing_api_key_skips_without_claiming_work() -> None:
    note = Row(user_id=1, activity_id=10)
    generator, _ = _generator(_repository(note), ScriptedLlm(), configured=False)

    stats = generator.run()

    assert stats.skipped_reason == "llm_not_configured"
    assert note.status == "pending"


def test_missing_activity_marks_note_failed() -> None:
    note = Row(user_id=1, activity_id=10)
    repository = _repository(note)
    generator, builder = _generator(repository, ScriptedLlm())
    builder.build_activity_context = lambda **_kwargs: None

    generator.run()

    assert (note.status, note.last_error) == ("failed", "Activity no longer exists.")

