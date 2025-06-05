import dash_leaflet as dl

from dash_apps.run_together.model.extended_activity import ExtendedActivity


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

    # https://leaflet-extras.github.io/leaflet-providers/preview/
    url = "https://tiles.stadiamaps.com/tiles/outdoors/{z}/{x}/{y}{r}.png"

    activity_map = dl.Map(
        id={"type": "activity-map", "index": extended_activity.activity_id},
        style={"height": "30vh"},
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
