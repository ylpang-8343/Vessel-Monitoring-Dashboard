# Vessel Monitoring Dashboard — Phases 1-4

Implements Phases 1-4 of `Vessel_Monitoring_Dashboard_Proposal_Final.pdf` (Section 9):

- **Phase 1**: vessel registration, manual + bulk add (Excel/CSV/PDF with AI-extraction review),
  automated tracking via a pluggable source adapter (mock adapter for now — see below), dashboard
  view, history timeline, and latest-status display.
- **Phase 2**: arrived-at-destination auto-archive lifecycle (Section 3.7, configurable retention
  window), manual archive/remove actions (Section 3.8), and admin tracking-source management
  (Section 3.9) at `/settings`.
- **Phase 3**: dashboard search (6.A), status filter chips (6.D: At Sea / At Port / ETA to
  Destination / Arrived at Destination), status colour coding (6.E), and a live Map View (6.B) at
  `/map` using react-leaflet + OpenStreetMap tiles, plus search on the Settings → Tracking Sources
  and Settings → Users tables.
- **Phase 4**: email + Microsoft Teams notifications (6.C) on vessel arrival/departure/arrival-at-
  destination, configured at Settings → Notifications; a Reports page (`/reports`, Section 7) with
  Active/ETA-to-Destination/Arrived-at-Destination vessel lists and Excel/PDF export; a daily
  report on an admin-configurable schedule, delivered through the same two channels. See "Phase 4:
  notifications and reports" below for what's deliberately out of scope and why.
- **Auth**: email/password login and registration, plus optional "Sign in with Microsoft", gating
  the whole app. See "First-time setup" below — registering (by either method) never grants admin,
  so there's a required bootstrap step. See "Sign in with Microsoft: setup" for enabling the
  Microsoft option.

Not yet built (see `Vessel_Monitoring_Dashboard_Proposal_Final.pdf` Section 9, Phase 5): the
Container/Booking Tracking module.

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

Open http://localhost:3000 — you'll land on `/login`. See "First-time setup" below before you
can reach Settings. The FastAPI backend runs at http://localhost:8000 (docs at `/docs`).

## First-time setup: creating the first admin

Registering through the web app (`/register`) always creates a regular `user` account — there is
deliberately no path in the app itself to become admin, so there's no self-promotion hole. To get
your first admin:

```bash
# 1. Register a normal account at http://localhost:3000/register

# 2. Promote it from a terminal, with the backend venv active
cd backend
.venv\Scripts\activate
python -m app.cli promote-admin you@example.com
```

Log out and back in (or just refresh) and you'll see the Settings link. From then on, admins can
promote or demote other users from Settings → Users — the CLI command is only for bootstrapping
the very first one. The last remaining admin can't be demoted (by themselves or anyone else),
since that would leave nobody able to manage roles at all.

## Sign in with Microsoft: setup

Off by default - the button doesn't even appear on `/login`/`/register` until it's configured
(`GET /api/auth/microsoft/status` reports whether it is). To enable it:

