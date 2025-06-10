import logging

import dash_bootstrap_components as dbc
from dash import html

from dash_apps.app.model.extended_activity import ExtendedActivity
from dash_apps.app.utils.interval import get_kpi_interval


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
    """ ""
    intervals_moving_average_pace_zone = (
        extended_activity.intervals_moving_average_pace_zone
    )

    zone_pace_heart_rate_kpi = {}

    # Reformat the dictionary to have for each zone the list of interval.
    for interval_moving_average_pace_zone in intervals_moving_average_pace_zone:

        # Set-up the main dictionary for the pace
        zone_pace = interval_moving_average_pace_zone["zones"]["zone_pace"]
        zone_heart_rate = interval_moving_average_pace_zone["zones"]["zone_heart_rate"]

        # Set-up if first time the zone pace has not be found yet
        if zone_pace not in list(zone_pace_heart_rate_kpi.keys()):
            zone_pace_heart_rate_kpi[zone_pace] = {}
            zone_pace_heart_rate_kpi[zone_pace]["intervals"] = []

        # Adding the zone pace hart rate
        zone_pace_heart_rate_kpi[zone_pace]["intervals"].append(
            interval_moving_average_pace_zone
        )

        # Set-up if first time the zone pace heart-rate has be found
        if zone_heart_rate not in list(zone_pace_heart_rate_kpi[zone_pace].keys()):
            zone_pace_heart_rate_kpi[zone_pace][zone_heart_rate] = {}
            zone_pace_heart_rate_kpi[zone_pace][zone_heart_rate]["intervals"] = []

        # Adding the zone heart Rate
        zone_pace_heart_rate_kpi[zone_pace][zone_heart_rate]["intervals"].append(
            interval_moving_average_pace_zone
        )

    # Get the KPI for each
    for zone_pace in zone_pace_heart_rate_kpi.keys():
        kpi_interval_tmp_pace = get_kpi_interval(
            intervals=zone_pace_heart_rate_kpi[zone_pace]["intervals"]
        )

        # Delete Intervals keys
        zone_pace_heart_rate_kpi[zone_pace].pop("intervals", None)

        zone_pace_heart_rate_kpi[zone_pace]["average_pace"] = kpi_interval_tmp_pace[0]
        zone_pace_heart_rate_kpi[zone_pace]["average_heart_rate"] = (
            kpi_interval_tmp_pace[1]
        )
        zone_pace_heart_rate_kpi[zone_pace]["total_distance"] = kpi_interval_tmp_pace[2]
        logging.info(
            f"Zone {zone_pace} "
            f"average_pace {zone_pace_heart_rate_kpi[zone_pace]['average_pace']} "
            f"average_heart_rate {zone_pace_heart_rate_kpi[zone_pace]['average_heart_rate']} "
            f"total_distance {zone_pace_heart_rate_kpi[zone_pace]['total_distance']} "
        )

        for zone_heart_rate in zone_pace_heart_rate_kpi[zone_pace].keys():
            if zone_heart_rate not in (
                "average_heart_rate",
                "average_pace",
                "total_distance",
                "intervals",
            ):
                kpi_interval_heart_rate = get_kpi_interval(
                    intervals=zone_pace_heart_rate_kpi[zone_pace][zone_heart_rate][
                        "intervals"
                    ]
                )
                # Delete Intervals keys
                zone_pace_heart_rate_kpi[zone_pace][zone_heart_rate].pop(
                    "intervals", None
                )

                zone_pace_heart_rate_kpi[zone_pace][zone_heart_rate]["average_pace"] = (
                    kpi_interval_heart_rate[0]
                )
                zone_pace_heart_rate_kpi[zone_pace][zone_heart_rate][
                    "average_heart_rate"
                ] = kpi_interval_heart_rate[1]
                zone_pace_heart_rate_kpi[zone_pace][zone_heart_rate][
                    "total_distance"
                ] = kpi_interval_heart_rate[2]

    # Get the two most important interval and then take how much zone it wasbpm_pace_mapping = {
    zones_threshold = {
        "100m": {"threshold": 0.5, "priority": 1},
        "5km": {"threshold": 0.5, "priority": 1},
        "10km": {"threshold": 1, "priority": 1},
        "Half-Marathon": {"threshold": 2.1, "priority": 1},
        "Marathon": {"threshold": 4.2, "priority": 1},
        "Active Jogging": {"threshold": 0, "priority": 0},
        "Slow Jogging": {"threshold": 0, "priority": 0},
        "Walk": {"threshold": 0, "priority": 0},
    }

    zones_to_display = []

    i = 0
    # Loop per difficulties-priority eg: Marathon > Jogging
    for pace_zone, zone_threshold in zones_threshold.items():
        # In case there is not intervals at this pace
        if pace_zone in list(zone_pace_heart_rate_kpi.keys()):
            # Check there is already a priority one if yes we do not get anymore
            if zone_threshold["priority"] == 0 and len(zones_to_display) > 0:
                break

            if (
                zone_pace_heart_rate_kpi[pace_zone]["total_distance"]
                > zone_threshold["threshold"]
            ):
                zones_to_display.append(
                    {
                        "distance": zone_pace_heart_rate_kpi[pace_zone][
                            "total_distance"
                        ],
                        "pace_zone": pace_zone,
                    }
                )
                i = i + 1

                # I break to get only the first two highest value
                if i == 2:
                    break

    sorted_zones_to_display = sorted(
        zones_to_display, key=lambda d: d["distance"], reverse=True
    )

    analysis = f"🦶 {round(extended_activity.activity['distance'] / 1000, 2)} km: "
    for zone_to_display in sorted_zones_to_display:
        analysis = (
            analysis + f" | {round(zone_to_display['distance'], 2)}"
            f" km @ {zone_to_display['pace_zone']} Pace"
        )

    # Get the score for the most important interval calculated distance pace below / distance total
    # Loop per difficulties-priority eg: Marathon > Jogging
    longest_pace_zone = sorted_zones_to_display[0]
    logging.info(
        f"Longest Pace zone for the activity: {longest_pace_zone} "
        f"with {round(longest_pace_zone['distance'], 2)}km"
    )

    distance_heart_rate_in_range = 0
    for heart_rate_zone in list(zones_threshold.keys()):
        logging.info(heart_rate_zone)
        logging.info(zone_pace_heart_rate_kpi[longest_pace_zone["pace_zone"]])
        # In case there is not intervals at this heart Rate
        if heart_rate_zone in list(
            zone_pace_heart_rate_kpi[longest_pace_zone["pace_zone"]].keys()
        ):
            distance_heart_rate_in_range = (
                distance_heart_rate_in_range
                + zone_pace_heart_rate_kpi[longest_pace_zone["pace_zone"]][
                    heart_rate_zone
                ]["total_distance"]
            )
            # logging.info(
            #     zone_pace_heart_rate_kpi[
            #         longest_pace_zone['pace_zone']
            #     ][heart_rate_zone]['total_distance']
            # )

        # If we arrive at the pace_zone we stop
        if heart_rate_zone == longest_pace_zone["pace_zone"]:
            break

    score = distance_heart_rate_in_range / sorted_zones_to_display[0]["distance"] * 100
    logging.info(distance_heart_rate_in_range)
    logging.info(sorted_zones_to_display[0]["distance"])
    logging.info(score)
    score_text = ""
    if score > 50:
        score_text = (
            f"🟢 Congrats, {round(score, 2)}% of the distance run in "
            f"{sorted_zones_to_display[0]['pace_zone']} Pace is equal or bellow the associated heart-rate. "
        )
    if score <= 50:
        score_text = (
            f"🔴 Be careful, {round(score, 2)}% of the distance run in "
            f"{sorted_zones_to_display[0]['pace_zone']} Pace is above the associated heart-rate. "
        )

    return html.Div(children=[dbc.Row(analysis), dbc.Row(score_text)])
