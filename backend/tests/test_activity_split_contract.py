import pytest
from pydantic import ValidationError

from app.domain.schemas.activity import ActivitySplit, ActivitySplitsResponse


def split(**kwargs):
    return {
        "number": 1,
        "distance_meters": 1000,
        "start_distance_meters": 0,
        "end_distance_meters": 1000,
        **kwargs,
    }


def test_detail_contract_preserves_garmin_elevation_and_old_laps():
    response = ActivitySplitsResponse(
        status="ready",
        laps=[
            split(elevation_gain_meters=12.5, elevation_loss_meters=0),
            split(),
        ],
    ).model_dump()
    assert response["laps"][0]["elevation_gain_meters"] == 12.5
    assert response["laps"][0]["elevation_loss_meters"] == 0
    assert response["laps"][1]["elevation_gain_meters"] is None
    assert response["laps"][1]["elevation_loss_meters"] is None


@pytest.mark.parametrize("value", [-1, float("inf"), float("nan")])
def test_detail_contract_rejects_invalid_elevation(value):
    with pytest.raises(ValidationError):
        ActivitySplit.model_validate(split(elevation_gain_meters=value))
