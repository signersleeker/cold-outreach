from collections.abc import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine, _SessionLocal
    if _engine is None:
        _engine = create_engine(get_settings().sqlalchemy_database_url(), pool_pre_ping=True)
        _SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)
    return _engine


def SessionLocal() -> Session:
    get_engine()
    assert _SessionLocal is not None
    return _SessionLocal()


def reset_engine() -> None:
    """Clear the cached engine after a settings reload (CLI dotenv, tests)."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def import_all_models() -> None:
    """Import every slice that owns a table so Base.metadata is complete.

    Needed by create_all (seed script, tests). Kept here so there is exactly one
    list to update when a slice gains a table.
    """
    from app.app_settings import app_setting  # noqa: F401
    from app.contacts import contact  # noqa: F401
    from app.gmail import oauth_token  # noqa: F401
    from app.sends.models import daily_counter, send_event  # noqa: F401
    from app.suppressions import suppression  # noqa: F401
    from app.templates import template  # noqa: F401
