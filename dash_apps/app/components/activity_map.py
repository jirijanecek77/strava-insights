import dash_leaflet as dl

from blueprints.login.login import mapy_cz_api_key
from dash_apps.app.model.extended_activity import ExtendedActivity


def get_activity_map(extended_activity: ExtendedActivity) -> dl.Map:
    """
        Return the Activity Map

    :return: dl.Map ot the activity
    """

    # Manage the size of the map
    min_latitude = min(
        [x[0] for x in extended_activity.extended_stream["latlng"]["data"]]
    )
    max_latitude = max(
        [x[0] for x in extended_activity.extended_stream["latlng"]["data"]]
    )
    min_longitude = min(
        [x[1] for x in extended_activity.extended_stream["latlng"]["data"]]
    )
    max_longitude = max(
        [x[1] for x in extended_activity.extended_stream["latlng"]["data"]]
    )

    bounds_points = [
        [min_latitude, min_longitude],  # South West
        [max_latitude, max_longitude],  # North East
    ]

    url = (
        "https://api.mapy.cz/v1/maptiles/outdoor/256/{z}/{x}/{y}?apikey="
        + mapy_cz_api_key
    )

    activity_map = dl.Map(
        id={"type": "activity-map", "index": extended_activity.activity_id},
        style={"height": "calc(100vh - 400px)"},
        bounds=bounds_points,
        children=[
            dl.TileLayer(
                url=url,
            ),
            dl.Polyline(
                positions=extended_activity.extended_stream["latlng"]["data"],
            ),
            dl.LayerGroup(id="marker-map", children=[]),
        ],
    )

    activity_map.viewport = dict(bounds=bounds_points, transition="flyToBounds")

    return activity_map
