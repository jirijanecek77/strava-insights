from flask import session
import dash
from dash import Output, Input, State, html, no_update, dcc
from dash_extensions.enrich import DashProxy
from dash_apps.run_together.pages.settings_and_profile.settings_profile_helper_method import which_race_button, which_race_distance
from connections.update_data_mongo import update_user_record
from dash_apps.run_together.utils.conversion import (
    convert_birthday_back, convert_birthday, marathon_pace, calculate_speed_max)
from dash_apps.run_together.utils.conversion import calculate_age


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

                max_bpm = 220 - calculate_age(
                    convert_birthday)

                update_user_record(session, {
                    "birthday": converted_bd,
                    "name": name,
                    "email": email,
                    "max_bpm": max_bpm}
                )
                session["run_together_user"]["max_bpm"] = max_bpm
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

                return display, form, {"display": "block"}

        return no_update

    @dash_app.callback(
        Output("max-bpm", "children"),
        Output("calculated-pace", "children"),
        Output("speed-max", "children"),
        Input("url", "pathname")
    )
    def calculate_max_bpm(url: str):
        if url == '/settings':
            max_bpm = session["run_together_user"]["max_bpm"]
            pace = session["run_together_user"].get("pace", 0)
            speed_max = session["run_together_user"].get("speed_max", 0)
            race_distance = session["run_together_user"].get("race_distance", 0)
            target_time = session["run_together_user"].get("target_time", {
                    "hours": 0, "minutes": 0, "seconds": 0})

            if (
                pace == 0 or speed_max == 0 or race_distance == 0 or
                target_time == {"hours": 0, "minutes": 0, "seconds": 0}
            ):
                return '', html.P("Please fill in your target time and click the race you plan to run"), html.P("")
            else:
                pace_min, pace_sec = marathon_pace(
                    target_time["hours"], target_time["minutes"],
                    target_time["seconds"], race_distance)

                return max_bpm, html.P(f'Min:{pace_min} Seconds:{pace_sec} for {race_distance}'), html.P(f"{speed_max}")
        else:
            no_update

    @dash_app.callback(
        Output("calculated-pace", "children"),
        Output("speed-max", "children"),
        Output("max-bpm", "children"),
        Input('ten-k-button', 'n_clicks'),
        Input('semi-button', 'n_clicks'),
        Input('full-button', 'n_clicks'),
        State("seconds-dropdown", "value"),
        State("minutes-dropdown", "value"),
        State("hours-dropdown", "value"),
        prevent_initial_call=True
    )
    def calculate_pace_and_save(distance_ten, distance_semi, distance_full, seconds, minutes, hours):
        ctx = dash.callback_context

        if not ctx.triggered:
            button_id = 'No clicks yet'
            distance = None
            return no_update
        else:
            button_id = ctx.triggered[0]['prop_id'].split('.')[0]
            distance, coefficient = which_race_button(button_id)

        if hours is None or minutes is None or seconds is None:
            return html.P("Please fill in all the dropdowns")
        else:
            min, sec = marathon_pace(hours, minutes, seconds, distance)
            pace = min+(sec/60)

            speed_max = calculate_speed_max((min+(sec/60)), coefficient)
            race_distance = which_race_distance(button_id)

            update_user_record(session, {
                "speed_max": speed_max,
                "pace": pace,
                "race_distance": distance,
                "target_time": {
                    "hours": hours, "minutes": minutes, "seconds": seconds}
                }
            )
            max_bpm = session["run_together_user"]["max_bpm"]
            session["run_together_user"]["target_time"] = (hours, minutes, seconds)
            session["run_together_user"]["speed_max"] = speed_max
            session["run_together_user"]["pace"] = pace
            session["run_together_user"]["race_distance"] = distance
            session["run_together_user"]["race"] = race_distance
            session.modified = True

            return html.P(f'Min:{min} Seconds:{sec} for {race_distance}'), html.P(f"{speed_max}"), max_bpm
