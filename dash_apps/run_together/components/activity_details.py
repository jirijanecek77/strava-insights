from dash.html import Div
from dash import html, dcc
import dash_bootstrap_components as dbc
from dash_apps.run_together.components.activity_graph import get_activity_graph
from dash_apps.run_together.components.activity_kpi import get_activity_kpi
from dash_apps.run_together.components.activity_analysis import get_activity_analysis
from dash_apps.run_together.components.activity_map import get_activity_map

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

    # Get activity Graph component
    activity_graph = get_activity_graph(extended_activity=extended_activity)

    # Get activity KPI component
    activity_kpi = get_activity_kpi(extended_activity=extended_activity)

    # Get activity map component
    activity_map = get_activity_map(extended_activity=extended_activity)

    range_slider = html.Div(
        children=[
            dcc.Slider(
                id="range-slider-pace",
                min=10,
                max=80,
                step=1,
                value=extended_activity.range_points_pace,
                marks={10: "10", 50: "50", 90: "90"},
            ),
        ],
    )

    activity_analysis = get_activity_analysis(extended_activity=extended_activity)

    # Create the activity Details with two columns
    return html.Div(
        children=[
            dbc.Row(
                [
                    dbc.Col(
                        [
                            dbc.Row(
                                html.Div(extended_activity.activity["name"]),
                                className="h2",
                            ),
                            dbc.Row(
                                dbc.FormText(extended_activity.activity["description"])
                            ),
                            dbc.Row(activity_kpi),
                            dbc.Row(activity_map, className="mb-2"),
                        ],
                        width=3,
                    ),
                    dbc.Col(
                        [
                            dbc.Row(activity_graph),
                            dbc.Row(range_slider, className="mx-8"),
                        ]
                    ),
                ]
            ),
            dbc.Row(activity_analysis),
            dcc.Store(
                id="extended-stream", data=extended_activity.extended_stream
            ),  # store the activity stream for use in the callback
            dcc.Store(
                id="moving-average-stream", data=extended_activity.moving_average_pace
            ),  # store the activity stream for use in the callback
            dcc.Store(
                id="bpm-pace-mapping", data=extended_activity.user.pace_bpm_mapping
            ),  # store the pace bpm mapping for use in the callback
            dcc.Store(
                id="kpi-bpm-pace-distance-activity",
                data=(
                    extended_activity.activity["average_heartrate"],
                    convert_min_to_min_sec(
                        speed_to_pace(extended_activity.activity["average_speed"])
                    ),
                    round(extended_activity.activity["distance"] / 1e3, 2),
                ),
            ),  # store the pace bpm mapping for use in the callback
        ],
    )
