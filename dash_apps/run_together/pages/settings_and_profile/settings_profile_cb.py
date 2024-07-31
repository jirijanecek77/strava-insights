from flask import session
import dash
from dash import Output, Input, State, html, no_update, dcc
from dash_extensions.enrich import DashProxy
import logging
from connections.mongodb import MongoConnection
from dash_apps.run_together.utils.conversion import (
    convert_birthday_back, convert_birthday, marathon_pace, calculate_speed_max)


def settings_profile_cb(dash_app: DashProxy):
    @dash_app.callback(
        Output("display-div", "children"),
        Output("form-div", "children"),
        Input("url", "pathname"),
    )
    def toggle_form(url_path):
        user_values = session.get("run_together_user", {})
        if url_path == "/settings":
            display = html.Div([
                html.P(f"Name: {user_values['name']}"),
                html.P(f"Email: {user_values['email']}"),
                html.P(f"Birthday: {user_values['birthday']}")
            ])
            form = html.Div()
            return display, form
        return no_update

    @dash_app.callback(
        Output("display-div", "children"),
        Output("form-div", "children"),
        Output("change-button", "style"),
        Input("change-button", "n_clicks"),
        prevent_initial_call=True
    )
    def display_user_form(n_clicks):
        if n_clicks:
            user_values = session.get("run_together_user", {})
            display = html.Div()
            form = html.Div(
                children=[
                    html.Form([
                        html.Div([
                            html.Label("Name:"),
                            dcc.Input(
                                type="text", id="name-input",
                                className="user-input-field",
                                placeholder="Enter your name",
                                value=user_values["name"],
                                required=True
                            ),
                        ]),
                        html.Div([
                            html.Label("Email Address:"),
                            dcc.Input(
                                type="email", id="email-input",
                                className="user-input-field",
                                placeholder="Enter your email",
                                value=user_values["email"],
                                required=True)
                        ]),
                        html.Div([
                            html.Label("Birthday:"),
                            dcc.DatePickerSingle(
                                id="birthday-input",
                                display_format="DD-MM-YYYY",
                                placeholder="Select your birthday",
                                date=convert_birthday_back(user_values["birthday"]),
                                className="user-input-field"
                            )
                        ]),
                    ]),
                    html.Button("Submit", id="submit-button-user-form", n_clicks=0)
                ],
                className="user-settings-form-container"
            )
            return display, form, {"display": "none"}
        return no_update

    @dash_app.callback(
        Output('display-div', 'children'),
        Output('form-div', 'children'),
        Output("change-button", "style"),
        Input('submit-button-user-form', 'n_clicks'),
        State('name-input', 'value'),
        State('email-input', 'value'),
        State('birthday-input', 'date'),
        prevent_initial_call=True
    )
    def update_output(submit_clicks, name, email, birthday):
        if submit_clicks != 0:
            ctx = dash.callback_context
            if not ctx.triggered:
                return no_update
            else:
                button_id = ctx.triggered[0]["prop_id"].split(".")[0]
            if button_id == "submit-button-user-form":
                converted_bd = convert_birthday(birthday)
                mongo_connection = MongoConnection("localhost:27017", "mydatabase")
                collection = mongo_connection.collection_con("mycollection")

                result = collection.update_one(
                    {"strava_id": session["athlete"]["id"]},
                    {"$set": {
                        "birthday": converted_bd,
                        "name": name,
                        "email": email
                        }}
                )
                session["run_together_user"]["birthday"] = converted_bd
                session["run_together_user"]["name"] = name
                session["run_together_user"]["email"] = email
                session.modified = True
                display = html.Div([
                    html.P(f"Name: {name}"),
                    html.P(f"Email: {email}"),
                    html.P(f"Birthday: {converted_bd}")
                ])
                form = html.Div()
                if result.matched_count > 0:
                    logging.info(f"Successfully updated {result.modified_count} document(s).")
                else:
                    logging.info("No document matched the filter criteria.")
                return display, form, {"display": "block"}

        return no_update

    @dash_app.callback(
        Output("calculated-pace", "children"),
        Output("speed-max", "children"),
        Input('calculate-pace-button', 'n_clicks'),
        Input('ten-k-button', 'n_clicks'),
        Input('semi-button', 'n_clicks'),
        Input('full-button', 'n_clicks'),
        State("seconds-dropdown", "value"),
        State("minutes-dropdown", "value"),
        State("hours-dropdown", "value"),
        prevent_initial_call=True
    )
    def calculate_pace_and_save(calculate_pace_click, distance_ten, distance_semi, distance_full, seconds, minutes, hours):
        ctx = dash.callback_context

        if not ctx.triggered:
            button_id = 'No clicks yet'
            distance = None
            return no_update
        else:
            button_id = ctx.triggered[0]['prop_id'].split('.')[0]
            if button_id == 'ten-k-button':
                distance = 10
            elif button_id == 'semi-button':
                distance = 21.4125
            elif button_id == 'full-button':
                distance = 41.925
        if hours is None or minutes is None or seconds is None:
            return html.P("Please fill in all the dropdowns")
        else:
            min, sec = marathon_pace(hours, minutes, seconds, distance)

            speed_max = calculate_speed_max((min+(sec/60)))
            mongo_connection = MongoConnection("localhost:27017", "mydatabase")
            collection = mongo_connection.collection_con("mycollection")

            result = collection.update_one(
                {"strava_id": session["athlete"]["id"]},
                {"$set": {
                    "speed_max": speed_max
                    }}
            )
            if result.matched_count > 0:
                logging.info(f"Successfully updated {result.modified_count} document(s).")
            else:
                logging.info("No document matched the filter criteria.")

            session["run_together_user"]["speed_max"] = speed_max
            session.modified = True
            return html.P(f'Min:{min} Seconds{sec}'), html.P(f"{speed_max}")
