from dash_apps.run_together.utils.interval import get_kpi_interval
from dash_apps.run_together.model.extended_activity import ExtendedActivity
import logging
from dash import html


def get_activity_analysis(extended_activity: ExtendedActivity):
    """""
    test = {
        'Marathon': {
            'average_heart_rate': 0,
            'average_pace': 0,
            'total_distance': 0,
            'intervals': [],
            'Marathon': {
                'average_heart_rate': 0,
                'average_pace': 0,
                'total_distance': 0,
                'intervals': [],

            },
            'Half-Marathon': {
                'average_heart_rate': 0,
                'average_pace': 0,
                'total_distance': 0,
                'intervals': [],

            }
        }
    }
    """""
    intervals_moving_average_pace_zone = extended_activity.intervals_moving_average_pace_zone

    zone_pace_heart_rate_kpi = {}

    # Reformat the dictionary to have for each zone the list of interval.
    for interval_moving_average_pace_zone in intervals_moving_average_pace_zone:

        # Set-up the main dictionary for the pace
        zone_pace = interval_moving_average_pace_zone['zones']['zone_pace']
        zone_heart_rate = interval_moving_average_pace_zone['zones']['zone_heart_rate']

        # Set-up if first time the zone pace has not be found yet
        if zone_pace not in list(zone_pace_heart_rate_kpi.keys()):
            zone_pace_heart_rate_kpi[zone_pace] = {}
            zone_pace_heart_rate_kpi[zone_pace]['intervals'] = []

        # Adding the zone pace hart rate
        zone_pace_heart_rate_kpi[zone_pace]['intervals'].append(
            interval_moving_average_pace_zone
        )

        # Set-up if first time the zone pace heart-rate has be found
        if zone_heart_rate not in list(zone_pace_heart_rate_kpi[zone_pace].keys()):
            zone_pace_heart_rate_kpi[zone_pace][zone_heart_rate] = {}
            zone_pace_heart_rate_kpi[zone_pace][zone_heart_rate]['intervals'] = []

        # Adding the zone heart Rate
        zone_pace_heart_rate_kpi[zone_pace][zone_heart_rate]['intervals'].append(
            interval_moving_average_pace_zone
        )

    # Get the KPI for each
    for zone_pace in zone_pace_heart_rate_kpi.keys():
        kpi_interval_tmp_pace = get_kpi_interval(
            intervals=zone_pace_heart_rate_kpi[zone_pace]['intervals']
        )

        # Delete Intervals keys
        zone_pace_heart_rate_kpi[zone_pace].pop('intervals', None)

        zone_pace_heart_rate_kpi[zone_pace]['average_pace'] = kpi_interval_tmp_pace[0]
        zone_pace_heart_rate_kpi[zone_pace]['average_heart_rate'] = kpi_interval_tmp_pace[1]
        zone_pace_heart_rate_kpi[zone_pace]['total_distance'] = kpi_interval_tmp_pace[2]

        for zone_heart_rate in zone_pace_heart_rate_kpi[zone_pace].keys():
            if zone_heart_rate not in ('average_heart_rate', 'average_pace', 'total_distance', 'intervals'):
                kpi_interval_heart_rate = get_kpi_interval(
                    intervals=zone_pace_heart_rate_kpi[zone_pace][zone_heart_rate]['intervals']
                )
                # Delete Intervals keys
                zone_pace_heart_rate_kpi[zone_pace][zone_heart_rate].pop('intervals', None)

                zone_pace_heart_rate_kpi[zone_pace][zone_heart_rate]['average_pace'] = kpi_interval_heart_rate[0]
                zone_pace_heart_rate_kpi[zone_pace][zone_heart_rate]['average_heart_rate'] = kpi_interval_heart_rate[1]
                zone_pace_heart_rate_kpi[zone_pace][zone_heart_rate]['total_distance'] = kpi_interval_heart_rate[2]

    # logging.info(zone_pace_heart_rate_kpi['Marathon'])
    to_display = 'Half-Marathon'
    total_distance_first = zone_pace_heart_rate_kpi['Half-Marathon']['total_distance']
    total_distance_second = zone_pace_heart_rate_kpi['10km']['total_distance']

    analysis = f"🦶 {round(extended_activity.activity['distance'] / 1000, 2)} km: " \
               f"{round(total_distance_first, 2)} km @ Half-Marathon Pace | " \
               f"{round(total_distance_second, 2)} km @ 10km Pace |" \
               f"| www.run-together.com"

    return html.Div(
        children=analysis,
        className="h3",
        style={"text-align": "left"}
    )