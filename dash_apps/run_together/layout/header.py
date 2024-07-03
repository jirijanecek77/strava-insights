from dash import html
from flask import session
import dash_bootstrap_components as dbc
import dash_core_components as dcc


# Sample styles
container_style = {
    'display': 'flex',
    'justifyContent': 'space-between',
    'alignItems': 'center',
    'padding': '10px',
    'backgroundColor': '#f8f9fa',
    'height': '60px',  # Reduce header height
}

shoe_image_style = {
    'height': '75px',  # Smaller shoe image
}

avatar_style = {
    'height': '50px',  # Smaller height
    'width': '50px',   # Smaller width
    'borderRadius': '50%',
    'cursor': 'pointer',
}

name_application = {
    'fontSize': '20px',  # Smaller font size
    'fontWeight': 'bold',
}

profile_menu_container_style = {
    'display': 'flex',
    'alignItems': 'center',  # Center align vertically
}

menu_style = {
    "background": "#f8f9fa",
    "color": "black",
    "border": "3px solid black",
    "marginRight": "20px",
    "fontSize": "15px",
    "fontWeight": "bold"
}

menu_item_style = {
    "color": "black",
    "fontSize": "15px"
}


def get_header():
    header = html.Div(
        children=[
            html.Img(
                src="../../../static/img/running_shoe.png",
                alt="Running Shoe",
                style=shoe_image_style,  # Apply new style
            ),
            html.Div(
                children="Run Together",
                style=name_application,
            ),
            html.Div(
                id="profile-menu-container",
                children=[
                    dbc.DropdownMenu(
                        label="Menu",
                        id="dropdown-menu",
                        children=[
                            dbc.DropdownMenuItem("Home", href='/home', style=menu_item_style),
                            dbc.DropdownMenuItem("Settings", href='/settings', style=menu_item_style),
                            dbc.DropdownMenuItem("Profile", href='/settings', style=menu_item_style),
                            dbc.DropdownMenuItem("Subscription", href='/settings', style=menu_item_style)
                        ],
                        toggle_style=menu_style
                    ),
                    dcc.Location(id='url', refresh=True),
                    html.Img(
                        src=session["user_profile_picture"],
                        alt="Profile Picture",
                        id="profile-picture",
                        style=avatar_style,
                        n_clicks=0
                    ),
                ],
                style=profile_menu_container_style
            )
        ],
        style=container_style
    )

    return header