1. Register an app at https://portal.azure.com (Entra ID → App registrations → New registration).
   Add a Redirect URI of type "Web": `http://localhost:8000/api/auth/microsoft/callback` (or your
   deployed backend's equivalent).
2. Under "Certificates & secrets", create a client secret.
3. Set in `backend/.env` (placeholders already present in `.env.example`, empty by default):
   ```
   MICROSOFT_CLIENT_ID=<application (client) id>
   MICROSOFT_CLIENT_SECRET=<the client secret value>
   ```
   `MICROSOFT_TENANT_ID` defaults to `common` (personal *and* any work/school account can sign
   in) - set it to a specific tenant id to restrict sign-in to one organisation.
4. Restart the backend. The button now appears.

However someone signs in - password or Microsoft - registration/first-sign-in always creates a
`user`-role account, never admin (see "First-time setup" above); if the email matches an existing
account, Microsoft sign-in links to it instead of creating a duplicate, and Settings → Users shows
a "Microsoft" badge for any account that can currently sign in that way (regardless of which
method originally created it).

## Phase 4: notifications and reports

Settings → Notifications (admin-only) has three independent cards:

- **Email** — SMTP host/port/username/password, a from-address, and a comma-separated recipient
  list. Standard `smtplib` + STARTTLS on whatever port you configure (587 is the common default) —
  point it at a real provider (Gmail, Office 365, SendGrid, etc.) or a local debug SMTP server for
  testing (e.g. `pip install aiosmtpd && python -m aiosmtpd -n -l localhost:1025`, though note a
  bare debug server like that typically doesn't support STARTTLS, so delivery will correctly show
  as `failed` with a clear reason rather than `sent` — that's the error-handling path working, not
  a bug).
- **Microsoft Teams** — a single incoming-webhook URL. Any endpoint that accepts a `POST` with a
  `{"text": "..."}` JSON body works, including a real Teams incoming webhook.
- **Daily Report** — an on/off toggle and a UTC hour; checked once an hour by a background job
  (`backend/app/services/report_worker.py`), so it fires within the hour it's due rather than at
  the exact minute.

Both "Send Test Notification" and "Send Daily Report Now" trigger immediately, useful for
confirming a channel actually works without waiting for a real vessel event or the scheduled hour.
Every attempt (sent/skipped/failed) is logged in the "Recent Activity" table below, including
*why* something was skipped or failed — nothing fails silently.

**Deliberately not implemented**, matching Section 3.10's reasoning for the dashboard's own status
values: ETA-change and delay notifications/reports, and WhatsApp (which the proposal's own Figure
5 labels "planned for phase 2 rollout"). None of these have real underlying data to back them —
see `backend/app/services/notification_service.py`'s and `report_service.py`'s module docstrings.

Reports (`/reports`, reachable by any logged-in user, not just admins) covers Active Vessels, ETA
to Destination, and Arrived at Destination, each exportable to Excel or PDF from the same page.

## Tests

```bash
cd backend
.venv\Scripts\activate
pytest
```

## Notes

- Tables are created automatically on backend startup (`Base.metadata.create_all`) — there's no
  migration tool wired up yet. This only *adds* new tables/columns, it doesn't alter existing
  ones, so a schema change (like Phase 2's new `archived_at` column, or the Microsoft sign-in
  work's `users.password_hash` becoming nullable) on a database that already has the old shape
  will error on first query. If you hit `UndefinedColumn`/`NOT NULL constraint` errors after
  pulling schema changes, reset the local dev volume: `docker compose down -v && docker compose
  up -d`. Add Alembic before this touches real data you care about preserving across schema
  changes.
- The mock tracking worker advances each vessel's simulated voyage by one step every poll tick
  (`TRACKING_POLL_INTERVAL_SECONDS` in `.env`, default 300s/5min to match the dashboard's
  "auto-refreshed every 5 minutes"). Lower it in `.env` for faster manual testing. It only runs
  while the "Mock Tracking Feed" source is enabled in Settings (`/settings`).
- Vessels whose latest event is "Arrived at Destination" auto-archive after
  `ARRIVED_RETENTION_DAYS` (`.env`, default 10) — checked on every tracking-poll tick. Archiving
  (auto or manual) is one-way for now: archived vessels move to the dashboard's Archived tab with
  full history intact, but there's no "unarchive" — re-register the vessel to resume tracking.
- Map View (`/map`) only plots vessels whose current location is a recognised port/sea-region —
  see `frontend/lib/portCoordinates.ts`. A vessel with an unrecognised location (e.g. a free-text
  destination the mock adapter never emits) is listed separately below the map instead of guessed
  at. Requires outbound access to `tile.openstreetmap.org` to load map tiles.
- With `TRACKING_POLL_INTERVAL_SECONDS` lowered for testing, every enabled vessel produces a
  notification roughly every tick - the "Recent Activity" log fills up fast and the daily report
  you just sent can scroll out of the visible list within seconds. At the default 300s/5min
  interval this isn't an issue; it's purely an artefact of speeding up the demo.
