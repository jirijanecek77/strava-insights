from dash import html, register_page
import dash_bootstrap_components as dbc

from dash_apps.run_together.layout.header import get_header
from dash_apps.run_together.layout.footer import get_footer


register_page(
    __name__,
    name='Settings',
    top_nav=True,
    path='/settings'
)

card_style = {
    "color": "black",
    "fontSize": "15px"
}


def get_settings():
    settings_tab = dbc.Card(
        dbc.CardBody(
            [
                html.Div(
                    style={
                        'display': 'flex',
                        'flexDirection': 'column',
                        'justifyContent': 'center',
                        'alignItems': 'center',
                        'height': '100vh',
                        'padding': '20px',
                    },
                    children=[
                        # Buttons in the middle of the body
                        html.Div(
                            style={
                                'display': 'flex',
                                'justifyContent': 'center',
                                'alignItems': 'center',
                                'marginBottom': '20px',
                            },
                            children=[
                                dbc.Button("10 kilometers", id="button-1", color="secondary", className="mr-2"),
                                dbc.Button("Semi-marathon", id="button-2", color="secondary", className="mr-2"),
                                dbc.Button("Marathon", id="button-3", color="secondary"),
                            ]
                        ),
                        html.Div(
                            children=[
                                html.P("Hours"),
                                dbc.Input(type="number", min=0, max=5, step=1),
                                html.P("Minutes"),
                                dbc.Input(type="number", min=0, max=60, step=1),
                            ],
                            id="styled-numeric-input",
                        )
                    ]
                )
            ]
        )
    )

    profile_tab = dbc.Card(
        dbc.CardBody(
            [
                html.P("Profile", className="card-text")
            ]
        )
    )

    subscription_tab = dbc.Card(
        dbc.CardBody(
            [
                html.P("Registration below. Only for real action takers", className="card-text"),
                dbc.FormFloating(
                    [
                        dbc.Input(type="email", id="email-input", placeholder="example@internet.com"),
                        dbc.Label("Email address"),
                    ]
                ),
                html.Br(),
                dbc.Button("Submit", id="submit-button", n_clicks=0),
                html.Br(),
                html.Div(id="output")
            ]
        )
    )

    tabs = dbc.Tabs(
        [
            dbc.Tab(
                settings_tab, label="Settings", label_style=card_style,
                tab_id='settings-tab'),
            dbc.Tab(
                profile_tab, label="Profile", label_style=card_style,
                tab_id='profile-tab'),
            dbc.Tab(
                subscription_tab, label="Subscription", label_style=card_style,
                tab_id='subscription-tab')
        ],
        id='settings-tabs',
        active_tab='settings-tab'
    )
    return tabs


def layout():
    header = get_header()
    body = get_settings()
    footer = get_footer()

    basic_components = [
        header,
        html.Div(
            children=[body],
            style={
                "flex": "1",
                "padding": "20px"
            }
        ),
        footer,
    ]

    return html.Div(
        style={
            'display': 'flex',
            'flexDirection': 'column',
            'minHeight': '100vh'
        },
        children=basic_components)
