from dash import Output, Input, State, no_update
from dash_extensions.enrich import DashProxy
from flask import session
from connections.mongodb import MongoConnection
from dash_apps.run_together.utils.conversion import convert_birthday, calculate_age
from connections.fetch_data_mongo import find_user_by_strava_id
from connections.insert_data_to_mongo import insert_new_user_to_mongo


def first_login_cb(dash_app: DashProxy):
    @dash_app.callback(
        State("first-login-name-input", "value"),
        State("first-login-email-input", "value"),
        State("first-login-birthday", "date"),
        Input("first-login-submit-button", "n_clicks"),
        Output("url", "href")
    )
    def store_user_and_redirect(name, emailaddress, birthday, button_click):
        if button_click:

            converted_bd = convert_birthday(birthday)
            # Data to be inserted
            max_bpm = 220 - calculate_age(
                converted_bd)
            data = {
                "strava_id": session['athlete']['id'],
                "name": name,
                "email": emailaddress,
                "birthday": converted_bd,
                "max_bpm": max_bpm
            }
            # Insert data
            insert_new_user_to_mongo(data)

            user = find_user_by_strava_id(strava_id=session['athlete']['id'])
            user['_id'] = str(user['_id'])
            session['run_together_user'] = user
            return "/home"
        else:
            return no_update
