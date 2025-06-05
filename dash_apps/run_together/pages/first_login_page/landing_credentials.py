import dash_bootstrap_components as dbc
from dash import dcc
from dash import html, register_page


register_page(
    __name__, name="Welcome to Strava Insights", top_nav=True, path="/welcome"
)


def welcome_cards():

    return dbc.Container(
        [
            html.H1("User Information Form"),
            dbc.Form(
                [
                    dbc.CardGroup(
                        [
                            dbc.Label("Name", html_for="name-input"),
                            dbc.Input(
                                type="text",
                                id="first-login-name-input",
                                placeholder="Enter your name",
                            ),
                        ]
                    ),
                    dbc.CardGroup(
                        [
                            dbc.Label("Email", html_for="email-input"),
                            dbc.Input(
                                type="email",
                                id="first-login-email-input",
                                placeholder="Enter your email address",
                            ),
                        ]
                    ),
                    dbc.CardGroup(
                        [
                            dbc.Label("Birthday", html_for="birthday-input"),
                            dcc.DatePickerSingle(
                                id="first-login-birthday",
                                date="01-01-1990",
                                display_format="DD-MM-YYYY",
                                placeholder="Select a date",
                                style={"width": "100%"},
                            ),
                        ]
                    ),
                    dbc.Button(
                        "Submit",
                        id="first-login-submit-button",
                        color="primary",
                        className="mr-2",
                    ),
                    html.Div(id="output-state"),
                ]
            ),
        ]
    )


def layout():
    body = welcome_cards()

    basic_components = [
        html.Div(children=[body], style={"flex": "1", "padding": "20px"})
    ]

    return html.Div(
        style={"display": "flex", "flexDirection": "column", "minHeight": "100vh"},
        children=basic_components,
    )
