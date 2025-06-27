import logging

from dash import html

from dash_apps.app.components.calendar_training import get_monthly_calendar


def get_body(year: int, month: str):

    logging.info(f"""Initialisation of the Body for year: {year} & month: {month} """)
    grid = html.Div(
        className="calendar-container",
        children=[
            html.Div(
                style={"font-size": "24px", "font-weight": "bold"},
                children="Training Calendar",
            ),
            html.Div(
                children=get_monthly_calendar(year=year, month=month),
                id="calendar-training-container",
            ),
        ],
    )

    return html.Div(children=[grid])
