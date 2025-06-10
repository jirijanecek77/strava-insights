import logging
import time
from datetime import datetime
from os import environ as env

from dotenv import load_dotenv
from flask import Blueprint, render_template
from flask import request, redirect, session
from stravalib import client

from connections.fetch_data_mongo import find_user_by_strava_id
from dash_apps.app.model.strava_manager import StravaManager

# Create the Blueprint Login
login_blueprint = Blueprint(
    "login",
    __name__,
    template_folder="templates",  # Find the HTML template folder
    static_folder="static",  # Find the CSS file style folder
)

# Load .env file where are stored my strava credential
load_dotenv()
strava_client_id = int(env["STRAVA_CLIENT_ID"])
strava_client_secret = env["STRAVA_CLIENT_SECRET"]
web_app_url = env["WEB_APP_URL"]
mapy_cz_api_key = env["MAPY_CZ_API_KEY"]

# Strava Lib Client
client = client.Client()


@login_blueprint.route("/")
def landing():
    """Get the URL needed to authorize your application to access a Strava
    user's information.
    Add this URL as a parameter of my HTML file login.html as redirect of the login Button
    """
    redirect_uri = f"{web_app_url}/callback"
    logging.info(f"Login Completed, redirection: {redirect_uri}")
    authorize_url = client.authorization_url(
        client_id=strava_client_id,
        redirect_uri=redirect_uri,
        scope=["read_all", "profile:read_all", "activity:read_all", "activity:write"],
    )
    logging.info(f"Login Completed, authorize_url: {authorize_url}")

    return render_template("login.html", authorize_url=authorize_url)


@login_blueprint.route("/callback")
def strava_callback():
    """Strava the code needed to get the user's data in Callback in the following ULR:
    web_app_url/run-together/?state=&code={code}&scope=read,activity:read_all,profile:read_all,read_all
    This function get the code, put it in the Flash Session.
    Redirect to the Dash
        Add this URL as a parameter of my HTML file login.html as redirect of the login Button
    """
    # Get the code parameter from the URL
    code = request.args.get("code")

    # add in to the Flask Session
    session["strava_code"] = code
    session["user"] = {}

    strava_manager = StravaManager(session=False)

    # no token yet associate to the session
    # TODO: move the below logic into a method
    if "expires_at" not in session:
        logging.info("running generate token from login")
        strava_manager.generate_token_response(strava_code=session["strava_code"])
    # token expired
    elif time.time() > session["expires_at"]:
        logging.info("running else generate token from login")
        strava_manager.generate_token_response(strava_code=session["strava_code"])
    else:
        strava_manager.set_token_from_session()

    session["selected_year"] = datetime.now().year
    session["selected_month"] = datetime.now().strftime("%B").upper()

    # Add in the session the current athlete
    athlete = strava_manager.get_athlete_v2()
    session["athlete"] = athlete

    # Check if StravaId already exists in MongoDB
    user = find_user_by_strava_id(strava_id=athlete["id"])

    if user:
        logging.info("User already registered, redirect to home page")
        user["_id"] = str(user["_id"])
        session["run_together_user"] = user
        session.modified = True
        return redirect("/home")
    else:
        logging.info("User not registered, redirect to welcome page")
        return redirect("/welcome")
