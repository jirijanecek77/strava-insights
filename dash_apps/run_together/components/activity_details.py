from dash.html import Div
from dash import html, dcc
# from dash_apps.run_together.components.activity_map import get_activity_map
from dash_apps.run_together.components.activity_graph import get_activity_graph
from dash_apps.run_together.model.extended_activity import ExtendedActivity
import pickle


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

    with open('extended_activity.pickle', 'wb') as handle:
        pickle.dump(extended_activity.extended_stream, handle, protocol=pickle.HIGHEST_PROTOCOL)
    with open('pace_bpm_mapping.pickle', 'wb') as handle:
        pickle.dump(extended_activity.user.pace_bpm_mapping, handle, protocol=pickle.HIGHEST_PROTOCOL)

    # Create grid layout for displaying map and graph components
    activity_details = html.Div(
        className="activity-details-container",
        children=[
            html.H2(
                children=f"Analyse your Activity",
                style={"font-size": "24px", "font-weight": "bold"},
            ),
            html.H3(
                children=f"{extended_activity.activity['name']}",
                # style={"font-size": "24px", "font-weight": "bold", "padding": "20px"},
            ),
            html.H4(
                children=f"{extended_activity.activity['description']}",
                # style={"font-size": "24px", "font-weight": "bold", "padding": "20px"},
            ),
            activity_graph,
            html.Div(
                html.Button(
                    id='button-analyze-activity-details',
                    children=[
                        html.I(className="fas fa-project-diagram", style={"padding-right": "8px"}),
                        "Analyze",
                    ],
                    className="Button_login",
                    style={"font-weight": "500"}
                ),
                style={"display": "flex", "justify-content": "flex-end"}
            ),
            dcc.Store(
                id="extended-stream",
                data=extended_activity.extended_stream
            ),# store the activity stream in a dash component to be used in the callback
            dcc.Store(
                id="moving-average-stream",
                data=extended_activity.moving_average_pace
            ),  # store the activity stream in a dash component to be used in the callback
            dcc.Store(
                id="bpm-pace-mapping",
                data=extended_activity.user.pace_bpm_mapping
            ),  # store the pace bpm mapping of the user to be used in the callback

        ],
    )

    return activity_details
