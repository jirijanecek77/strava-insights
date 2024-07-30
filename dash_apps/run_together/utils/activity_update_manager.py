import logging

import dash
import plotly.graph_objects as go
from typing import List, Tuple
from statistics import mean

from dash_apps.run_together.utils.conversion import normalize_value
from dash_apps.run_together.utils.conversion import calculate_pace
from dash_apps.run_together.utils.conversion import convert_min_to_min_sec
from dash_apps.run_together.utils.conversion import convert_min_sec_to_min

from dash_apps.run_together.utils.interval import extract_intervals
from dash_apps.run_together.utils.interval import get_kpi_interval


def add_interval_figure(
    figure: go.Figure,
    intervals: List[dict]
):
    for interval in intervals:

        # if interval['reason'] == 'Kept':
        figure['layout']['shapes'].append(
            dict(
                id='interval',
                type="rect",
                x0=min(interval['distance_km']),
                y0=0,
                x1=max(interval['distance_km']),
                y1=7,
                line_width=0,
                layer="below",
                fillcolor="LightGrey",
                opacity=0.40,
            )
        )

        distance = round(max(interval['distance_km']) - min(interval['distance_km']), 2)
        pace = convert_min_to_min_sec(mean(interval['pace']))

        figure['layout']['annotations'].append(
            dict(
                x=(min(interval['distance_km']) + max(interval['distance_km'])) / 2,
                # Place the annotation in the middle of the interval
                y=7,  # Adjust the y position as needed
                text=f"<b>Distance:</b> {distance} km<br>"
                     f"<b>Pace:</b> {pace} min/km",
                showarrow=False,
                font=dict(size=15),
                xanchor="center",
                yanchor="bottom"
            )
        )
    return figure


def reset_annotation_and_shapes(
    figure: go.Figure,
):
    # If not annotation we need to initiate it
    figure['layout']['annotations'] = []

    # Drop all te previous shapes build if user click multiple times on analyze
    figure['layout']['shapes'] = [
        shape for shape in figure['layout']['shapes']
        if shape.get('id') != 'interval'
    ]
    return figure


def update_graph_display_all(
    figure: go.Figure,
    extended_stream: dict,
    kpi_bpm_pace_distance_activity: Tuple
):
    figure = reset_annotation_and_shapes(figure=figure)

    return figure, \
        dash.no_update, \
        kpi_bpm_pace_distance_activity[0], \
        kpi_bpm_pace_distance_activity[1], \
        kpi_bpm_pace_distance_activity[2], \
        False, \
        False, \
        True


def update_graph_display_jogging(
    figure: go.Figure,
):
    figure = reset_annotation_and_shapes(figure=figure)

    distance_km = figure['data'][0]['x']

    # Get the Custom Data to get the non normalize data
    moving_average_pace_minute_second_per_km = figure['data'][0]['customdata']
    moving_average_pace_minute_per_km = [
        convert_min_sec_to_min(x) for x in moving_average_pace_minute_second_per_km
    ]
    intervals = extract_intervals(
        distance_km=distance_km,
        pace=moving_average_pace_minute_per_km,
        heart_rate=figure['data'][1]['customdata'],
        # TODO change the lower bound according to the data
        lower_bound=4.25,
        upper_bound=float('inf')
    )

    average_heart_rate, average_pace, total_distance = get_kpi_interval(
        intervals=intervals
    )

    figure = add_interval_figure(
        figure=figure,
        intervals=intervals
    )
    return figure, \
        dash.no_update, \
        round(average_heart_rate, 1), \
        convert_min_to_min_sec(average_pace), \
        round(total_distance, 2), \
        False, \
        True, \
        False


def update_graph_display_interval(
    figure: go.Figure,
):
    figure = reset_annotation_and_shapes(figure=figure)

    distance_km = figure['data'][0]['x']
    moving_average_pace_minute_second_per_km = figure['data'][0]['customdata']
    moving_average_pace_minute_per_km = [
        convert_min_sec_to_min(x) for x in moving_average_pace_minute_second_per_km
    ]

    intervals = extract_intervals(
        distance_km=distance_km,
        pace=moving_average_pace_minute_per_km,
        heart_rate=figure['data'][1]['customdata'],
        # TODO change the lower bound according to the data
        lower_bound=0,
        upper_bound=4.25
    )

    average_heart_rate, average_pace, total_distance = get_kpi_interval(
        intervals=intervals
    )

    figure = add_interval_figure(
        figure=figure,
        intervals=intervals
    )

    return figure, \
        dash.no_update, \
        round(average_heart_rate, 1), \
        convert_min_to_min_sec(average_pace), \
        round(total_distance, 2), \
        True, \
        False, \
        False



def update_graph_moving_average_pace(
    range_slider_pace: int,
    extended_stream: dict,
    pace_bpm_mapping: dict,
    kpi_bpm_pace_distance_activity: Tuple,
    figure: go.Figure,
):
    figure = reset_annotation_and_shapes(figure=figure)

    # Get the new pace with the new range slider input
    moving_average_pace = {
        'minute_per_km': calculate_pace(
            seconds=extended_stream['time']['data'][0:],
            distances=extended_stream['distance']['data'][0:],
            range_points=range_slider_pace,
        )
    }

    moving_average_pace['minute_second_per_km'] = [
        convert_min_to_min_sec(x)
        for x in moving_average_pace['minute_per_km']
    ]

    # Normalize it based on the user information
    normalized_moving_average_pace = [
        normalize_value(
            value=x,
            original_range=[x['pace'] for x in pace_bpm_mapping.values()],
            target_range=list(range(len(pace_bpm_mapping.values())))
        )
        for x in moving_average_pace['minute_per_km']
    ]

    # Update the graph
    figure['data'][0]['x'] = extended_stream["distance_km"]
    figure['data'][0]['y'] = normalized_moving_average_pace
    figure['data'][0]['customdata'] = moving_average_pace['minute_second_per_km']

    return figure, moving_average_pace, \
        kpi_bpm_pace_distance_activity[0], \
        kpi_bpm_pace_distance_activity[1], \
        kpi_bpm_pace_distance_activity[2], \
        False, \
        False, \
        True

