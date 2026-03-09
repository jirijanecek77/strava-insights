from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.application.auth.current_user import CurrentUserService
from app.application.sync.dto import CreatedSyncJob
from app.application.sync.orchestrator import SyncOrchestrator
from app.application.sync.status import SyncStatusService
from app.domain.schemas.sync import SyncStatusResponse


router = APIRouter(prefix="/sync")


@router.get("/status", response_model=SyncStatusResponse)
def get_sync_status(
    request: Request,
    current_user_service: CurrentUserService = Depends(CurrentUserService),
    sync_status_service: SyncStatusService = Depends(SyncStatusService),
) -> SyncStatusResponse:
    user = current_user_service.get_current_user(request)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )

    return sync_status_service.get_status_for_user(user.id)


@router.post("/refresh", response_model=CreatedSyncJob, status_code=status.HTTP_202_ACCEPTED)
def trigger_incremental_sync(
    request: Request,
    current_user_service: CurrentUserService = Depends(CurrentUserService),
    sync_orchestrator: SyncOrchestrator = Depends(SyncOrchestrator),
) -> CreatedSyncJob:
    user = current_user_service.get_current_user(request)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )

    return sync_orchestrator.enqueue_incremental_sync(user.id)
