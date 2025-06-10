import dash_bootstrap_components as dbc
from dash import html, register_page, dcc
from flask import session

from dash_apps.app.layout.footer import get_footer
from dash_apps.app.layout.header import get_header

register_page(__name__, name="Settings", top_nav=True, path="/settings")

card_style = {"color": "black", "fontSize": "15px"}

hours_options = [{"label": str(i), "value": i} for i in range(6)]
minutes_seconds_options = [{"label": str(i), "value": i} for i in range(61)]


def get_settings():
    user = session.get("run_together_user", {})
    hours, minutes, seconds = user.get(
        "target_time", {"hours": 0, "minutes": 0, "seconds": 0}
    ).values()
    return dbc.Container(
        [
            dbc.Card(
                dbc.CardBody(
                    [
                        dbc.Label("User Information", className="h2"),
                        dbc.Row(dbc.Label(f"Name: {user.get('name')}")),
                        dbc.Row(dbc.Label(f"Email: {user.get('email')}")),
                        dbc.Row(
                            dbc.Label(f"Birthday: {user.get('birthday')}"),
                            className="mb-3",
                        ),
                        dbc.Label("Race pace setting", className="h2"),
                        html.Div(
                            children=[
                                dbc.Stack(
                                    [
                                        dbc.Label("Pace:"),
                                        dbc.Label(id="calculated-pace"),
                                    ],
                                    gap=2,
                                    direction="horizontal",
                                ),
                                dbc.Stack(
                                    [
                                        dbc.Label(
                                            html.A(
                                                "Maximum aerobic speed:",
                                                href="https://medium.com/@matthieu.ru/simplifying-training-performance-with-race-pace-heart-rate-zones-9c0ceea5a1d6",
                                            )
                                        ),
                                        dbc.Label(id="speed-max"),
                                        dbc.Label("km/h"),
                                    ],
                                    gap=2,
                                    direction="horizontal",
                                ),
                                dbc.Stack(
                                    children=[
                                        dbc.Label("Max HR:"),
                                        dbc.Label(id="max-bpm"),
                                        dbc.Label("bpm"),
                                    ],
                                    gap=2,
                                    direction="horizontal",
                                ),
                            ],
                        ),
                        dbc.Stack(
                            children=[
                                html.Label("Target time:"),
                                dcc.Dropdown(
                                    id="hours-dropdown",
                                    options=hours_options,
                                    value=hours,
                                    placeholder="Hours",
                                ),
                                html.Label("h"),
                                dcc.Dropdown(
                                    id="minutes-dropdown",
                                    options=minutes_seconds_options,
                                    value=minutes,
                                    placeholder="Minutes",
                                ),
                                html.Label("min"),
                                dcc.Dropdown(
                                    id="seconds-dropdown",
                                    options=minutes_seconds_options,
                                    value=seconds,
                                    placeholder="Seconds",
                                ),
                                html.Label("sec"),
                            ],
                            gap=2,
                            direction="horizontal",
                            className="mb-3",
                        ),
                        html.Div(
                            children=[
                                dbc.Button(
                                    "10 kilometers",
                                    id="ten-k-button",
                                    color="secondary",
                                    className="mr-2",
                                ),
                                dbc.Button(
                                    "Half-marathon",
                                    id="semi-button",
                                    color="secondary",
                                    className="mr-2",
                                ),
                                dbc.Button(
                                    "Marathon", id="full-button", color="secondary"
                                ),
                            ],
                        ),
                    ],
                )
            ),
        ]
    )


def layout():
    header = get_header()
    body = get_settings()
    footer = get_footer()

    return html.Div(
        children=[
            header,
            html.Div(children=body, style={"flex": "1", "padding": "20px"}),
            footer,
        ],
    )
