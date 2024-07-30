from dash import html
import plotly.graph_objects as go
from dash import dcc
import dash_mantine_components as dmc
from dash.html import Div
from dash_apps.run_together.utils.colors import Colors
from dash_apps.run_together.model.extended_activity import ExtendedActivity
from dash_apps.run_together.utils.conversion import convert_min_to_min_sec

import logging

def get_reference_race():
    """

    :return:
    """
    selection_reference_race = html.Div(
        [
            dmc.SegmentedControl(
                id="segmented",
                value="ng",
                data=[
                    {"value": "marathon", "label": "Marathon"},
                    {"value": "half_marathon", "label": "Half Marathon"},
                    {"value": "10km", "label": "10 km"},
                ],
                mb=10,
            ),
        ]
    )
    return selection_reference_race

#

def get_activity_graph(extended_activity: ExtendedActivity) -> Div:
    """
    Generate an Activity Pace graph.

    This function creates a heart rate graph based on the provided activity
    stream data,displaying heart rate values over distance.
    The graph is customized with specificstyling and hover interactions.

    :param activity_stream: Dictionary containing activity stream data.
    :return: dcc.Graph component representing the heart rate graph.
    """

    # Get some parameter to display the zone on the graph
    pace_bpm_mapping = extended_activity.user.get_pace_bpm_mapping()

    colors = [x['color'] for x in pace_bpm_mapping.values()]
    y_bpm_axis = [x['bpm'] for x in pace_bpm_mapping.values()]

    zone = list(range(len(pace_bpm_mapping)))

    fig = go.Figure()

    # Add heart rate data as a scatter plot
    fig.add_trace(
        go.Scatter(
            x=extended_activity.extended_stream["distance_km"],
            y=extended_activity.normalized_moving_average_pace,
            name="Pace min/km",
            mode="lines",
            line=dict(
                color=Colors.green,
                width=2
            ),
            hovertemplate="Pace: %{customdata} min/km<extra></extra>",  # Hover tooltip template with y / 60
            customdata=extended_activity.moving_average_pace['minute_second_per_km']
        ),
    )

    fig.add_trace(
        go.Scatter(
            x=extended_activity.extended_stream["distance_km"],
            y=extended_activity.normalized_moving_average_heartrate,
            name="Heart Rate (bpm)",
            mode="lines",
            line=dict(
                color=Colors.orange,
                width=2
            ),
            hovertemplate="BPM: %{customdata}<extra></extra>",  # Hover tooltip template with y / 60
            customdata=[int(x) for x in extended_activity.moving_average_heartrate],
            yaxis="y2"  # Assign this trace to the secondary y-axis
        )
    )

    # Add background color and labels for each pace zone
    shapes = []

    for i in range(len(pace_bpm_mapping)):

        # if i  < len(pace_bpm_mapping):
        shapes.append(
            dict(
                type="rect",
                xref="paper",
                yref="y",
                x0=0,
                y0=i-0.5,
                x1=1,
                y1=i+1-0.5,
                fillcolor=colors[i],
                opacity=0.8,
                layer="below",
                line_width=0,
            )
        )

    # Update layout
    fig.update_layout(
        # title="<b> Pace & Heart rate <b>",
        xaxis=dict(
            title='<b>Distance</b> (km)',
        ),
        yaxis=dict(
            title='<b>Pace</b> (min/km)',
            showgrid=False,  # Optional: Hide grid lines for secondary y-axis
            tickvals=zone,
            ticktext=[
                f"<b>{key}</b><br><i>{convert_min_to_min_sec(value['pace'])}</i>" for key, value in pace_bpm_mapping.items()
            ],
            range=[max(zone), min(zone)],

        ),
        yaxis2=dict(
            title='<b>Heart Rate</b> (bpm)',
            overlaying='y',
            side='right',
            showgrid=False,  # Optional: Hide grid lines for secondary y-axis
            tickvals=zone,
            ticktext=[int(x) for x in y_bpm_axis],
            range=[max(zone), min(zone)],
        ),
        hovermode="x unified",
        height=500,
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(
            orientation="h",
            yanchor="top",
        ),
        shapes=shapes,  # Add shapes to the layout
        margin=dict(
            t=30,
            r=5,
            l=5,
            b=5,
            pad=15,# padding y-axis and the graph
            # autoexpand=False
        )
    )

    activity_graph = dcc.Graph(
        figure=fig,
        style={"width": "100%"},
        config={
            "displayLogo": False,
            "displayModeBar": False,
        },  # Disable display of logo and mode bar
        id="activity-graph",  # Set component ID
        className="activity-graph-container",
        responsive=True
    )

    return html.Div(children=activity_graph)
