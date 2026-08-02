from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import Base, SessionLocal, engine
from app.models import SourceKind, TrackingSource
from app.routers import bulk_upload, history, tracking_sources, vessels
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
    Base.metadata.create_all(bind=engine)
    _seed_tracking_sources()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="Vessel Monitoring Dashboard API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(vessels.router)
app.include_router(history.router)
app.include_router(bulk_upload.router)
app.include_router(tracking_sources.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
