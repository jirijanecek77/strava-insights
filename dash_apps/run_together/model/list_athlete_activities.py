from datetime import datetime, timedelta, date
from dash_apps.run_together.model.strava_manager import StravaManager
from dash_apps.run_together.model.user import User


def list_athlete_activities():
    """
    Method that fetches a list of the athletes 30 most recent activities
    """
    date_today = date.today()
    date_thirty_days_ago = date_today - timedelta(days=30)

    strava_client = StravaManager()
    activities_last_thirty_days = strava_client.get_activities_between(
        start_date=date_thirty_days_ago, end_date=date_today)

    return activities_last_thirty_days
