from itsdangerous import BadSignature, URLSafeSerializer
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse

from app.application.auth.current_user import CurrentUserService
from app.application.auth.oauth import StravaOAuthService
from app.application.sync.orchestrator import SyncOrchestrator
from app.core.config import settings
from app.domain.schemas.user import CurrentUserResponse


router = APIRouter(prefix="/auth")


def _build_state_serializer() -> URLSafeSerializer:
    return URLSafeSerializer(settings.session_secret_key, salt="strava-oauth-state")


@router.get("/strava/login")
def start_strava_login(
    request: Request,
    strava_oauth_service: StravaOAuthService = Depends(StravaOAuthService),
) -> dict[str, str]:
    state = _build_state_serializer().dumps({"client": request.client.host if request.client else "unknown"})
    request.session["oauth_state"] = state
    return {"authorization_url": strava_oauth_service.build_authorization_url(state)}


@router.get("/strava/callback", response_class=RedirectResponse, status_code=status.HTTP_302_FOUND)
def strava_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    strava_oauth_service: StravaOAuthService = Depends(StravaOAuthService),
    sync_orchestrator: SyncOrchestrator = Depends(SyncOrchestrator),
) -> RedirectResponse:
    expected_state = request.session.get("oauth_state")
    if expected_state is None or state != expected_state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state.")

    try:
        _build_state_serializer().loads(state)
    except BadSignature as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state.") from exc

    authenticated_user = strava_oauth_service.authenticate_from_code(code)
    if authenticated_user.is_new_user:
        sync_orchestrator.enqueue_first_import_if_needed(authenticated_user.id)
    request.session["user"] = {
        "id": authenticated_user.id,
        "strava_athlete_id": authenticated_user.strava_athlete_id,
        "display_name": authenticated_user.display_name,
        "profile_picture_url": authenticated_user.profile_picture_url,
    }
    request.session.pop("oauth_state", None)

    return RedirectResponse(url=settings.frontend_public_url, status_code=status.HTTP_302_FOUND)


@router.get("/session", response_model=CurrentUserResponse)
def get_current_session(
    request: Request,
    current_user_service: CurrentUserService = Depends(CurrentUserService),
) -> CurrentUserResponse:
    user = current_user_service.get_current_user(request)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )

    return CurrentUserResponse.model_validate(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request) -> None:
    request.session.clear()
