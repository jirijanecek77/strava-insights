from dash import Output, Input, State, Dash
from dash.exceptions import PreventUpdate
from flask import session

from connections.fetch_data_mongo import find_user_by_strava_id
from connections.insert_data_to_mongo import insert_new_user_to_mongo
from dash_apps.app.utils.conversion import convert_birthday, calculate_age


def login_callbacks(dash_app: Dash):
    @dash_app.callback(
        Output("url", "href", allow_duplicate=True),
        Input("first-login-submit-button", "n_clicks"),
        State("first-login-name-input", "value"),
        State("first-login-email-input", "value"),
        State("first-login-birthday", "date"),
        prevent_initial_call=True,
    )
    def store_user_and_redirect(button_click, name, email_address, birthday):
        if not button_click:
            raise PreventUpdate

        converted_bd = convert_birthday(birthday)
        # Data to be inserted
        max_bpm = 220 - calculate_age(converted_bd)
        data = {
            "strava_id": session["athlete"]["id"],
            "name": name,
            "email": email_address,
            "birthday": converted_bd,
            "max_bpm": max_bpm,
        }
        # Insert data
        insert_new_user_to_mongo(data)

        user = find_user_by_strava_id(strava_id=session["athlete"]["id"])
        user["_id"] = str(user["_id"])
        session["run_together_user"] = user
        return "/home"
