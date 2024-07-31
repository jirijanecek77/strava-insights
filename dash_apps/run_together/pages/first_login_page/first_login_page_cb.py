from dash import Output, Input, State, no_update
from dash_extensions.enrich import DashProxy
from flask import session
import logging
from connections.mongodb import MongoConnection
from dash_apps.run_together.utils.conversion import convert_birthday
from connections.fetch_data_mongo import find_user_by_strava_id


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
            mongo_connection = MongoConnection('localhost:27017', 'mydatabase')
            collection = mongo_connection.collection_con('mycollection')

            converted_bd = convert_birthday(birthday)
            # Data to be inserted
            data = {
                "strava_id": session['athlete']['id'],
                "name": name,
                "email": emailaddress,
                "birthday": converted_bd
            }
            # Insert data
            collection.insert_one(data)
            user = find_user_by_strava_id(strava_id=session['athlete']['id'], collection=collection)
            user['_id'] = str(user['_id'])
            session['run_together_user'] = user

            return "/home"
        else:
            return no_update
