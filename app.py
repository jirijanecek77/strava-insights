from os import environ as env

import dash_bootstrap_components as dbc
from dash import Dash
from flask import Flask, session

from blueprints.login.auth import authorisation
from blueprints.login.login import login_blueprint
from dash_apps.app.app_callbacks import app_callbacks
from dash_apps.app.pages.first_login_page.login_callbacks import (
    login_callbacks,
)
from dash_apps.app.pages.settings_and_profile.settings_callbacks import (
    settings_callbacks,
)

# Create the Flask App
app = Flask(__name__)
app.config["SECRET_KEY"] = env["SECRET_KEY"]

app.register_blueprint(login_blueprint)
# To use the small icon in the app & use static file in a sub-folder of static
# Define external stylesheets, including Font Awesome and a local CSS file
external_stylesheets = [
    "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.3/css/all.min.css",
    dbc.themes.BOOTSTRAP,  # Add the path to style.css
]

# Adding the Tailwind CSS script in the application setup
# Define external scripts, including the Tailwind CSS framework
external_script = ["https://tailwindcss.com/", {"src": "https://cdn.tailwindcss.com"}]

# Configure DashProxy instance for the Dash application
dash_app = Dash(
    __name__,  # Set the name of the Dash application
    server=app,  # Connect the Dash application to the Flask app
    title="Strava insights",  # Set the title of the Dash application
    pages_folder="./dash_apps/app/pages/",  # Specify the folder containing Dash page
    use_pages=True,  # Enable the use of pages for organizing Dash layouts
    assets_folder="./static",  # Specify the folder for static assets (e.g., CSS, images)
    external_stylesheets=external_stylesheets,  # Add external stylesheets to the Dash application
    external_scripts=external_script,  # Add external scripts to the Dash application
)

# Flask App need registration
excluded = ["login.landing", "login.strava_callback", "static"]
app = authorisation(app, session, excluded)

# Initialize the Dash application using the configured Dash instance
app_callbacks(dash_app=dash_app, app_path="/home")
login_callbacks(dash_app=dash_app)
settings_callbacks(dash_app=dash_app)

# For the deployment of the application locally
if __name__ == "__main__":
    # Run the Flask app when the script is executed
    app.run(host="0.0.0.0", port=8502, debug=True, use_reloader=True)  #
