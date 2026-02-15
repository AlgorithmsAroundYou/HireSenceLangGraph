from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.api import (
    ChangePasswordRequest,
    ChangePasswordResponse,
    ProfileCreateRequest,
    ProfileUpdateRequest,
    ProfileResponse,
)
from app.models.user import User


USER_NOT_FOUND_DETAIL = "User not found"
INVALID_CURRENT_PASSWORD_DETAIL = "Current password is incorrect"


def _to_profile_response(user: User) -> ProfileResponse:
    return ProfileResponse(
        id=user.id,
        user_name=user.user_name,
        full_name=user.full_name,
        email=user.email,
        role=user.role,
        is_active=bool(user.is_active),
        is_email_verified=bool(user.is_email_verified),
        last_login_at=user.last_login_at.isoformat() if user.last_login_at else None,
        last_login_ip=user.last_login_ip,
        created_at=user.created_at.isoformat() if user.created_at else None,
        updated_at=user.updated_at.isoformat() if user.updated_at else None,
    )


def create_profile(db: Session, payload: ProfileCreateRequest) -> ProfileResponse:
    existing_user = db.query(User).filter(User.user_name == payload.user_name).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        )

    if payload.email:
        existing_email = db.query(User).filter(User.email == payload.email).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already exists",
            )

    now = datetime.now(timezone.utc)
    user = User(
        user_name=payload.user_name,
        full_name=payload.full_name,
        email=payload.email,
        password_hash=payload.password,
        role="employee",
        is_active=True,
        is_email_verified=False,
        created_at=now,
        updated_at=now,
    )

    db.add(user)
    db.commit()
    db.refresh(user)
    return _to_profile_response(user)


def list_profiles(db: Session) -> list[ProfileResponse]:
    users = db.query(User).order_by(User.id.asc()).all()
    return [_to_profile_response(user) for user in users]


def _find_user(db: Session, user_key: str) -> User | None:
    user = db.query(User).filter(User.user_name == user_key).first()
    if user:
        return user

    if user_key.isdigit():
        return db.query(User).filter(User.id == int(user_key)).first()

    return None


def get_profile_by_id(db: Session, user_key: str) -> ProfileResponse:
    user = _find_user(db, user_key)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=USER_NOT_FOUND_DETAIL,
        )
    return _to_profile_response(user)


def update_profile(db: Session, user_key: str, payload: ProfileUpdateRequest) -> ProfileResponse:
    user = _find_user(db, user_key)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=USER_NOT_FOUND_DETAIL,
        )

    if payload.user_name and payload.user_name != user.user_name:
        exists = db.query(User).filter(User.user_name == payload.user_name).first()
        if exists:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already exists",
            )
        user.user_name = payload.user_name

    if payload.email is not None and payload.email != user.email:
        exists = db.query(User).filter(User.email == payload.email).first()
        if exists:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already exists",
            )
        user.email = payload.email

    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.password is not None:
        user.password_hash = payload.password
    if payload.role is not None:
        user.role = payload.role
    if payload.is_active is not None:
        user.is_active = payload.is_active

    user.updated_at = datetime.now(timezone.utc)
    db.add(user)
    db.commit()
    db.refresh(user)
    return _to_profile_response(user)


def delete_profile(db: Session, user_key: str) -> None:
    user = _find_user(db, user_key)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=USER_NOT_FOUND_DETAIL,
        )

    db.delete(user)
    db.commit()


def change_password(
    db: Session,
    current_user_name: str,
    payload: ChangePasswordRequest,
) -> ChangePasswordResponse:
    user = db.query(User).filter(User.user_name == current_user_name).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=USER_NOT_FOUND_DETAIL,
        )

    if user.password_hash != payload.current_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=INVALID_CURRENT_PASSWORD_DETAIL,
        )

    user.password_hash = payload.new_password
    user.updated_at = datetime.now(timezone.utc)

    db.add(user)
    db.commit()

    return ChangePasswordResponse(
        success=True,
        message="Password changed successfully",
    )
