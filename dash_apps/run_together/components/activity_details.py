from dash.html import Div
from dash import html, dcc
from dash_apps.run_together.components.activity_graph import get_activity_graph
from dash_apps.run_together.components.activity_kpi import get_activity_kpi
from dash_apps.run_together.components.activity_analysis import get_activity_analysis

from dash_apps.run_together.utils.conversion import convert_min_to_min_sec
from dash_apps.run_together.utils.conversion import speed_to_pace

from dash_apps.run_together.model.extended_activity import ExtendedActivity


def get_activity_details(activity_id: int) -> Div:
    """
    Retrieve activity details.

    This function retrieves activity details for a given activity ID,
    including the activity stream, activity map, heart rate graph,
    and grid layout for displaying map and graph components.

    :param activity_id: ID of the activity.
    :return: List containing HTML components for activity details.
    """
    # Retrieve activity stream data
    extended_activity = ExtendedActivity(activity_id=activity_id)

    # # Get activity map component
    # activity_map = get_activity_map(
    #     activity_id=activity_id, activity_stream=activity_stream
    # )

    # Get activity Graph component
    activity_graph = get_activity_graph(
        extended_activity=extended_activity
    )

    # Get activity KPI component
    activity_kpi = get_activity_kpi(
        extended_activity=extended_activity
    )

    range_slider = html.Div(
        children=[
            dcc.Slider(
                id="range-slider-pace",
                min=10, max=80, step=1, value=extended_activity.range_points_pace,
                marks={
                    10: '10',
                    50: '50',
                    90: '90'
                },
            ),
        ],
        className="div-range-slider-pace"
    )

    # Create the column with the name KPI and button
    name_kpi_button_activity_details = html.Div(
        children=[
            html.Div(
                children=f"{extended_activity.activity['name']}",
                className="h2",
                style={"text-align": "left"},
            ),
            html.H4(
                children=f"{extended_activity.activity['description']}",
            ),
            html.Div(
                children=[
                    html.Button(
                        id='button-display-interval',
                        children=[
                            "Display Interval",
                        ],
                        className="button-select-intervals",
                        style={"font-weight": "500"}
                    ),
                    html.Button(
                        id='button-display-jogging',
                        children=[
                            "Display Jogging",
                        ],
                        className="button-select-intervals",
                        style={"font-weight": "500"}
                    ),
                    html.Button(
                        id='button-display-all',
                        children=[
                            "Display All Run",
                        ],
                        disabled=True,
                        className="button-select-intervals",
                        style={"font-weight": "500"}
                    ),
                ],
                className="grid_button",
            ),
            activity_kpi,
            range_slider

        ]
    )

    # Create the activity Details with two columns
    activity_details = html.Div(
        children=[
            name_kpi_button_activity_details,
            activity_graph
        ],
        className="activity-details-container",
    )

    activity_analysis = get_activity_analysis(
        extended_activity=extended_activity
    )

    # Create layout for displaying Activity Details + Analysis
    activity_details = html.Div(
        children=[
            activity_details,
            html.Div(
                children=[
                    activity_analysis,
                    html.Button(
                        id='button-update-description-strava',
                        children=[
                            html.I(className="fas fa-running", style={"padding-right": "8px"}),
                            "Update Description on Strava",
                        ],
                        disabled=False,
                        className="Button_login",
                        style={"font-weight": "500"}
                    ),
                ],
                className="analysis-details-container"
            ),
            dcc.Store(
                id="extended-stream",
                data=extended_activity.extended_stream
            ), # store the activity stream in a dash component to be used in the callback
            dcc.Store(
                id="moving-average-stream",
                data=extended_activity.moving_average_pace
            ),  # store the activity stream in a dash component to be used in the callback
            dcc.Store(
                id="bpm-pace-mapping",
                data=extended_activity.user.pace_bpm_mapping
            ),  # store the pace bpm mapping of the user to be used in the callback
            dcc.Store(
                id="kpi-bpm-pace-distance-activity",
                data=(
                    extended_activity.activity['average_heartrate'],
                    convert_min_to_min_sec(speed_to_pace(extended_activity.activity['average_speed'])),
                    round(extended_activity.activity['distance'] / 1e3, 2)
                )
            ),  # store the pace bpm mapping of the user to be used in the callback
        ],
    )

    return activity_details
