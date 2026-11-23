from dataclasses import dataclass


@dataclass
class PlanningRunStats:
    generated: int = 0
    calls: int = 0
    failures: int = 0
    rate_limited: bool = False
    insufficient_data: int = 0
    skipped_reason: str | None = None
