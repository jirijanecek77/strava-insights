from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from app.application.auth.current_user import CurrentUserService
from app.domain.schemas.user import CurrentUserResponse
from app.infrastructure.db.models.activity import Activity
from app.infrastructure.db.models.activity_stream import ActivityStream
from app.infrastructure.db.models.best_effort import BestEffort
from app.infrastructure.db.models.period_summary import PeriodSummary
from app.infrastructure.db.models.user_threshold_profile import UserThresholdProfile
from app.main import app


class CurrentUserServiceStub:
    def __init__(self, user_id: int) -> None:
        self.user = CurrentUserResponse(
            id=user_id,
            external_user_id="162181",
            source_provider="garmin",
            display_name="Integration Athlete",
            profile_picture_url=None,
        )

    def get_current_user(self, _request):
        return self.user


def test_read_endpoints_with_mocked_repositories(client, monkeypatch) -> None:
    today = date.today()
    current_month = today.replace(day=1)
    previous_month = (current_month - timedelta(days=1)).replace(day=1)
    current_year = today.replace(month=1, day=1)
    previous_year = current_year.replace(year=current_year.year - 1)
    current_week = today - timedelta(days=today.weekday())
    previous_week = current_week - timedelta(days=7)

    profile = UserThresholdProfile(
        user_id=1,
        effective_from=date(1900, 1, 1),
        aet_heart_rate_bpm=145,
        ant_heart_rate_bpm=165,
        aet_pace_min_per_km=Decimal("5.20"),
        ant_pace_min_per_km=Decimal("4.30"),
    )
    activity = Activity(
        id=5,
        user_id=1,
        source_activity_id=1005,
        source_provider="garmin",
        name="Morning Run",
        description="steady effort",
        sport_type="Run",
        start_date_utc=datetime.now(UTC) - timedelta(days=2),
        start_date_local=datetime.now(UTC) - timedelta(days=2),
        distance_meters=Decimal("10000"),
        distance_km=Decimal("10.00"),
        moving_time_seconds=2700,
        moving_time_display="45:00",
        elapsed_time_seconds=2800,
        total_elevation_gain_meters=Decimal("100.00"),
        average_speed_mps=Decimal("3.7000"),
        average_speed_kph=Decimal("13.32"),
        max_speed_mps=Decimal("4.5000"),
        average_heartrate_bpm=Decimal("150.00"),
        average_cadence=Decimal("84.00"),
        average_pace_seconds_per_km=Decimal("270.00"),
        average_pace_display="4:30",
        summary_metric_display="4:30 /km",
    )
    faster_route_activity = Activity(
        id=6,
        user_id=1,
        source_activity_id=1006,
        source_provider="garmin",
        name="Earlier River Run",
        sport_type="Run",
        start_date_utc=datetime.now(UTC) - timedelta(days=3),
        start_date_local=datetime.now(UTC) - timedelta(days=3),
        distance_meters=Decimal("10000"),
        distance_km=Decimal("10.00"),
        moving_time_seconds=2600,
        moving_time_display="43:20",
        average_speed_mps=Decimal("3.8462"),
        average_speed_kph=Decimal("13.85"),
        average_pace_seconds_per_km=Decimal("260.00"),
        average_pace_display="4:20",
        summary_metric_display="4:20 /km",
        average_heartrate_bpm=Decimal("148.00"),
    )
    stream = ActivityStream(
        activity_id=5,
        time_stream={"data": [0, 60, 120, 180, 240, 300]},
        distance_stream={"data": [0, 250, 500, 750, 1000, 1250]},
        latlng_stream={"data": [[50.0, 14.0], [50.1, 14.1]]},
        altitude_stream={"data": [200, 201, 202, 203, 204, 205]},
        velocity_smooth_stream={"data": [4.0, 4.1, 4.2, 4.3, 4.4, 4.5]},
        heartrate_stream={"data": [150, 151, 152, 153, 154, 155]},
    )
    best_effort = BestEffort(
        user_id=1,
        sport_type="Run",
        effort_code="5km",
        best_time_seconds=1400,
        distance_meters=Decimal("5000"),
        activity_id=5,
        achieved_at=activity.start_date_utc,
    )
    faster_best_effort = BestEffort(
        user_id=1,
        sport_type="Run",
        effort_code="5km",
        best_time_seconds=1300,
        distance_meters=Decimal("5000"),
        activity_id=6,
        achieved_at=faster_route_activity.start_date_utc,
    )
    period_summaries = [
        PeriodSummary(
            user_id=1,
            sport_type="Run",
            period_type="month",
            period_start=current_month,
            activity_count=3,
            total_distance_meters=Decimal("30000"),
            total_moving_time_seconds=7200,
            average_speed_mps=None,
            average_pace_seconds_per_km=Decimal("240.00"),
            total_elevation_gain_meters=Decimal("300.00"),
        ),
        PeriodSummary(
            user_id=1,
            sport_type="Run",
            period_type="month",
            period_start=previous_month,
            activity_count=2,
            total_distance_meters=Decimal("20000"),
            total_moving_time_seconds=5400,
            average_speed_mps=None,
            average_pace_seconds_per_km=Decimal("270.00"),
            total_elevation_gain_meters=Decimal("200.00"),
        ),
        PeriodSummary(
            user_id=1,
            sport_type="Run",
            period_type="year",
            period_start=current_year,
            activity_count=8,
            total_distance_meters=Decimal("80000"),
            total_moving_time_seconds=21000,
            average_speed_mps=None,
            average_pace_seconds_per_km=Decimal("262.50"),
            total_elevation_gain_meters=Decimal("800.00"),
        ),
        PeriodSummary(
            user_id=1,
            sport_type="Run",
            period_type="year",
            period_start=previous_year,
            activity_count=6,
            total_distance_meters=Decimal("60000"),
            total_moving_time_seconds=17000,
            average_speed_mps=None,
            average_pace_seconds_per_km=Decimal("283.33"),
            total_elevation_gain_meters=Decimal("600.00"),
        ),
        PeriodSummary(
            user_id=1,
            sport_type="Run",
            period_type="week",
            period_start=current_week,
            activity_count=2,
            total_distance_meters=Decimal("20000"),
            total_moving_time_seconds=5200,
            average_speed_mps=None,
            average_pace_seconds_per_km=Decimal("260.00"),
            total_elevation_gain_meters=Decimal("180.00"),
        ),
        PeriodSummary(
            user_id=1,
            sport_type="Run",
            period_type="week",
            period_start=previous_week,
            activity_count=1,
            total_distance_meters=Decimal("10000"),
            total_moving_time_seconds=2800,
            average_speed_mps=None,
            average_pace_seconds_per_km=Decimal("280.00"),
            total_elevation_gain_meters=Decimal("90.00"),
        ),
    ]

    from types import SimpleNamespace
    from unittest.mock import Mock

    from app.application.read_models import best_efforts, dashboard
    from tests.read_mocks import mock_activity_repositories

    repositories = mock_activity_repositories(
        monkeypatch, [activity, faster_route_activity]
    )
    repositories.streams.get_for_activity.return_value = stream
    repositories.user_profiles.get_effective_for_user.return_value = profile
    repositories.best_efforts.list_for_user.return_value = [
        faster_best_effort,
        best_effort,
    ]
    repositories.activities.get_route_attempt_group.return_value = SimpleNamespace(
        id=42,
        sport_type="Run",
        nominal_distance_meters=Decimal("10000"),
        activities=[faster_route_activity, activity],
    )
    monkeypatch.setattr(
        best_efforts,
        "BestEffortRepository",
        Mock(return_value=repositories.best_efforts),
    )
    summaries = Mock(spec=dashboard.PeriodSummaryRepository)
    summaries.get_for_period.side_effect = (
        lambda user_id, *, period_type, period_start, sport_type: [
            row
            for row in period_summaries
            if row.period_type == period_type and row.period_start == period_start
        ]
    )
    summaries.list_for_user.side_effect = lambda user_id, *, period_type, sport_type: [
        row for row in period_summaries if row.period_type == period_type
    ]
    monkeypatch.setattr(
        dashboard, "PeriodSummaryRepository", Mock(return_value=summaries)
    )

    app.dependency_overrides[CurrentUserService] = lambda: CurrentUserServiceStub(1)
    try:
        dashboard_response = client.get("/dashboard")
        assert dashboard_response.status_code == 200
        assert dashboard_response.json()["month"][0]["current"]["activity_count"] == 3

        trends_response = client.get("/trends?period_type=week")
        assert trends_response.status_code == 200
        assert len(trends_response.json()["items"]) == 2

        rolling_response = client.get("/comparisons?period_type=rolling_30d")
        assert rolling_response.status_code == 200
        assert rolling_response.json()[0]["current"]["period_type"] == "rolling_30d"

        activities_response = client.get("/activities")
        assert activities_response.status_code == 200
        assert activities_response.json()["items"][0]["name"] == "Morning Run"
        assert (
            activities_response.json()["items"][0]["summary_metric_display"] == "4:30"
        )
        assert activities_response.json()["items"][0]["summary_metric_kind"] == "pace"
        first_activity = activities_response.json()["items"][0]
        assert first_activity["moving_time_seconds"] == 2700
        assert first_activity["average_pace_seconds_per_km"] == "270.00"
        assert first_activity["average_speed_kph"] == "13.32"
        assert first_activity["aerobic_efficiency_m_per_beat"] == 1.48

        activity_detail_response = client.get("/activities/5")
        assert activity_detail_response.status_code == 200
        assert activity_detail_response.json()["map"]["bounds"]["max_lat"] == 50.1
        assert (
            activity_detail_response.json()["kpis"]["summary_metric_display"] == "4:30"
        )
        assert activity_detail_response.json()["kpis"]["summary_metric_kind"] == "pace"
        assert activity_detail_response.json()["series"]["pace_display"][0] == "4:00"
        assert activity_detail_response.json()["series"]["altitude_meters"][0] == 200
        assert (
            activity_detail_response.json()["thresholds"]["aet_heart_rate_bpm"] == 145.0
        )
        assert (
            activity_detail_response.json()["thresholds"]["ant_pace_min_per_km"] == 4.3
        )
        assert (
            activity_detail_response.json()["running_analysis"]["pace_distribution"][0][
                "label"
            ]
            == "Below AeT"
        )
        assert activity_detail_response.json()["cycling_analysis"] is None
        assert activity_detail_response.json()["kpis"]["max_pace_display"] == "3:42"
        assert activity_detail_response.json()["kpis"]["max_speed_kph"] is None
        assert activity_detail_response.json()["best_efforts"][0]["rank"] == 2
        assert (
            activity_detail_response.json()["route_comparison"]["route_name"]
            == "Same route \u00b7 Run \u00b7 10 km \u00b7 4:30/km"
        )
        assert activity_detail_response.json()["route_comparison"]["current_rank"] == 2
        assert activity_detail_response.json()["route_comparison"]["attempt_count"] == 2

        best_efforts_response = client.get("/best-efforts")
        assert best_efforts_response.status_code == 200
        assert best_efforts_response.json()["items"][0]["effort_code"] == "5km"
        assert best_efforts_response.json()["items"][0]["sport_type"] == "Run"
        assert [item["rank"] for item in best_efforts_response.json()["items"]] == [
            1,
            2,
        ]
    finally:
        app.dependency_overrides.clear()
