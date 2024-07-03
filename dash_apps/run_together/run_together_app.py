import dash
from dash import Input, Output, ctx, ALL, no_update, State
from dash_extensions.enrich import DashProxy
from flask import session
from datetime import datetime, date
import logging
import dash_leaflet as dl
import plotly.graph_objects as go

from dash_apps.run_together.pages.home import get_home_layout

from dash_apps.run_together.utils.conversion import normalize_value
from dash_apps.run_together.utils.conversion import calculate_pace
from dash_apps.run_together.utils.conversion import convert_min_to_min_sec

from dash_apps.run_together.components.calendar_training import get_monthly_calendar
from dash_apps.run_together.components.calendar_training import get_yearly_calendar
from dash_apps.run_together.components.activity_details import get_activity_details


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
            print(n_clicks)
            return '/settings'
        return no_update, no_update

    @dash_app.callback(
        Output("output", "children"),
        Input("submit-button", "n_clicks"),
        State("email-input", "value"),
    )
    def update_output(n_clicks, email_value):
        if n_clicks > 0:
            from pymongo import MongoClient

            # Connect to MongoDB
            client = MongoClient("mongodb://localhost:27017/")

            # Create or connect to a database
            db = client["mydatabase"]

            # Create or connect to a collection
            collection = db["mycollection"]

            # Data to be inserted
            data = {
                "email": email_value
            }

            # Insert data
            collection.insert_one(data)
            return "Email address submitted"
        return ""

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
                    datetime.strptime(session["selected_month"], "%b").month - 1
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
        Input("range-slider-pace", "value"),
        Input("button-analyze-activity-details", "n_clicks"), # Case to display the working interval
        Input("extended-stream", "data"),
        Input("bpm-pace-mapping", "data"),
        State('activity-graph', 'figure'),
        prevent_initial_call=True,
    )
    def update_calendar_training_container(
        range_slider_pace: int,
        button_analyze_activity_n_clicks,
        extended_stream: dict,
        pace_bpm_mapping: dict,
        figure: go.Figure,
    ):
        triggered_id = ctx.triggered_id
        logging.info(triggered_id)

        # Case: Range is updated & display the recalculate moving pace average.
        if triggered_id == "range-slider-pace":
            # Get the new pace with the new range slider input
            moving_average_pace = {
                'minute_per_km': calculate_pace(
                    seconds=extended_stream['time']['data'][0:],
                    distances=extended_stream['distance']['data'][0:],
                    range_points=range_slider_pace,
                )
            }

            moving_average_pace['minute_second_per_km'] = [
                convert_min_to_min_sec(x)
                for x in moving_average_pace['minute_per_km']
            ]

            # Normalize it based on the user information
            normalized_moving_average_pace = [
                normalize_value(
                    value=x,
                    original_range=[x['pace'] for x in pace_bpm_mapping.values()],
                    target_range=list(range(len(pace_bpm_mapping.values())))
                )
                for x in moving_average_pace['minute_per_km']
            ]

            # Update the graph
            figure['data'][0]['x'] = extended_stream["distance_km"]
            figure['data'][0]['y'] = normalized_moving_average_pace
            figure['data'][0]['customdata'] = moving_average_pace['minute_second_per_km']

            return figure, moving_average_pace

        # if triggered_id == "button-analyze-activity-details":
        #
        #     figure.add_vrect(
        #         x0="2018-09-24",
        #         x1="2018-12-18",
        #         # label=dict(
        #         #     text="Decline",
        #         #     textposition="top center",
        #         #     font=dict(size=20, family="Times New Roman"),
        #         # ),
        #         fillcolor="green",
        #         opacity=0.25,
        #         line_width=0,
        #     )
        #
        # return figure,