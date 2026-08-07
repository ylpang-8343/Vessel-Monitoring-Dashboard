"""FastAPI application entry point: wires up routers, auth gating, CORS, and startup/shutdown.

Run with `uvicorn app.main:app` (see README.md).
"""

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import Base, SessionLocal, engine
from app.dependencies import get_current_user, require_admin
from app.models import SourceKind, TrackingSource
from app.routers import (
    auth,
    bookings,
    bulk_upload,
    history,
    insights,
    notifications,
    reports,
    tracking_sources,
    users,
    vessels,
)
from app.services import booking_worker, report_worker
from app.services.tracking_worker import start_scheduler, stop_scheduler

# adapter_key="mock" is the only vessel source actually wired up to run (see
# sources/mock_adapter.py). The real vessel-tracking sites are catalogued per Section 3.9 but
# marked "unavailable" - no credentials/API access, see README.md - so enabling them here has no
# polling effect; the frontend Settings screen labels them "Not yet connected" accordingly.
SEED_VESSEL_SOURCES = [
    ("Mock Tracking Feed", "internal://mock", "mock", True),
    ("MarineTraffic", "https://www.marinetraffic.com/en/ais/home/centerx:-12.0/centery:25.0/zoom:4", "unavailable", False),
    ("VesselFinder", "https://www.vesselfinder.com/", "unavailable", False),
    ("Polestar GMDA", "https://mda-gov.polestarglobal.com/gmap/asset-search", "unavailable", False),
]

# Same idea for the Container/Booking Tracking module (Section 4/8.1) - adapter_key="mock_booking"
# is the only one actually wired up (see sources/mock_booking_adapter.py); the five real carrier
# portals are catalogued as "unavailable" for the same no-credentials-yet reason as the vessel
# sources above. Reuses the exact same TrackingSource table/admin screen (kind=CONTAINER) rather
# than a second one, per Section 4's "can share the same... patterns as the vessel dashboard".
SEED_CONTAINER_SOURCES = [
    ("Mock Booking Feed", "internal://mock-booking", "mock_booking", True),
    ("ONE eCommerce", "https://ecomm.one-line.com/one-ecom/manage-shipment/cargo-tracking", "unavailable", False),
    ("Maersk", "https://www.maersk.com/tracking/", "unavailable", False),
    ("MSC", "https://www.msc.com/en/track-a-shipment", "unavailable", False),
    ("CMA CGM", "https://www.cma-cgm.com/eBusiness/Tracking", "unavailable", False),
    ("InterAsia", "https://www.interasia.cc/Service/Form?servicetype=1", "unavailable", False),
]


def _seed_tracking_sources() -> None:
    """Insert the default tracking-source catalogue on startup if it isn't already there
    (matched by name), so a fresh database always has something to show under Settings →
    Tracking Sources without requiring manual setup. Safe to call on every startup - existing
    rows (including any an admin has since edited) are left untouched."""
    db = SessionLocal()
    try:
        for name, url, adapter_key, enabled in SEED_VESSEL_SOURCES:
            if not db.query(TrackingSource).filter(TrackingSource.name == name).first():
                db.add(
                    TrackingSource(
                        name=name, url=url, kind=SourceKind.VESSEL, adapter_key=adapter_key, enabled=enabled
                    )
                )
        for name, url, adapter_key, enabled in SEED_CONTAINER_SOURCES:
            if not db.query(TrackingSource).filter(TrackingSource.name == name).first():
                db.add(
                    TrackingSource(
                        name=name, url=url, kind=SourceKind.CONTAINER, adapter_key=adapter_key, enabled=enabled
                    )
                )
        db.commit()
    finally:
        db.close()


def _check_cookie_config() -> None:
    """Warn loudly at startup about a cookie configuration browsers will silently reject.

    `SameSite=None` without `Secure` is dropped by every modern browser: the login response
    looks completely healthy (200, Set-Cookie present), the cookie is simply never stored, and
    every subsequent request reads as logged-out. Nothing in the app can detect that at runtime,
    so the only place to catch it is here, against the configuration itself.
    """
    if settings.cookie_samesite == "none" and not settings.cookie_secure:
        logging.getLogger("uvicorn.error").error(
            "COOKIE CONFIG ERROR: cookie_samesite='none' requires cookie_secure=true — browsers "
            "silently drop a SameSite=None cookie that isn't Secure, so login will appear to "
            "succeed but every request will read as logged-out. Set COOKIE_SECURE=true (needs "
            "HTTPS), or use COOKIE_SAMESITE=lax if the frontend and backend share a site."
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Runs once at startup (before the app accepts requests) and once at shutdown. Creates any
    missing tables, seeds the tracking-source catalogue, and starts/stops the three background
    schedulers: vessel tracking-poll (services/tracking_worker.py), booking/container polling
    (services/booking_worker.py), and the hourly daily-report check (services/report_worker.py)."""
    Base.metadata.create_all(bind=engine)
    _check_cookie_config()
    _seed_tracking_sources()
    start_scheduler()
    booking_worker.start_scheduler()
    report_worker.start_scheduler()
    yield
    stop_scheduler()
    booking_worker.stop_scheduler()
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
# Container/Booking Tracking module (Section 4) - same access level as vessels: any logged-in
# user, not admin-only.
app.include_router(bookings.router, dependencies=[Depends(get_current_user)])
# Phase 6 (Section 7): AI voyage summaries and exception alerts. Operational views, so the same
# any-logged-in-user gating as the dashboard rather than admin-only.
app.include_router(insights.router, dependencies=[Depends(get_current_user)])
app.include_router(tracking_sources.router, dependencies=[Depends(require_admin)])


@app.get("/api/health")
def health():
    """Trivial liveness check - not gated by auth, used for local `curl` sanity checks and
    could back a container/orchestrator health probe later."""
    return {"status": "ok"}
