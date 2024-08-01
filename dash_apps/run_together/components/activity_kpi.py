from dash import html
from typing import List

from dash_apps.run_together.utils.conversion import speed_to_pace
from dash_apps.run_together.utils.conversion import convert_min_to_min_sec

from dash_apps.run_together.model.extended_activity import ExtendedActivity


def get_activity_kpi(extended_activity: ExtendedActivity) -> List[html.Button]:
    """
        logic to generate the left column content goes from the body
        with the activities from the datafram as input

    :param activities_df:
    :return:
"""

    # Second row with three columns and icons
    kpi_icons = html.Div(
        children=[
            html.Div(
                children=[
                    html.I(className="fas fa-heart"),
                    html.Div(
                        children=f"{extended_activity.activity['average_heartrate']}",
                        id="bpm-kpi"
                    ),
                    f"bpm",
                ],
                className="kpi-icons",
            ),
            html.Div(
                children=[
                    html.I(className="fas fa-tachometer-alt"),
                    html.Div(
                        children=f"{convert_min_to_min_sec(speed_to_pace(extended_activity.activity['average_speed']))}",
                        id="pace-kpi"
                    ),
                    f"min/km",
                ],
                className="kpi-icons",
            ),
            html.Div(
                children=[
                    html.I(className="fas fa-route"),
                    html.Div(
                        children=f"{round(extended_activity.activity['distance'] / 1000, 2)}",
                        id="distance-kpi"
                    ),
                    f"km",
                ],
                className="kpi-icons",
            ),
        ],
        className="card_grid",
    )

    return kpi_icons
