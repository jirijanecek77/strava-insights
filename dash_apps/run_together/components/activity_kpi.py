from typing import List

from dash import html

from dash_apps.run_together.model.extended_activity import ExtendedActivity
from dash_apps.run_together.utils.conversion import convert_min_to_min_sec
from dash_apps.run_together.utils.conversion import speed_to_pace


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
                    html.I(className="fas fa-route"),
                    html.Div(
                        children=f"{round(extended_activity.activity['distance'] / 1000, 2)}"
                    ),
                    f"km",
                ],
                className="kpi-icons",
            ),
            html.Div(
                children=[
                    html.I(className="fas fa-clock"),
                    html.Div(
                        f"{convert_min_to_min_sec(extended_activity.activity['moving_time']/60)}"
                    ),
                    f"min",
                ],
                className="kpi-icons",
            ),
            html.Div(
                children=[
                    html.I(className="fas fa-tachometer-alt"),
                    html.Div(
                        f"{convert_min_to_min_sec(speed_to_pace(extended_activity.activity['average_speed']))}"
                    ),
                    f"min/km",
                ],
                className="kpi-icons",
            ),
            html.Div(
                children=[
                    html.I(className="fas fa-chart-line"),
                    html.Div(
                        children=f"{extended_activity.activity['total_elevation_gain']}"
                    ),
                    f"m",
                ],
                className="kpi-icons",
            ),
            html.Div(
                children=[
                    html.I(className="fas fa-heart"),
                    html.Div(
                        children=f"{extended_activity.activity['average_heartrate']}"
                    ),
                    f"bpm",
                ],
                className="kpi-icons",
            ),
        ],
        className="card_grid",
    )

    return kpi_icons
