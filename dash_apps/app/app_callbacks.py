import logging
from datetime import datetime, date

import dash
import dash_leaflet as dl
from dash import Input, Output, ctx, ALL, no_update, Dash
from flask import session

from dash_apps.app.components.activity_details import get_activity_details
from dash_apps.app.components.calendar_training import get_monthly_calendar
from dash_apps.app.components.calendar_training import get_yearly_calendar
from dash_apps.app.pages.home import get_home_layout


def app_callbacks(
    dash_app: Dash,
    app_path: str,
):
    dash.register_page(__name__, layout=get_home_layout, path=app_path)

    @dash_app.callback(
        Output("url", "href", allow_duplicate=True),
        Input("profile-picture", "n_clicks"),
        prevent_initial_call=True,
    )
    def go_to_settings(n_clicks):
        if n_clicks > 0:
            return "/settings"
        return no_update, no_update

    @dash_app.callback(
        Output("marker-map", "children"),
        Input("activity-graph", "hoverData"),
        Input("extended-stream", "data"),
        prevent_initial_call=True,
    )
    def display_hover_data(hover_data, activity_stream):
        index = hover_data["points"][0]["pointIndex"]
        position = activity_stream["latlng"]["data"][index]

        return [dl.Marker(position=position)]

    @dash_app.callback(
        Output("modal", "is_open"),
        Output("modal-header", "children"),
        Output("modal-content", "children"),
        Input({"type": "select-activity-btn", "index": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def display_modal_box(n_clicks):
        """
        Open the Modal box when user click on one activity
        :param n_clicks:  User Clicking on the activity
        :return: is_open = True for the model Component
        """
        # When the Component is build it can trigger the callback to avoid it
        # check that n_click is not None
        if all(x is None for x in n_clicks):
            return no_update, no_update, no_update

        session["displayed_activity_id"] = ctx.triggered_id["index"]
        logging.info(
            f"User Action: select-activity-btn. Get Activity: "
            f"id={session['displayed_activity_id']}"
        )

        modal_header, modal_content = get_activity_details(
            activity_id=session["displayed_activity_id"]
        )

        return True, modal_header, modal_content

    @dash_app.callback(
        Output("calendar-training-container", "children"),
        Input({"type": "select-month-btn", "index": ALL}, "n_clicks"),
        Input({"type": "calendar-btn", "index": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def update_calendar_training_container(
        month_n_clicks,
        calendar_n_clicks,
    ):
        triggered_id = ctx.triggered_id

        # Case: the user select the months on the monthly calendar
        if triggered_id["type"] == "select-month-btn":
            # Change the value for the selected month according to the user selection
            session["selected_month"] = triggered_id["index"]
            logging.info(
                f"User Action: select-month-btn. Get Monthly Calendar: "
                f"year={session['selected_year']} & month={session['selected_month']}"
            )

            return get_monthly_calendar(
                year=session["selected_year"],
                month=session["selected_month"],
            )

        # Case: the user click on the previous month on the monthly calendar
        if triggered_id.index == "prev-month":
            # If Month is JAN, update the year to the previous one
            if session["selected_month"] == "JANUARY":
                session["selected_month"] = "DECEMBER"
                session["selected_year"] = session["selected_year"] - 1
            # Else get the previous month in the correct format JAN, FEB etc
            else:
                month_number = (
                    datetime.strptime(session["selected_month"], "%B").month - 1
                )
                session["selected_month"] = datetime.strftime(
                    date(session["selected_year"], month_number, 1), "%B"
                ).upper()

            logging.info(
                f"User Action: prev-month. Get Monthly Calendar: "
                f"year={session['selected_year']} & month={session['selected_month']}"
            )
            return get_monthly_calendar(
                year=session["selected_year"],
                month=session["selected_month"],
            )

        # Case: the user click on the next month on the monthly calendar
        if triggered_id.index == "next-month":
            # If Month is DEC, update the year to the next one
            if session["selected_month"] == "DECEMBER":
                session["selected_month"] = "JANUARY"
                session["selected_year"] = session["selected_year"] + 1
            # Else get the next month in the correct format JAN, FEB et
            else:
                month_number = (
                    datetime.strptime(session["selected_month"], "%B").month + 1
                )
                session["selected_month"] = datetime.strftime(
                    date(session["selected_year"], month_number, 1), "%B"
                ).upper()

            logging.info(
                f"User Action: next-month. Get Monthly Calendar: "
                f"year={session['selected_year']} & month={session['selected_month']}"
            )
            return get_monthly_calendar(
                year=session["selected_year"],
                month=session["selected_month"],
            )

        # Case: the user click on `back to yearly calendar` from the monthly calendar
        if triggered_id.index == "back-yearly-calendar":
            logging.info(
                f"User Action: back-yearly-calendar. Get yearly Calendar: "
                f"year={session['selected_year']}"
            )
            return get_yearly_calendar(year=session["selected_year"])

        # Case: the user click on the previous year on the yearly calendar
        if triggered_id.index == "prev-year":
            session["selected_year"] = session["selected_year"] - 1

            logging.info(
                f"User Action: prev-year. Get yearly Calendar: year={session['selected_year']}"
            )
            return get_yearly_calendar(year=session["selected_year"])

        # Case: the user click on the next year on the yearly calendar
        if triggered_id.index == "next-year":
            session["selected_year"] = session["selected_year"] + 1

            logging.info(
                f"User Action: next-year. Get yearly Calendar: year={session['selected_year']}"
            )
            return get_yearly_calendar(year=session["selected_year"])
