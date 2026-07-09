from __future__ import annotations

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)


class UserLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str


class WatchlistRequest(BaseModel):
    codes: list[str] = Field(default_factory=list)


class WatchlistResponse(BaseModel):
    items: list[dict[str, str]]
