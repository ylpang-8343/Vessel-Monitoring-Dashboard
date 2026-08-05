"""FastAPI application entry point: wires up routers, auth gating, CORS, and startup/shutdown.

Run with `uvicorn app.main:app` (see README.md).
"""

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import Base, SessionLocal, engine
from app.dependencies import get_current_user, require_admin
from app.models import SourceKind, TrackingSource
from app.routers import auth, bulk_upload, history, notifications, reports, tracking_sources, users, vessels
from app.services import report_worker
from app.services.tracking_worker import start_scheduler, stop_scheduler

# adapter_key="mock" is the only one actually wired up to run (see sources/mock_adapter.py).
# The real vessel-tracking sites are catalogued per Section 3.9 but marked "unavailable" -
# no credentials/API access, see README.md - so enabling them here has no polling effect;
# the frontend Settings screen labels them "Not yet connected" accordingly.
SEED_SOURCES = [
    ("Mock Tracking Feed", "internal://mock", "mock", True),
    ("MarineTraffic", "https://www.marinetraffic.com/en/ais/home/centerx:-12.0/centery:25.0/zoom:4", "unavailable", False),
    ("VesselFinder", "https://www.vesselfinder.com/", "unavailable", False),
    ("Polestar GMDA", "https://mda-gov.polestarglobal.com/gmap/asset-search", "unavailable", False),
]


def _seed_tracking_sources() -> None:
    """Insert the default tracking-source catalogue on startup if it isn't already there
    (matched by name), so a fresh database always has something to show under Settings →
    Tracking Sources without requiring manual setup. Safe to call on every startup - existing
    rows (including any an admin has since edited) are left untouched."""
    db = SessionLocal()
    try:
        for name, url, adapter_key, enabled in SEED_SOURCES:
            if not db.query(TrackingSource).filter(TrackingSource.name == name).first():
                db.add(
                    TrackingSource(
                        name=name, url=url, kind=SourceKind.VESSEL, adapter_key=adapter_key, enabled=enabled
                    )
                )
        db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Runs once at startup (before the app accepts requests) and once at shutdown. Creates any
    missing tables, seeds the tracking-source catalogue, and starts/stops the two background
    schedulers: tracking-poll (services/tracking_worker.py) and the hourly daily-report check
    (services/report_worker.py)."""
    Base.metadata.create_all(bind=engine)
    _seed_tracking_sources()
    start_scheduler()
    report_worker.start_scheduler()
    yield
    stop_scheduler()
    report_worker.stop_scheduler()


app = FastAPI(title="Vessel Monitoring Dashboard API", lifespan=lifespan)

# Credentialed CORS (cookies sent cross-origin between the :3000 frontend and this :8000 API)
# requires an explicit origin list - "*" is not allowed together with allow_credentials=True.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth endpoints themselves must stay unauthenticated (you can't require a login to log in);
# the users-management and notifications endpoints enforce admin access internally via each
# route's own `Depends(require_admin)` in routers/users.py and routers/notifications.py.
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(notifications.router)

# Whole app requires login; Settings/tracking-source management additionally requires admin
# (Section 3.9 - "Admin users can add, edit, and remove vessel tracking website sources").
# Applying the dependency at include_router() level (rather than per-route) guarantees every
# current and future route on these routers is covered automatically.
app.include_router(vessels.router, dependencies=[Depends(get_current_user)])
app.include_router(history.router, dependencies=[Depends(get_current_user)])
app.include_router(bulk_upload.router, dependencies=[Depends(get_current_user)])
app.include_router(reports.router, dependencies=[Depends(get_current_user)])
app.include_router(tracking_sources.router, dependencies=[Depends(require_admin)])


@app.get("/api/health")
def health():
    """Trivial liveness check - not gated by auth, used for local `curl` sanity checks and
    could back a container/orchestrator health probe later."""
    return {"status": "ok"}
