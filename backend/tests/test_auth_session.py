from app.application.auth.current_user import CurrentUserService


def test_get_current_session_requires_authentication(client) -> None:
    response = client.get("/auth/session")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required."}


def test_current_user_service_returns_user_from_session() -> None:
    request = type(
        "RequestStub",
        (),
        {
            "session": {
                "user": {
                    "id": 1,
                    "strava_athlete_id": 162181,
                    "display_name": "Test Athlete",
                    "profile_picture_url": None,
                }
            }
        },
    )()

    current_user = CurrentUserService().get_current_user(request)

    assert current_user is not None
    assert current_user.model_dump() == {
        "id": 1,
        "strava_athlete_id": 162181,
        "display_name": "Test Athlete",
        "profile_picture_url": None,
    }
