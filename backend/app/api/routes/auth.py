import logging

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status

from app.application.auth.current_user import CurrentUserService
from app.application.auth.credentials import IntervalsCredentialService
from app.application.sync.orchestrator import SyncOrchestrator
from app.core.logging import set_log_user_name
from app.domain.schemas.auth import (
    IntervalsCredentialStateResponse,
    StartIntervalsLoginRequest,
    StartIntervalsLoginResponse,
)
from app.domain.schemas.user import CurrentUserResponse


router = APIRouter(prefix="/auth")
logger = logging.getLogger(__name__)


@router.get("/intervals/credentials", response_model=IntervalsCredentialStateResponse)
def get_intervals_landing_credentials(
    request: Request,
    intervals_credential_service: IntervalsCredentialService = Depends(IntervalsCredentialService),
) -> IntervalsCredentialStateResponse:
    remembered_user_id = request.session.get("remembered_user_id")
    return intervals_credential_service.get_landing_credential_state(remembered_user_id)


@router.post("/intervals/login", response_model=StartIntervalsLoginResponse)
def start_intervals_login(
    request: Request,
    payload: StartIntervalsLoginRequest = Body(...),
    intervals_credential_service: IntervalsCredentialService = Depends(IntervalsCredentialService),
    sync_orchestrator: SyncOrchestrator = Depends(SyncOrchestrator),
) -> StartIntervalsLoginResponse:
    authenticated_user = intervals_credential_service.authenticate_with_credentials(
        athlete_id=payload.athlete_id,
        api_key=payload.api_key,
        use_saved_credentials=payload.use_saved_credentials,
        remembered_user_id=request.session.get("remembered_user_id"),
    )
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
    set_log_user_name(authenticated_user.display_name)
    logger.info("Completed Intervals.icu credential login.", extra={"user.id": authenticated_user.id})
    return StartIntervalsLoginResponse(user_id=authenticated_user.id, is_new_user=authenticated_user.is_new_user)


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
