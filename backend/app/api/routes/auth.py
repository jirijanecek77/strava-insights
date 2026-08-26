from fastapi import APIRouter, Body, Depends, HTTPException, Request, status

from app.application.auth.credentials import GarminCredentialService
from app.application.auth.current_user import CurrentUserService
from app.application.auth.dto import GarminCredentials
from app.application.sync.orchestrator import SyncOrchestrator
from app.domain.schemas.auth import GarminCredentialStateResponse, StartGarminLoginRequest, StartGarminLoginResponse
from app.domain.schemas.user import CurrentUserResponse

router = APIRouter(prefix="/auth")


def _set_session(request: Request, user) -> None:
    request.session["user"] = {"id": user.id, "external_user_id": user.external_user_id, "display_name": user.display_name, "profile_picture_url": user.profile_picture_url}
    request.session["remembered_user_id"] = user.id


@router.get("/garmin/credentials", response_model=GarminCredentialStateResponse)
def credentials(request: Request, service: GarminCredentialService = Depends(GarminCredentialService)):
    return service.state(request.session.get("remembered_user_id"))


@router.post("/garmin/login", response_model=StartGarminLoginResponse)
def login(request: Request, payload: StartGarminLoginRequest = Body(...), service: GarminCredentialService = Depends(GarminCredentialService), sync_orchestrator: SyncOrchestrator = Depends(SyncOrchestrator)):
    remembered = request.session.get("remembered_user_id")
    user = service.authenticate_saved(remembered) if payload.use_saved_credentials and remembered else service.authenticate(GarminCredentials(payload.email or "", payload.password), remembered)
    _set_session(request, user)
    if user.is_new_user:
        sync_orchestrator.enqueue_first_import_if_needed(user.id)
    return StartGarminLoginResponse(user_id=user.id, is_new_user=user.is_new_user)


@router.get("/session", response_model=CurrentUserResponse)
def session(request: Request, current_user_service: CurrentUserService = Depends(CurrentUserService)) -> CurrentUserResponse:
    user = current_user_service.get_current_user(request)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")
    return CurrentUserResponse.model_validate(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request) -> None:
    remembered = (request.session.get("user") or {}).get("id")
    request.session.clear()
    if remembered is not None:
        request.session["remembered_user_id"] = remembered
