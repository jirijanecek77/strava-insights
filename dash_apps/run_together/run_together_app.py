import dash
from dash import Input, Output, ctx, ALL, no_update, State
from dash_extensions.enrich import DashProxy
from flask import session
from datetime import datetime, date
import logging
import dash_leaflet as dl
import plotly.graph_objects as go
from typing import Tuple

from dash_apps.run_together.pages.home import get_home_layout

from dash_apps.run_together.utils.activity_update_manager import update_graph_moving_average_pace
from dash_apps.run_together.utils.activity_update_manager import update_graph_display_interval
from dash_apps.run_together.utils.activity_update_manager import update_graph_display_jogging
from dash_apps.run_together.utils.activity_update_manager import update_graph_display_all

from dash_apps.run_together.components.calendar_training import get_monthly_calendar
from dash_apps.run_together.components.calendar_training import get_yearly_calendar
from dash_apps.run_together.components.activity_details import get_activity_details

from dash_apps.run_together.model.strava_manager import StravaManager


def run_together_app(
    dash_app: DashProxy,
    app_path: str,
) -> object:
    dash.register_page(__name__, layout=get_home_layout, path=app_path)

    @dash_app.callback(
        Output('url', 'href'),
        Input('profile-picture', 'n_clicks'),
        prevent_initial_call=True
    )
    def go_to_settings(n_clicks):
        if n_clicks > 0:
            return '/settings'
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
        Output("modal", "hidden"),
        Output("modal-body", "children"),
        Input({"type": "select-activity-btn", "index": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def display_modal_box(n_clicks):
        """
        Open the Modal box when user click on one activity
        :param n_clicks:  User Clicking on the activity
        :return: Hidden = True for the model Component
        """
        # When the Component is build it can trigger the callbakc to avoid it
        # check that n_click is not None
        if all(x is None for x in n_clicks):
            return no_update, no_update

        session["displayed_activity_id"] = ctx.triggered_id["index"]
        logging.info(
            f"User Action: select-activity-btn. Get Activity: "
            f"id={session['displayed_activity_id']}"
        )

        activity_details_modal_content = get_activity_details(
            activity_id=session["displayed_activity_id"]
        )

        return False, activity_details_modal_content

    @dash_app.callback(
        Output("modal", "hidden"),
        Input("close-modal-btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def close_modal_box(n_clicks):
        """
        Clost the Modal box when user click on the cross
        :param n_clicks:  User Clicking on the cross
        :return: Hidden = True for the model Component
        """

        logging.info("User Action: close-modal-btn. Close Modal Box")
        return True

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
            if session["selected_month"] == "JAN":
                session["selected_month"] = "DEC"
                session["selected_year"] = session["selected_year"] - 1
            # Else get the previous month in the correct format JAN, FEB etc
            else:
                month_number = (
                    datetime.strptime(session["selected_month"], "%B").month - 1
                )
                session["selected_month"] = datetime.strftime(
                    date(session["selected_year"], month_number, 1), "%b"
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
            if session["selected_month"] == "DEC":
                session["selected_month"] = "JAN"
                session["selected_year"] = session["selected_year"] + 1
            # Else get the next month in the correct format JAN, FEB et
            else:
                month_number = (
                    datetime.strptime(session["selected_month"], "%b").month + 1
                )
                session["selected_month"] = datetime.strftime(
                    date(session["selected_year"], month_number, 1), "%b"
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

    @dash_app.callback(
        Output("activity-graph", "figure"),
        Output("moving-average-stream", "data"),

        Output("bpm-kpi", "children"),
        Output("pace-kpi", "children"),
        Output("distance-kpi", "children"),

        Output("button-display-interval", "disabled"),  # Case to display the working interval
        Output("button-display-jogging", "disabled"),  # Case to display the working interval
        Output("button-display-all", "disabled"),  # Case to display the working interval

        Input("range-slider-pace", "value"),

        Input("button-display-interval", "n_clicks"), # Case to display the working interval
        Input("button-display-jogging", "n_clicks"),  # Case to display the working interval
        Input("button-display-all", "n_clicks"),  # Case to display the working interval

        Input("extended-stream", "data"),
        Input("bpm-pace-mapping", "data"),
        Input("kpi-bpm-pace-distance-activity", "data"),

        State('activity-graph', 'figure'),
        prevent_initial_call=True,
    )
    def update_calendar_training_container_new(
        range_slider_pace: int,
        button_interval_n_clicks,
        button_jogging_n_clicks,
        button_all_n_clicks,

        extended_stream: dict,
        pace_bpm_mapping: dict,
        kpi_bpm_pace_distance_activity: Tuple,

        figure: go.Figure,
    ):
        triggered_id = ctx.triggered_id

        # Case: Range is updated & display the recalculate moving pace average.
        if triggered_id == "range-slider-pace":
            logging.info(
                f"User Action: Update Graph with new range for Moving Average Pace  "
                f"range={range_slider_pace}"
            )

            return update_graph_moving_average_pace(
                range_slider_pace=range_slider_pace,
                extended_stream=extended_stream,
                pace_bpm_mapping=pace_bpm_mapping,
                kpi_bpm_pace_distance_activity=kpi_bpm_pace_distance_activity,
                figure=figure
            )

        if triggered_id == "button-display-interval":
            logging.info(
                f"User Action: Update Graph, Display intervals"
            )
            return update_graph_display_interval(
                figure=figure
            )

        if triggered_id == "button-display-jogging":
            logging.info(
                f"User Action: Update Graph, Display Jogging"
            )
            return update_graph_display_jogging(
                figure=figure
            )

        if triggered_id == "button-display-all":
            logging.info(
                f"User Action: Update Graph, Display All"
            )
            return update_graph_display_all(
                figure=figure,
                extended_stream=extended_stream,
                kpi_bpm_pace_distance_activity=kpi_bpm_pace_distance_activity
            )

    @dash_app.callback(
        Input("button-update-description-strava", "n_clicks"),
        Output("button-update-description-strava", "disabled"),
        prevent_initial_call=True,
    )
    def update_description_on_strava(n_clicks):
        """
        Clost the Modal box when user click on the cross
        :param n_clicks:  User Clicking on the cross
        :return: Hidden = True for the model Component
        """

        logging.info("User Action: button-update-description-strava. Update Description")
        strava_manager = StravaManager()
        description = strava_manager.get_activity(session["displayed_activity_id"])['description']
        strava_manager.update_description_activity(
            activity_id=session["displayed_activity_id"],
            description=description + str(datetime.now())
        )

        return False
