import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.application.auth.current_user import CurrentUserService
from app.api.dependencies import get_db_session
from app.domain.schemas.user import CurrentUserResponse, UpdateUserProfileRequest, UserProfileResponse, UserThresholdProfileItem
from app.infrastructure.db.models.user import User
from app.infrastructure.repositories.user_profile_repository import UserProfileRepository
from app.infrastructure.repositories.user_repository import UserRepository


router = APIRouter()
logger = logging.getLogger(__name__)


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

    logger.info("Loading threshold profiles.", extra={"user.id": user.id})
    profiles = UserProfileRepository(db_session).list_for_user(user.id)
    if not profiles:
        return UserProfileResponse(items=[], current=None)
    return UserProfileResponse(
        items=[UserThresholdProfileItem.model_validate(profile) for profile in profiles],
        current=UserThresholdProfileItem.model_validate(profiles[0]),
    )


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

    logger.info(
        "Saving threshold profile snapshot.",
        extra={
            "user.id": user.id,
            "effective_from": payload.effective_from.isoformat(),
        },
    )
    user_repository = UserRepository(db_session)
    persisted_user = user_repository.get_by_id(user.id)
    if persisted_user is None:
        logger.warning("Creating missing persisted user from session before profile save.", extra={"user.id": user.id})
        user_repository.save(
            User(
                id=user.id,
                strava_athlete_id=user.strava_athlete_id,
                display_name=user.display_name,
                profile_picture_url=user.profile_picture_url,
                is_active=True,
            )
        )

    profile = UserProfileRepository(db_session).upsert_for_user(
        user_id=user.id,
        effective_from=payload.effective_from,
        aet_heart_rate_bpm=payload.aet_heart_rate_bpm,
        ant_heart_rate_bpm=payload.ant_heart_rate_bpm,
        aet_pace_min_per_km=payload.aet_pace_min_per_km,
        ant_pace_min_per_km=payload.ant_pace_min_per_km,
    )
    db_session.commit()
    profiles = UserProfileRepository(db_session).list_for_user(user.id)
    logger.info(
        "Saved threshold profile snapshot.",
        extra={
            "user.id": user.id,
            "effective_from": profile.effective_from.isoformat(),
            "profile_count": len(profiles),
        },
    )
    return UserProfileResponse(
        items=[UserThresholdProfileItem.model_validate(item) for item in profiles],
        current=UserThresholdProfileItem.model_validate(profile),
    )
