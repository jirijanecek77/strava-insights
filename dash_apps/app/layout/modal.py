import dash_bootstrap_components as dbc
from dash.development.base_component import Component


def get_modal_box() -> Component:
    return dbc.Modal(
        children=[
            dbc.ModalHeader(id="modal-header"),
            dbc.ModalBody(id="modal-content"),
        ],
        id="modal",
        is_open=False,
        size="xl",
        fade=True,
        centered=True,
        className="mw-100 p-5",
    )
