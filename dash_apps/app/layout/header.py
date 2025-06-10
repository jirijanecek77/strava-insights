from dash import html, dcc
from flask import session

# Sample styles
container_style = {
    "display": "flex",
    "justifyContent": "space-between",
    "alignItems": "center",
    "padding": "10px",
    "backgroundColor": "#f8f9fa",
    "height": "60px",  # Reduce header height
}

shoe_image_style = {
    "height": "75px",  # Smaller shoe image
}

avatar_style = {
    "height": "50px",  # Smaller height
    "width": "50px",  # Smaller width
    "borderRadius": "50%",
    "cursor": "pointer",
}

name_application = {
    "fontSize": "20px",  # Smaller font size
    "fontWeight": "bold",
}

profile_menu_container_style = {
    "display": "flex",
    "alignItems": "center",  # Center align vertically
}

menu_style = {
    "background": "#f8f9fa",
    "color": "black",
    "border": "3px solid black",
    "marginRight": "20px",
    "fontSize": "15px",
    "fontWeight": "bold",
}

menu_item_style = {"color": "black", "fontSize": "15px"}


def get_header():
    header = html.Div(
        children=[
            html.Img(
                src="../../../static/img/running_shoe.png",
                alt="Running Shoe",
                style=shoe_image_style,
            ),
            html.Div(
                children=[
                    dcc.Link(
                        children="Strava Insights", href="/home", style=name_application
                    )
                ],
                style=name_application,
            ),
            html.Div(
                id="profile-menu-container",
                children=[
                    dcc.Location(id="url", refresh=True),
                    html.Img(
                        src=session.get(
                            "user_profile_picture", "static/img/empty_profile.png"
                        ),
                        alt="Profile Picture",
                        id="profile-picture",
                        style=avatar_style,
                        n_clicks=0,
                    ),
                ],
                style=profile_menu_container_style,
            ),
        ],
        style=container_style,
    )

    return header
