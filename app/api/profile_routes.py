from fastapi import APIRouter, Depends, status

from app.models.api import (
    ChangePasswordRequest,
    ChangePasswordResponse,
    ProfileCreateRequest,
    ProfileListResponse,
    ProfileResponse,
    ProfileUpdateRequest,
)
from app.models.user import User
from app.services.auth_service import get_current_user, get_db
from app.services.profile_service import (
    change_password as change_password_svc,
    create_profile as create_profile_svc,
    delete_profile as delete_profile_svc,
    get_profile_by_id as get_profile_by_id_svc,
    list_profiles as list_profiles_svc,
    update_profile as update_profile_svc,
)


router = APIRouter()


@router.post("/profile", response_model=ProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_profile(
    request: ProfileCreateRequest,
    db=Depends(get_db),
    user: User = Depends(get_current_user),
):
    return create_profile_svc(db, request)


@router.get("/profile", response_model=ProfileListResponse)
async def list_profiles(
    db=Depends(get_db),
    user: User = Depends(get_current_user),
):
    users = list_profiles_svc(db)
    return {"users": users}


@router.post("/profile/change-password", response_model=ChangePasswordResponse)
async def change_password(
    request: ChangePasswordRequest,
    db=Depends(get_db),
    user: User = Depends(get_current_user),
):
    return change_password_svc(db, user.user_name, request)


@router.get("/profile/{user_id}", response_model=ProfileResponse)
async def get_profile_by_id(
    user_id: str,
    db=Depends(get_db),
    user: User = Depends(get_current_user),
):
    return get_profile_by_id_svc(db, user_id)


@router.put("/profile/{user_id}", response_model=ProfileResponse)
async def update_profile(
    user_id: str,
    request: ProfileUpdateRequest,
    db=Depends(get_db),
    user: User = Depends(get_current_user),
):
    return update_profile_svc(db, user_id, request)


@router.delete("/profile/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_profile(
    user_id: str,
    db=Depends(get_db),
    user: User = Depends(get_current_user),
):
    delete_profile_svc(db, user_id)
    return None
