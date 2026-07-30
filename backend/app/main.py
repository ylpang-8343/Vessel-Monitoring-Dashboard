from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import Base, SessionLocal, engine
from app.models import SourceKind, TrackingSource
from app.routers import bulk_upload, history, vessels
from app.services.tracking_worker import start_scheduler, stop_scheduler

SEED_SOURCES = [
    ("MarineTraffic", "https://www.marinetraffic.com/en/ais/home/centerx:-12.0/centery:25.0/zoom:4"),
    ("VesselFinder", "https://www.vesselfinder.com/"),
    ("Polestar GMDA", "https://mda-gov.polestarglobal.com/gmap/asset-search"),
]


def _seed_tracking_sources() -> None:
    db = SessionLocal()
    try:
        for name, url in SEED_SOURCES:
            if not db.query(TrackingSource).filter(TrackingSource.name == name).first():
                db.add(TrackingSource(name=name, url=url, kind=SourceKind.VESSEL, adapter_key="mock", enabled=False))
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


@app.get("/api/health")
def health():
    return {"status": "ok"}
