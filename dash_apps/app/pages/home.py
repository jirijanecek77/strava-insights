import logging
import time
from datetime import datetime

from dash import html
from flask import session

from dash_apps.app.layout.body import get_body
from dash_apps.app.layout.header import get_header
from dash_apps.app.layout.modal import get_modal_box
from dash_apps.app.model.strava_manager import StravaManager


def get_home_layout() -> html:
    strava_manager = StravaManager(session=False)

    # no token yet associate to the session
    if "expires_at" not in session:
        strava_manager.generate_token_response(strava_code=session.get("strava_code"))
    # token expired
    elif time.time() > session["expires_at"]:
        strava_manager.generate_token_response(strava_code=session.get("strava_code"))
    else:
        strava_manager.set_token_from_session()

    session["selected_year"] = datetime.now().year
    session["selected_month"] = datetime.now().strftime("%B").upper()

    # Add in the session the current athlete
    athlete = strava_manager.get_athlete()
    if athlete.profile == "avatar/athlete/large.png":
        session["user_profile_picture"] = "../../../static/img/empty_profile.png"
    else:
        session["user_profile_picture"] = athlete.profile

    header = get_header()
    body = get_body(year=session["selected_year"], month=session["selected_month"])
    modal_box = get_modal_box()

    basic_components = [header, html.Br(), body, html.Br(), modal_box]
    logging.info("Building home page")
    return html.Div(children=basic_components)
