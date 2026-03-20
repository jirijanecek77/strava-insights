import logging

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse

from app.application.auth.current_user import CurrentUserService
from app.application.auth.oauth import StravaOAuthService
from app.application.sync.orchestrator import SyncOrchestrator
from app.core.config import settings
from app.domain.schemas.auth import StartStravaLoginRequest, StartStravaLoginResponse, StravaCredentialStateResponse
from app.domain.schemas.user import CurrentUserResponse


router = APIRouter(prefix="/auth")
logger = logging.getLogger(__name__)


@router.get("/strava/credentials", response_model=StravaCredentialStateResponse)
def get_strava_landing_credentials(
    request: Request,
    strava_oauth_service: StravaOAuthService = Depends(StravaOAuthService),
) -> StravaCredentialStateResponse:
    remembered_user_id = request.session.get("remembered_user_id")
    return strava_oauth_service.get_landing_credential_state(remembered_user_id)


@router.post("/strava/login", response_model=StartStravaLoginResponse)
def start_strava_login(
    request: Request,
    payload: StartStravaLoginRequest = Body(...),
    strava_oauth_service: StravaOAuthService = Depends(StravaOAuthService),
) -> StartStravaLoginResponse:
    authorization_url = strava_oauth_service.start_login(
        client_id=payload.client_id,
        client_secret=payload.client_secret,
        use_saved_credentials=payload.use_saved_credentials,
        remembered_user_id=request.session.get("remembered_user_id"),
        request_client=request.client.host if request.client else "unknown",
    )
    return StartStravaLoginResponse(authorization_url=authorization_url)


@router.get("/strava/callback", response_class=RedirectResponse, status_code=status.HTTP_302_FOUND)
def strava_callback(
    request: Request,
    code: str = Query(...),
    state: str = Query(...),
    strava_oauth_service: StravaOAuthService = Depends(StravaOAuthService),
    sync_orchestrator: SyncOrchestrator = Depends(SyncOrchestrator),
) -> RedirectResponse:
    logger.info("Handling Strava OAuth callback.")
    authenticated_user = strava_oauth_service.authenticate_from_code(code, state)
    if authenticated_user.is_new_user:
        logger.info("Queueing first import after new user login.", extra={"user.id": authenticated_user.id})
        sync_orchestrator.enqueue_first_import_if_needed(authenticated_user.id)
    request.session["user"] = {
        "id": authenticated_user.id,
        "strava_athlete_id": authenticated_user.strava_athlete_id,
        "display_name": authenticated_user.display_name,
        "profile_picture_url": authenticated_user.profile_picture_url,
    }
    request.session["remembered_user_id"] = authenticated_user.id
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
    if session_user.get("id") is not None:
        request.session["remembered_user_id"] = session_user["id"]
