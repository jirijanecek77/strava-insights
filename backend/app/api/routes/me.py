from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.application.auth.current_user import CurrentUserService
from app.api.dependencies import get_db_session
from app.domain.schemas.user import CurrentUserResponse, UpdateUserProfileRequest, UserProfileResponse
from app.infrastructure.repositories.user_profile_repository import UserProfileRepository


router = APIRouter()


@router.get("/me", response_model=CurrentUserResponse)
def get_current_user_profile(
    request: Request,
    current_user_service: CurrentUserService = Depends(CurrentUserService),
) -> CurrentUserResponse:
    user = current_user_service.get_current_user(request)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )

    return user


@router.get("/me/profile", response_model=UserProfileResponse)
def get_user_profile_details(
    request: Request,
    current_user_service: CurrentUserService = Depends(CurrentUserService),
    db_session: Session = Depends(get_db_session),
) -> UserProfileResponse:
    user = current_user_service.get_current_user(request)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )

    profile = UserProfileRepository(db_session).get_for_user(user.id)
    if profile is None:
        return UserProfileResponse()
    return UserProfileResponse.model_validate(profile)


@router.put("/me/profile", response_model=UserProfileResponse)
def update_user_profile_details(
    payload: UpdateUserProfileRequest,
    request: Request,
    current_user_service: CurrentUserService = Depends(CurrentUserService),
    db_session: Session = Depends(get_db_session),
) -> UserProfileResponse:
    user = current_user_service.get_current_user(request)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )

    profile = UserProfileRepository(db_session).upsert_for_user(
        user_id=user.id,
        aet_heart_rate_bpm=payload.aet_heart_rate_bpm,
        ant_heart_rate_bpm=payload.ant_heart_rate_bpm,
        aet_pace_min_per_km=payload.aet_pace_min_per_km,
        ant_pace_min_per_km=payload.ant_pace_min_per_km,
    )
    db_session.commit()
    return UserProfileResponse.model_validate(profile)
