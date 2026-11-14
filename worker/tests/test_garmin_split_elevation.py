from types import SimpleNamespace

import pytest
from test_coaching_context_builder import RepositoryStub

from app.services.coaching.context_builder import CoachingContextBuilder
from app.services.coaching.evidence import lap_evidence


@pytest.mark.parametrize("has_stream", [False, True])
def test_coaching_uses_provider_totals_independently_of_altitude_coverage(has_stream):
    repo = RepositoryStub()
    recorded = repo.get_splits(10)
    recorded.laps[0].update(elevation_gain_meters=12.5, elevation_loss_meters=0)
    recorded.laps[1].update(elevation_gain_meters=0, elevation_loss_meters=None)
    repo.get_splits = lambda _: recorded
    if not has_stream:
        repo.get_stream = lambda _: None
    result = CoachingContextBuilder(repo).build_activity_context(
        user_id=1, activity_id=10
    )
    terrain = result["splits"][0]["terrain"]
    assert terrain["ascent_m"] == 12.5
    assert terrain["descent_m"] == 0
    assert terrain["elevation_totals_source"] == "garmin"
    assert bool(terrain["coverage_fraction"]) == has_stream
    assert result["splits"][1]["terrain"]["ascent_m"] == 0
    assert result["splits"][1]["terrain"]["descent_m"] is None


def test_lap_totals_never_silently_fall_back_to_stream_calculations():
    stream = SimpleNamespace(
        distance_stream={"data": list(range(0, 1001, 100))},
        altitude_stream={
            "data": [100, 110, 120, 130, 140, 150, 145, 140, 135, 130, 125]
        },
    )
    laps = [{"number": 1, "distance_meters": 1000}]
    terrain, _ = lap_evidence(laps, stream, None, "Run")
    assert terrain[0]["ascent_m"] is None
    assert terrain[0]["descent_m"] is None
