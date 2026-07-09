from __future__ import annotations

from sqlalchemy.orm import Session

from backend.services.security import hash_password, verify_password
from data.providers.akshare_provider import fetch_stock_names
from data.repositories.user_repository import User, Watchlist, WatchlistStock


def get_user_by_username(db: Session, username: str) -> User | None:
    return db.query(User).filter(User.username == username).first()


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def create_user(db: Session, username: str, password: str) -> User:
    user = User(username=username, password_hash=hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)
    default_watchlist = Watchlist(user_id=user.id, name="默认股票池")
    db.add(default_watchlist)
    db.commit()
    return user


def authenticate_user(db: Session, username: str, password: str) -> User | None:
    user = get_user_by_username(db, username)
    if not user or not verify_password(password, user.password_hash):
        return None
    return user


def get_default_watchlist_codes(db: Session, user_id: int) -> list[str]:
    watchlist = _get_or_create_default_watchlist(db, user_id)
    rows = db.query(WatchlistStock).filter(WatchlistStock.watchlist_id == watchlist.id).order_by(WatchlistStock.id).all()
    return [row.stock_code for row in rows]


def save_default_watchlist_codes(db: Session, user_id: int, codes: list[str]) -> list[dict[str, str]]:
    watchlist = _get_or_create_default_watchlist(db, user_id)
    db.query(WatchlistStock).filter(WatchlistStock.watchlist_id == watchlist.id).delete()
    names = fetch_stock_names(codes)
    for code in codes:
        db.add(WatchlistStock(watchlist_id=watchlist.id, stock_code=code, stock_name=names.get(code, "名称待获取")))
    db.commit()
    return [{"股票代码": code, "股票名称": names.get(code, "名称待获取")} for code in codes]


def get_default_watchlist_items(db: Session, user_id: int) -> list[dict[str, str]]:
    watchlist = _get_or_create_default_watchlist(db, user_id)
    rows = db.query(WatchlistStock).filter(WatchlistStock.watchlist_id == watchlist.id).order_by(WatchlistStock.id).all()
    return [{"股票代码": row.stock_code, "股票名称": row.stock_name} for row in rows]


def _get_or_create_default_watchlist(db: Session, user_id: int) -> Watchlist:
    watchlist = db.query(Watchlist).filter(Watchlist.user_id == user_id).order_by(Watchlist.id).first()
    if watchlist:
        return watchlist
    watchlist = Watchlist(user_id=user_id, name="默认股票池")
    db.add(watchlist)
    db.commit()
    db.refresh(watchlist)
    return watchlist
