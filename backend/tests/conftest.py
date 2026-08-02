import os

os.environ["DATABASE_URL"] = "sqlite:///./test_vessel_monitoring.db"

import pytest

from app.db import Base, SessionLocal, engine


@pytest.fixture(autouse=True)
def _clean_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def _seed_mock_source(_clean_db):
    # run_tracking_poll() only polls when an enabled "mock" TrackingSource exists (Section
    # 3.9 gating) - seed one by default so existing tracking-worker tests keep working;
    # tests that specifically exercise the disabled case delete/disable it themselves.
    from app.models import SourceKind, TrackingSource

    db = SessionLocal()
    try:
        db.add(
            TrackingSource(
                name="Mock Tracking Feed",
                url="internal://mock",
                kind=SourceKind.VESSEL,
                adapter_key="mock",
                enabled=True,
            )
        )
        db.commit()
    finally:
        db.close()


@pytest.fixture(autouse=True)
def _no_background_scheduler(monkeypatch):
    # Keep API tests deterministic: the real tracking worker runs on a background
    # thread against a live poll interval, which isn't relevant to these tests.
    monkeypatch.setattr("app.main.start_scheduler", lambda: None)
    monkeypatch.setattr("app.main.stop_scheduler", lambda: None)


@pytest.fixture
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
