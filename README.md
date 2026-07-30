# Vessel Monitoring Dashboard — Phase 1

Implements Phase 1 of `Vessel_Monitoring_Dashboard_Proposal_Final.pdf` (Section 9): vessel
registration, manual + bulk add (Excel/CSV/PDF with AI-extraction review), automated tracking via
a pluggable source adapter (mock adapter for now — see below), dashboard view, history timeline,
and latest-status display.

Not yet built (see `Vessel_Monitoring_Dashboard_Proposal_Final.pdf` Section 9, Phases 2-5):
arrived-at-destination auto-archiving, manual removal/archive UI, admin source management UI,
search/filters/map view, notifications/reports, and the Container/Booking Tracking module.

## Why tracking data is simulated

Section 3.3 of the proposal calls for polling MarineTraffic, VesselFinder, and Polestar GMDA.
None of these offer a public free API, and no credentials were available for this build. The
tracking worker (`backend/app/services/tracking_worker.py`) is built against a
`TrackingSourceAdapter` interface (`backend/app/sources/base.py`) with a `MockAdapter`
(`backend/app/sources/mock_adapter.py`) wired in for now, so the full pipeline — poll → status
engine → history → dashboard — works end-to-end. Swap in a real scraper/API client later by
implementing the same interface; nothing else needs to change.

## Prerequisites

- Docker Desktop (for PostgreSQL)
- Python 3.12+
- Node.js 20+
- An Anthropic API key if you want PDF bulk-upload extraction to work (Section 3.2). Without it,
  PDF upload returns a clear "unavailable" error; Excel/CSV upload works regardless.

## Running locally

```bash
# 1. Start Postgres
docker compose up -d

# 2. Backend
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
copy .env.example .env        # then fill in ANTHROPIC_API_KEY if you have one
uvicorn app.main:app --reload --port 8000

# 3. Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

Open http://localhost:3000. The FastAPI backend runs at http://localhost:8000 (docs at `/docs`).

## Tests

```bash
cd backend
.venv\Scripts\activate
pytest
```

## Notes

- Tables are created automatically on backend startup (`Base.metadata.create_all`) — there's no
  migration tool wired up yet (fine for Phase 1; add Alembic before this touches real data you
  care about preserving across schema changes).
- The mock tracking worker advances each vessel's simulated voyage by one step every poll tick
  (`TRACKING_POLL_INTERVAL_SECONDS` in `.env`, default 300s/5min to match the dashboard's
  "auto-refreshed every 5 minutes"). Lower it in `.env` for faster manual testing.
