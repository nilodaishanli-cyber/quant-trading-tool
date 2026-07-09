from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.api.deps import get_current_user
from backend.schemas.user import WatchlistRequest, WatchlistResponse
from backend.services.user_service import get_default_watchlist_items, save_default_watchlist_codes
from data.database import get_db
from data.repositories.user_repository import User
from utils.formatting import parse_stock_codes


router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


@router.get("", response_model=WatchlistResponse)
def get_watchlist(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> WatchlistResponse:
    return WatchlistResponse(items=get_default_watchlist_items(db, user.id))


@router.post("", response_model=WatchlistResponse)
def save_watchlist(
    payload: WatchlistRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WatchlistResponse:
    codes = parse_stock_codes("\n".join(payload.codes))
    return WatchlistResponse(items=save_default_watchlist_codes(db, user.id, codes))
