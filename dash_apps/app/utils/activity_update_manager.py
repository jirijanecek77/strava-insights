from statistics import mean
from typing import List

import plotly.graph_objects as go

from dash_apps.app.utils.conversion import convert_min_to_min_sec


def add_interval_figure(figure: go.Figure, intervals: List[dict]):
    for interval in intervals:
        # if interval['reason'] == 'Kept':
        figure["layout"]["shapes"].append(
            dict(
                id="interval",
                type="rect",
                x0=min(interval["distance_km"]),
                y0=0,
                x1=max(interval["distance_km"]),
                y1=7,
                line_width=0,
                layer="below",
                fillcolor="LightGrey",
                opacity=0.40,
            )
        )

        distance = round(max(interval["distance_km"]) - min(interval["distance_km"]), 2)
        pace = convert_min_to_min_sec(mean(interval["pace"]))

        figure["layout"]["annotations"].append(
            dict(
                x=(min(interval["distance_km"]) + max(interval["distance_km"])) / 2,
                # Place the annotation in the middle of the interval
                y=7,  # Adjust the y position as needed
                text=f"<b>Distance:</b> {distance} km<br>"
                f"<b>Pace:</b> {pace} min/km",
                showarrow=False,
                font=dict(size=15),
                xanchor="center",
                yanchor="bottom",
            )
        )
    return figure


def reset_annotation_and_shapes(
    figure: go.Figure,
):
    # If not annotation we need to initiate it
    figure["layout"]["annotations"] = []

    # Drop all te previous shapes build if user click multiple times on analyze
    figure["layout"]["shapes"] = [
        shape for shape in figure["layout"]["shapes"] if shape.get("id") != "interval"
    ]
    return figure
