import pytest

from app.infrastructure.garmin.client import GarminAuthClient, GarminLoginError


class NormalLoginClient:
    def __init__(self, **kwargs):
        self.constructor_kwargs = kwargs
        self.login_calls = 0
        self.client = self

    def login(self, **_kwargs):
        self.login_calls += 1
        if self.login_calls > 1:
            raise RuntimeError("login may only be called once")
        return None

    def get_full_name(self):
        return "Test Garmin Athlete"

    def dumps(self):
        return '{"di_token":"opaque-token"}'


def test_non_mfa_login_uses_public_garmin_flow_and_serializes_safe_tokens():
    clients = []

    def factory(**kwargs):
        client = NormalLoginClient(**kwargs)
        clients.append(client)
        return client

    client, profile = GarminAuthClient(factory).login("athlete@example.com", "secret")

    assert client is clients[0]
    assert clients[0].login_calls == 1
    assert clients[0].constructor_kwargs["email"] == "athlete@example.com"
    assert clients[0].constructor_kwargs["password"] == "secret"
    assert "return_on_mfa" not in clients[0].constructor_kwargs
    assert "prompt_mfa" not in clients[0].constructor_kwargs
    assert profile.display_name == "Test Garmin Athlete"
    assert GarminAuthClient.token_json(client) == '{"di_token":"opaque-token"}'
    assert "secret" not in GarminAuthClient.token_json(client)
