import dash
import dash_bootstrap_components as dbc
from dash import Output, Input, State, no_update
from dash_extensions.enrich import DashProxy
from flask import session

from connections.update_data_mongo import update_user_record
from dash_apps.run_together.pages.settings_and_profile.settings_profile_helper_method import (
    which_race_button,
    which_race_distance,
)
from dash_apps.run_together.utils.conversion import (
    marathon_pace,
    calculate_speed_max,
)


def settings_profile_cb(dash_app: DashProxy):
    @dash_app.callback(
        Output("display-div", "children"),
        Input("url", "pathname"),
    )
    def toggle_form(url_path):
        user_values = session.get("run_together_user", {})
        if url_path == "/settings":
            display = dbc.Stack(
                [
                    dbc.Label(f"Name: {user_values['name']}"),
                    dbc.Label(f"Email: {user_values['email']}"),
                    dbc.Label(f"Birthday: {user_values['birthday']}"),
                ],
                gap=2,
                direction="horizontal",
            )
            return display
        return no_update

    @dash_app.callback(
        Output("max-bpm", "children"),
        Output("calculated-pace", "children"),
        Output("speed-max", "children"),
        Input("url", "pathname"),
    )
    def calculate_max_bpm(url: str):
        if url == "/settings":
            max_bpm = session["run_together_user"]["max_bpm"]
            pace = session["run_together_user"].get("pace", 0)
            speed_max = session["run_together_user"].get("speed_max", 0)
            race_distance = session["run_together_user"].get("race_distance", 0)
            target_time = session["run_together_user"].get(
                "target_time", {"hours": 0, "minutes": 0, "seconds": 0}
            )

            if (
                pace == 0
                or speed_max == 0
                or race_distance == 0
                or target_time == {"hours": 0, "minutes": 0, "seconds": 0}
            ):
                return (
                    "",
                    "Please fill in your target time and click the race you plan to run",
                    "",
                )
            else:
                pace_min, pace_sec = marathon_pace(
                    target_time["hours"],
                    target_time["minutes"],
                    target_time["seconds"],
                    race_distance,
                )

                return (
                    max_bpm,
                    f"{pace_min} min {pace_sec} sec for {race_distance} km",
                    f"{speed_max}",
                )
        else:
            return no_update, no_update, no_update

    @dash_app.callback(
        Output("calculated-pace", "children"),
        Output("speed-max", "children"),
        Output("max-bpm", "children"),
        Input("ten-k-button", "n_clicks"),
        Input("semi-button", "n_clicks"),
        Input("full-button", "n_clicks"),
        State("seconds-dropdown", "value"),
        State("minutes-dropdown", "value"),
        State("hours-dropdown", "value"),
        prevent_initial_call=True,
    )
    def calculate_pace_and_save(
        distance_ten, distance_semi, distance_full, seconds, minutes, hours
    ):
        ctx = dash.callback_context

        if not ctx.triggered:
            return no_update, no_update, no_update

        button_id = ctx.triggered[0]["prop_id"].split(".")[0]
        distance, coefficient = which_race_button(button_id)

        if hours is None or minutes is None or seconds is None:
            return "Please fill in all the dropdowns", no_update, no_update
        else:
            min, sec = marathon_pace(hours, minutes, seconds, distance)
            pace = min + (sec / 60)

            speed_max = calculate_speed_max((min + (sec / 60)), coefficient)
            race_distance = which_race_distance(button_id)

            update_user_record(
                session,
                {
                    "speed_max": speed_max,
                    "pace": pace,
                    "race_distance": distance,
                    "target_time": {
                        "hours": hours,
                        "minutes": minutes,
                        "seconds": seconds,
                    },
                },
            )
            max_bpm = session["run_together_user"]["max_bpm"]
            session["run_together_user"]["target_time"] = {
                "hours": hours,
                "minutes": minutes,
                "seconds": seconds,
            }
            session["run_together_user"]["speed_max"] = speed_max
            session["run_together_user"]["pace"] = pace
            session["run_together_user"]["race_distance"] = distance
            session["run_together_user"]["race"] = race_distance
            session.modified = True

            return (
                f"{min} min {sec} sec for {race_distance} km",
                f"{speed_max}",
                max_bpm,
            )
