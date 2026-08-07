"""Database engine/session setup, shared across the whole app."""

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings

# `pool_pre_ping=True` makes SQLAlchemy test each pooled connection with a lightweight query
# before reusing it, so a connection that went stale (e.g. Postgres container restarted) is
# transparently replaced instead of raising on the next request.
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    connect_args={"prepare_threshold": None},
)

# Factory for new Session objects. `autoflush=False`/`autocommit=False` means changes are only
# sent to the DB on an explicit `.flush()`/`.commit()`, giving routers full control over when
# writes happen.
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Common base class every ORM model (app/models.py) inherits from."""

    pass


def get_db():
    """FastAPI dependency that yields one DB session per request and always closes it
    afterwards, even if the request handler raises."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
