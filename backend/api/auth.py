from __future__ import annotations

from typing import Union

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.api.deps import get_current_user
from backend.schemas.user import TokenResponse, UserCreate, UserLogin
from backend.services.security import create_access_token
from backend.services.user_service import authenticate_user, create_user, get_user_by_username
from data.database import get_db
from data.repositories.user_repository import User


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
def register(payload: UserCreate, db: Session = Depends(get_db)) -> TokenResponse:
    if get_user_by_username(db, payload.username):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已存在")
    user = create_user(db, payload.username, payload.password)
    return TokenResponse(access_token=create_access_token(str(user.id)), username=user.username)


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)) -> TokenResponse:
    user = authenticate_user(db, payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    return TokenResponse(access_token=create_access_token(str(user.id)), username=user.username)


@router.get("/me")
def me(user: User = Depends(get_current_user)) -> dict[str, Union[str, int]]:
    return {"id": user.id, "username": user.username}
