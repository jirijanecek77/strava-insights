import dash_bootstrap_components as dbc
from dash import html, register_page, dcc

from dash_apps.run_together.layout.footer import get_footer
from dash_apps.run_together.layout.header import get_header

register_page(__name__, name="Settings", top_nav=True, path="/settings")

card_style = {"color": "black", "fontSize": "15px"}

hours_options = [{"label": str(i), "value": i} for i in range(6)]
minutes_seconds_options = [{"label": str(i), "value": i} for i in range(61)]


def get_settings():
    return dbc.Container(
        [
            dbc.Card(
                dbc.CardBody(
                    [
                        dbc.Label("User Information", className="h2"),
                        html.Div(id="display-div"),
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
                                        dbc.Label("Speed max:"),
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
                                    value=0,
                                    placeholder="Hours",
                                ),
                                html.Label("h"),
                                dcc.Dropdown(
                                    id="minutes-dropdown",
                                    options=minutes_seconds_options,
                                    value=0,
                                    placeholder="Minutes",
                                ),
                                html.Label("min"),
                                dcc.Dropdown(
                                    id="seconds-dropdown",
                                    options=minutes_seconds_options,
                                    value=0,
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
