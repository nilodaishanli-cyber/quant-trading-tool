from __future__ import annotations

from sqlalchemy import create_engine
from collections.abc import Generator

from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from utils.config import settings


engine = create_engine(settings.database_url, connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def init_db() -> None:
    import data.repositories.user_repository  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
