# Vessel Monitoring Dashboard — Phases 1-6

Implements all six phases of `Vessel_Monitoring_Dashboard_Proposal_Final.pdf` (Section 9):

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
- **Phase 5**: the Container/Booking Tracking module (Section 4) at `/containers` — its own
  Booking Confirmed → Loaded → In Transit → Discharged → Gate Out lifecycle, sourced from a
  simulated carrier-portal feed (see below) rather than vessel-position data, which is what lets
  it reliably distinguish loaded vs. discharged (Section 3.10). Structured the same way as the
  vessel dashboard on purpose — same search/filter/colour-coding/archive patterns, and the same
  Settings → Tracking Sources screen manages both vessel and carrier sources. See "Phase 5:
  Container/Booking Tracking" below for what's deliberately out of scope and why.
- **Phase 6**: the AI/insight features (Section 7) — an AI voyage summary on each vessel's history
  page, delay detection, a predictive ETA from the vessel's own completed voyages, exception
  alerts at `/exceptions`, and WhatsApp as a third notification channel. See "Phase 6: AI features
  and exception alerts" below for what's genuinely AI, what's deliberately rule-based, and what
  isn't implemented.
- **Auth**: email/password login and registration, plus optional "Sign in with Microsoft", gating
  the whole app. See "First-time setup" below — registering (by either method) never grants admin,
  so there's a required bootstrap step. See "Sign in with Microsoft: setup" for enabling the
  Microsoft option.

## Why tracking data is simulated

Section 3.3 of the proposal calls for polling MarineTraffic, VesselFinder, and Polestar GMDA.
None of these offer a public free API, and no credentials were available for this build. The
tracking worker (`backend/app/services/tracking_worker.py`) is built against a
`TrackingSourceAdapter` interface (`backend/app/sources/base.py`) with a `MockAdapter`
(`backend/app/sources/mock_adapter.py`) wired in for now, so the full pipeline — poll → status
engine → history → dashboard — works end-to-end. Swap in a real scraper/API client later by
implementing the same interface; nothing else needs to change.

The same is true of the Container/Booking module's five carrier portals (Section 8.1: ONE, Maersk,
MSC, CMA CGM, InterAsia) — no credentials available, so `backend/app/services/booking_worker.py`
polls a `BookingSourceAdapter` interface (`backend/app/sources/booking_base.py`) with a
`MockBookingAdapter` (`backend/app/sources/mock_booking_adapter.py`) wired in the same way.

## Prerequisites

- Docker Desktop (for PostgreSQL)
- Python 3.12+
- Node.js 20+
- An Anthropic API key if you want PDF bulk-upload extraction (Section 3.2) and AI voyage
  summaries (Phase 6) to work. Without it both report a clear "unavailable" message and
  everything else — Excel/CSV upload, delay detection, exception alerts, predictive ETA — works
  regardless.

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

## Phase 5: Container/Booking Tracking

