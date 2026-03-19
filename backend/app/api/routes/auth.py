import logging

from itsdangerous import BadSignature, URLSafeSerializer
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse

from app.application.auth.current_user import CurrentUserService
from app.application.auth.oauth import StravaOAuthService
from app.application.sync.orchestrator import SyncOrchestrator
from app.core.config import settings
from app.domain.schemas.user import CurrentUserResponse


router = APIRouter(prefix="/auth")
logger = logging.getLogger(__name__)


def _build_state_serializer() -> URLSafeSerializer:
    return URLSafeSerializer(settings.session_secret_key, salt="strava-oauth-state")


@router.get("/strava/login")
def start_strava_login(
    request: Request,
    strava_oauth_service: StravaOAuthService = Depends(StravaOAuthService),
) -> dict[str, str]:
    state = _build_state_serializer().dumps({"client": request.client.host if request.client else "unknown"})
    request.session["oauth_state"] = state
    logger.info(
        "Starting Strava OAuth login.",
        extra={"client.address": request.client.host if request.client else "unknown"},
    )
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
        logger.error("Rejected Strava OAuth callback because state did not match.")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state.")

    try:
        _build_state_serializer().loads(state)
    except BadSignature as exc:
        logger.error("Rejected Strava OAuth callback because state signature was invalid.")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state.") from exc

    logger.info("Handling Strava OAuth callback.")
    authenticated_user = strava_oauth_service.authenticate_from_code(code)
    if authenticated_user.is_new_user:
        logger.info("Queueing first import after new user login.", extra={"user.id": authenticated_user.id})
        sync_orchestrator.enqueue_first_import_if_needed(authenticated_user.id)
    request.session["user"] = {
        "id": authenticated_user.id,
        "strava_athlete_id": authenticated_user.strava_athlete_id,
        "display_name": authenticated_user.display_name,
        "profile_picture_url": authenticated_user.profile_picture_url,
    }
    request.session.pop("oauth_state", None)
    logger.info("Completed Strava OAuth callback.", extra={"user.id": authenticated_user.id})

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
    session_user = request.session.get("user") or {}
    logger.info("Logging out current session.", extra={"user.id": session_user.get("id")})
    request.session.clear()
