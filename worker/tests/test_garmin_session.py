from app.garmin_client import GarminApiClient
from datetime import datetime


class GarminClientStub:
    def __init__(self) -> None:
        self.client = self
        self.login_tokens: list[str] = []
        self.get_activities_calls = 0
        self.get_detail_calls = 0

    def login(self, token_json: str) -> None:
        self.login_tokens.append(token_json)

    def dumps(self) -> str:
        return '{"di_token":"refreshed-access","di_refresh_token":"refreshed-refresh"}'

    def get_activities_by_date(self, *_args, **_kwargs):
        self.get_activities_calls += 1
        return []

    def get_activity_details(self, _activity_id: int):
        self.get_detail_calls += 1
        return {"metrics": []}


def test_authenticated_session_is_reused_and_exposes_refreshed_tokens() -> None:
    created_clients: list[GarminClientStub] = []
    factory_tokens: list[str] = []

    def factory(token_json: str) -> GarminClientStub:
        factory_tokens.append(token_json)
        client = GarminClientStub()
        created_clients.append(client)
        return client

    api = GarminApiClient(client_factory=factory)

    session = api.connect('{"di_token":"stored-access"}')
    api.get_activities(session, after=datetime(2026, 1, 1))
    api.get_activity_stream(session, 123)

    assert len(created_clients) == 1
    assert factory_tokens == ['{"di_token":"stored-access"}']
    assert created_clients[0].get_activities_calls == 1
    assert created_clients[0].get_detail_calls == 1
    assert session.token_json() == '{"di_token":"refreshed-access","di_refresh_token":"refreshed-refresh"}'