`/containers` (Section 4), reachable by any logged-in user like the vessel dashboard. Register a
booking/container with its number, shipping line, and Port of Loading/Discharge; a simulated
carrier feed (see "Why tracking data is simulated" above) then advances it through five stages,
one per poll tick: **Booking Confirmed → Loaded → In Transit → Discharged → Gate Out**. Unlike the
vessel mock adapter's repeating voyage, this lifecycle is linear and one-way — a real booking
doesn't sail again after Gate Out, so once a booking reaches it, polling stops producing events
for it (see `backend/app/sources/mock_booking_adapter.py`'s module docstring).

Deliberately "structured the same way as the vessel dashboard" (the proposal's own words for this
module):

- Same Active/Archived tabs, free-text search (booking number/shipping line/POL/POD), and status
  filter chips as the vessel dashboard, plus the same colour-coded "Last Event" convention (a
  different five-colour palette so a screenshot never reads as the vessel table at a glance — see
  `frontend/app/components/BookingStatusDot.tsx`).
- Same manual archive/remove actions as Section 3.8, on each booking's history page. Unlike
  vessels, there's no *auto*-archive sweep here — the proposal doesn't specify a retention window
  for this module, and "Gate Out" is already a clear, final signal worth leaving visible.
- The five real carrier portals (Section 8.1: ONE, Maersk, MSC, CMA CGM, InterAsia) are catalogued
  in the **same** Settings → Tracking Sources screen as the vessel sources (marked "Not yet
  connected", same reasoning as MarineTraffic/VesselFinder/Polestar GMDA) rather than a second
  admin screen — the Mock Booking Feed's enable/disable toggle there pauses/resumes this module's
  simulated updates, exactly like the Mock Tracking Feed does for vessels.

**Deliberately not implemented**: bulk upload (Section 3.2's Excel/CSV/PDF import is specific to
vessel registration; Section 4 doesn't call for an equivalent here) and notifications/reports
(Section 6.C/7 are scoped to the vessel dashboard) — a booking event doesn't trigger an email/Teams
alert or appear in `/reports`.

## Phase 6: AI features and exception alerts

Section 7's list, delivered with a clear split between what a model does well and what it
shouldn't be doing at all.

**AI Voyage Summary** — on each vessel's history page (where the proposal's Figure 3 sketches
it). Click "Generate AI Summary" to turn the recorded timeline into a plain-language narrative
via Claude. Generation is on demand, never on page load, so opening a vessel never silently costs
an API call; the result is cached per vessel and marked "new events since — regenerate to update"
once the timeline moves on. Needs `ANTHROPIC_API_KEY`; without it the panel says so and every
other part of the page works as normal.

**Delay detection** — this required closing a real data gap first. Section 3.3 lists ETA among
the fields a tracking source reports, but nothing in the app captured one until now, which is
exactly why earlier phases refused to show a "Delayed" status (Section 3.10's "don't guess"
reasoning). Tracking sources now report an ETA per event (`StatusEvent.eta`, shown inline on the
timeline), so "delayed" is arithmetic against a real reported time: late arrival, or still
underway past the ETA, beyond `DELAY_THRESHOLD_MINUTES` (default 60). This finally uses the red
"Delayed" colour Section 6.E's table assigns and Figure 4's map legend shows.

**Exception alerts** at `/exceptions` — delays, unusually long port stays
(`LONG_PORT_STAY_HOURS`, default 72), and unexpected port calls. Each fires a notification once,
through the same channels as everything else.

> **Detection is rule-based, not model-inferred — deliberately.** An alert is a claim that
> something is wrong, and the useful property of such a claim is that you can check it: "arrived
> 6h 12m after the reported ETA of 14:00" is auditable against the timeline shown right below it.
> Rules also cost nothing per tick and behave identically on identical input. The model's job
> here is the *narrative*, which is a genuine language task; the alerting is arithmetic.

**Predictive ETA** — shown while a vessel is underway, computed as the median transit time of
that vessel's own previously completed voyages on the same route, with the sample size always
displayed. The proposal describes this as using "vessel speed, route, and historical data"; of
those, only historical data actually exists here (AIS-style reports carry no speed or route
geometry), so the panel says so rather than implying more. No prediction is shown at all until
there's at least one completed prior voyage.

**WhatsApp** — a third channel alongside Email and Teams, configured at Settings → Notifications.
Uses Meta's WhatsApp Business Cloud API, so it needs a phone-number ID and an access token rather
than a single webhook URL. One request is sent per recipient; if any recipient fails the whole
attempt is logged `failed` with the offending numbers, so a partial delivery never reads as a
clean success.

**Deliberately not implemented**: **route-deviation alerts** (Section 7's fourth bullet) — a
deviation needs a planned route to deviate *from*, and neither this app nor AIS-style tracking
supplies one; inventing a signal from port calls alone would be exactly the guesswork Section 3.10
argues against. **ETA-change notifications** — they'd fire on every routine source revision, which
is noise rather than signal.

## Tests

```bash
cd backend
.venv\Scripts\activate
pytest
```

Want to click through every feature yourself instead of just running the automated suite? See
[`verification/TESTING_GUIDE.md`](verification/TESTING_GUIDE.md) — a step-by-step manual checklist
covering auth and all five phases. `verification/REPORT.md` has the results of the last such pass.

## Notes

- **Session cookies across domains.** `COOKIE_SAMESITE` defaults to `lax`, which is correct when
  the frontend and backend share a site — including local dev, since `:3000` → `:8000` counts as
  same-site (SameSite ignores the port). Set it to `none` **only** for a split deployment across
  genuinely different domains, and then `COOKIE_SECURE=true` (and therefore HTTPS) is mandatory:
  browsers silently discard a `SameSite=None` cookie that isn't also `Secure`. The failure is
  nasty precisely because nothing errors — login returns 200 with a `Set-Cookie` header, the
  browser stores nothing, and every request afterwards reads as logged-out, so the login form
  just appears to do nothing. The backend logs a loud startup error if these two are set
  inconsistently.
- Tables are created automatically on backend startup (`Base.metadata.create_all`) — there's no
  migration tool wired up yet. This only *adds* new tables/columns, it doesn't alter existing
  ones, so a schema change (like Phase 2's new `archived_at` column, or the Microsoft sign-in
  work's `users.password_hash` becoming nullable, or Phase 6's new `status_events.eta` column and
  extra `whatsapp` notification-channel enum value) on a database that already has the old shape
  will error on first query. If you hit `UndefinedColumn`/`NOT NULL constraint`/`invalid input
  value for enum` errors after pulling schema changes, reset the local dev volume: `docker
  compose down -v && docker compose up -d`. **Add Alembic before this touches real data** — every
  phase so far has needed a reset, which is fine for demo data and unacceptable for anything
  you'd miss.
- The mock tracking worker advances each vessel's simulated voyage by one step every poll tick
  (`TRACKING_POLL_INTERVAL_SECONDS` in `.env`, default 300s/5min to match the dashboard's
  "auto-refreshed every 5 minutes"). Lower it in `.env` for faster manual testing. It only runs
  while the "Mock Tracking Feed" source is enabled in Settings (`/settings`). The Phase 5 booking
  worker shares this same interval and enable/disable pattern (via "Mock Booking Feed") - see
  "Phase 5: Container/Booking Tracking" above.
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
