from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime, timezone

from app.models.user import User
from app.models.api import LoginRequest, LoginResponse, SignupRequest, SignupResponse
from app.services.auth_service import get_db, create_access_token, get_current_user


router = APIRouter()


@router.post("/auth/signup", response_model=SignupResponse, status_code=status.HTTP_201_CREATED)
async def signup(request: SignupRequest, db=Depends(get_db)):
    from app.models.user import User as UserModel

    existing_user = db.query(UserModel).filter(UserModel.user_name == request.user_name).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        )

    if request.email:
        existing_email = db.query(UserModel).filter(UserModel.email == request.email).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already exists",
            )

    now = datetime.now(timezone.utc)
    user = UserModel(
        user_name=request.user_name,
        full_name=request.full_name,
        email=request.email,
        password_hash=request.password,
        role="employee",
        is_active=True,
        is_email_verified=False,
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    user_claims = {
        "id": user.id,
        "user_name": user.user_name,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "is_active": bool(user.is_active),
        "is_email_verified": bool(user.is_email_verified),
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        "last_login_ip": user.last_login_ip,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
    }

    access_token = create_access_token(
        data={
            "sub": user.user_name,
            "user": user_claims,
        }
    )

    return SignupResponse(
        success=True,
        message="Signup successful",
        token=access_token,
    )


@router.post("/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest, db=Depends(get_db)):
    from app.models.user import User as UserModel

    user = db.query(UserModel).filter(UserModel.user_name == request.user_name).first()

    if user is None or user.password_hash != request.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive",
        )

    user_claims = {
        "id": user.id,
        "user_name": user.user_name,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "is_active": bool(user.is_active),
        "is_email_verified": bool(user.is_email_verified),
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
        "last_login_ip": user.last_login_ip,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
    }

    access_token = create_access_token(
        data={
            "sub": user.user_name,
            "user": user_claims,
        }
    )

    return LoginResponse(
        success=True,
        message="Login successful",
        token=access_token,
    )
