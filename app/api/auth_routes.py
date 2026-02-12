from fastapi import APIRouter, Depends, HTTPException, status

from app.models.user import User
from app.models.api import LoginRequest, LoginResponse
from app.services.auth_service import get_db, create_access_token, get_current_user


router = APIRouter()


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

    access_token = create_access_token(data={"sub": user.user_name})

    return LoginResponse(
        success=True,
        message="Login successful",
        token=access_token,
    )
