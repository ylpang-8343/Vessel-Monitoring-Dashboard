# Manual Testing Guide

A step-by-step checklist to click through every feature of the app in a browser and
confirm it actually works. This is the manual companion to two other things in this repo — it
doesn't replace either:

- **`cd backend && pytest`** — the automated test suite (130 tests). Run this first; it's faster
  and catches most regressions before you ever open a browser.
- **`verification/REPORT.md`** — a record of what was already tested and found, with screenshots.
  Use *this* guide when you want to re-check things yourself (after a code change, before a demo,
  onboarding a new tester), not just read about a past pass.

Each step below is a checkbox with what to do and what you should see. If a step doesn't match,
that's a bug — check the relevant file mentioned so you know where to start looking.

## Before you start

1. Follow the README's "Running locally" section: `docker compose up -d`, start the backend
   (`uvicorn app.main:app --reload --port 8000`), start the frontend (`npm run dev`). Open
   http://localhost:3000.
2. **Optional, but makes this much faster**: the tracking/booking workers poll every 300 seconds
   (5 minutes) by default. Stop the backend, set `TRACKING_POLL_INTERVAL_SECONDS=5` (either in
   `backend/.env` or as an environment variable for that one run), and restart it. Vessels and
   bookings will then progress through their simulated lifecycle every 5 seconds instead of every
   5 minutes, so you don't have to sit and wait during the steps below. Set it back to the default
   (or remove the override) when you're done - a 5-second poll is only for testing.
3. You'll need two accounts for a full pass: a regular user and an admin. Steps 1-2 below create
   both.

---

## 1. Registration, login, and roles (Auth)

- [ ] Go to http://localhost:3000/ while logged out → you're redirected to `/login`.
- [ ] Click through to `/register`. Try a weak password (e.g. `abc`) → rejected with a clear
      reason (needs 8+ chars, one uppercase, one lowercase, one symbol).
- [ ] Try mismatched confirm-password → rejected.
- [ ] Register a real account, e.g. `you@example.com` / `Passw0rd!`. You land on the dashboard,
      logged in as a **regular user** — no "Settings" link in the header.
- [ ] Log out (top-right menu). Log back in with the same credentials → works.
- [ ] Try logging in with the wrong password → clear error, not a crash.
- [ ] **Bootstrap the first admin** (there's deliberately no in-app way to do this yourself): in a
      terminal, with the backend venv active —
      ```
      cd backend
      .venv\Scripts\activate
      python -m app.cli promote-admin you@example.com
      ```
      Refresh the browser (or log out/in) → a "Settings" link now appears in the header.
- [ ] As admin, go to Settings → Users. Register a second throwaway account in another
      browser tab/incognito window first, then confirm it shows up here as `user`. Promote it to
      `admin`, then demote it back — both work.
- [ ] Try demoting yourself while you're the *only* admin → blocked with a clear message (can't
      leave zero admins).
- [ ] *(Optional)* If `MICROSOFT_CLIENT_ID`/`MICROSOFT_CLIENT_SECRET` are configured in
      `backend/.env`, a "Sign in with Microsoft" button appears on `/login` and `/register` — try
      it. If they're not configured, the button simply doesn't appear (that itself is correct
      behaviour, not a bug).

## 2. Phase 1 — Vessel registration, bulk upload, and tracking

- [ ] On the dashboard, click **+ Add** → **Single Vessel**. Register one with a destination (e.g.
      name `MV ABC`, IMO `1234567`, destination `Pasir Gudang`) → appears on the dashboard.
- [ ] Register a second vessel with **no destination set** → also appears; it'll never show
      "ETA to Destination"/"Arrived at Destination" and is never auto-archived (that's correct).
- [ ] Try registering a vessel with the same IMO number again → rejected as a duplicate.
- [ ] Try an IMO that isn't exactly 7 digits → rejected.
- [ ] **Bulk upload**: click + Add → Bulk Upload (Excel/CSV/PDF), upload a `.csv` with columns
      Vessel Name / IMO Number / Destination Port. Confirm the preview table shows every row with
      a status (ready / duplicate / needs fix) *before* anything is imported, then import only the
      "ready" ones.
- [ ] Upload a `.pdf` vessel list. If `ANTHROPIC_API_KEY` isn't set in `backend/.env`, you should
      see a clear "unavailable" message rather than a crash or silent failure — that's correct.
- [ ] Wait for a poll tick (5s if you lowered the interval, else up to 5 min) → the vessels you
      added pick up a "Last Event" (e.g. "Sailed Qingdao — …") with a colour-coded dot next to it.
- [ ] Click into a vessel → its history page shows a growing timeline as more ticks happen, plus a
      "Current Status" summary that always reflects the *latest* event.

## 3. Phase 2 — Lifecycle automation and tracking-source management

- [ ] Keep watching a vessel that has a destination set — after enough ticks it reaches "Arrived
      at Destination" (green dot), then dwells there for a couple of ticks before departing again
      ("Sailed from Destination").
- [ ] From a vessel's history page, click **Archive** → confirm bar appears → confirm. It moves to
      the dashboard's **Archived** tab; history stays intact and clickable.
- [ ] From another vessel's history page, click **Remove** → confirm → it's gone entirely
      (dashboard redirect), and revisiting its old URL 404s.
- [ ] *(Optional, needs patience or a lowered retention window)* Set `ARRIVED_RETENTION_DAYS=0` in
      `backend/.env` and restart the backend — a vessel that reaches "Arrived at Destination"
      should auto-archive on the very next poll tick, with no manual action.
- [ ] As admin, go to Settings → Tracking Sources. Confirm "Mock Tracking Feed" is **Enabled**
      and every other vessel source (MarineTraffic, VesselFinder, Polestar GMDA) is marked "Not
      yet connected" (expected — no real credentials configured).
- [ ] Uncheck "Mock Tracking Feed" → wait a tick → no new vessel events appear. Re-check it → new
      events resume.
- [ ] Add a new source via **+ Add Source**, edit its name/URL inline, then remove it → all work.
- [ ] As a **non-admin** user, try navigating directly to `/settings` → redirected away (no access).

## 4. Phase 3 — Search, filters, colour coding, Map View

- [ ] Dashboard search box: type part of a vessel name, an IMO number, and a destination port —
      each narrows the table correctly. Clear it → full list returns.
- [ ] Click each filter chip (At Sea / At Port / ETA to Destination / Arrived at Destination) →
      the table only shows vessels currently in that status. Click "All" → clears the filter.
- [ ] Confirm the coloured dot next to each "Last Event" matches its status consistently across
      the dashboard, the filter chips, and a vessel's history timeline.
- [ ] Go to **Map View** (`/map`) → vessels with a recognised port/sea-region location appear as
      markers; any vessel at an unrecognised location is listed separately below the map instead
      of guessed at. Zoom/pan the map (needs internet access to load OpenStreetMap tiles).
- [ ] On Settings → Tracking Sources and → Users, confirm their own search boxes filter correctly
      by name/URL and by email respectively.

## 5. Phase 4 — Notifications and Reports

- [ ] As admin, go to Settings → Notifications. Fill in the **Email** card with SMTP details (a
      real provider, or a local debug server like `python -m aiosmtpd -n -l localhost:1025`) and
      save. Fill in the **Microsoft Teams** card with any URL that accepts a JSON `POST` and save.
- [ ] Click **Send Test Notification** → a result appears (sent/skipped/failed per channel), and a
      new row shows up in "Recent Activity" below with the outcome and, if it failed, *why*.
- [ ] Enable **Daily Report**, pick an hour, save. Click **Send Daily Report Now** → confirms
      immediately without waiting for the scheduled hour; check "Recent Activity" again.
- [ ] Let a vessel produce a real tracking event (arrival/departure) with Email or Teams enabled →
      a corresponding notification is logged automatically, not just from the manual test button.
- [ ] Go to `/reports` (works for a regular user too, not just admins) → three sections (Active
      Vessels, ETA to Destination, Arrived at Destination) matching the dashboard's current data.
- [ ] Click **Export to Excel** and **Export to PDF** → both download a file; open each and
      confirm the vessel rows match what's on screen.

## 6. Phase 5 — Container/Booking Tracking

- [ ] From the dashboard header, click **Containers** → `/containers`, structured like the vessel
      dashboard (Active/Archived tabs, search, filter chips).
- [ ] Click **+ Add**, register a booking: number (e.g. `TCLU7788990`), shipping line, Port of
      Loading, Port of Discharge → appears in the table as "Awaiting first tracking update…".
- [ ] Try registering the same booking number again (try a different case, e.g. lower-case) →
      rejected as a duplicate either way.
- [ ] Wait for poll ticks → the booking advances one stage at a time: **Booking Confirmed → Loaded
      → In Transit → Discharged → Gate Out**, each with its own colour dot and a "Last Event" line
      naming the right port (Port of Loading for the first three stages, Port of Discharge for the
      last two).
- [ ] Keep waiting past Gate Out → confirm **no further events** appear for that booking; its
      lifecycle is meant to be one-way and terminal, unlike a vessel's repeating voyage.
- [ ] Click into the booking → its history page shows the same growing timeline pattern as a
      vessel's, plus Current Status/POL→POD/Current Location summary stats.
- [ ] Test the status filter chips (All / Booking Confirmed / Loaded / In Transit / Discharged /
      Gate Out) and the search box (by booking number, shipping line, or either port).
- [ ] From a booking's history page, test **Archive** (moves to the Archived tab, history kept)
      and, on a different booking, **Remove** (deleted entirely, redirects to `/containers`).
- [ ] As admin, go to Settings → Tracking Sources → confirm "Mock Booking Feed" (kind=`container`)
      is **Enabled** and shows no "Not yet connected" badge, while ONE eCommerce/Maersk/MSC/
      CMA CGM/InterAsia are all catalogued as "Not yet connected" (expected — no real carrier
      credentials configured). This is the *same* table as the vessel sources, not a separate one.
- [ ] Uncheck "Mock Booking Feed" → wait a tick → no new booking events. Re-check it → resumes.
- [ ] As a regular (non-admin) user, confirm `/containers` is still reachable (this module isn't
      admin-gated, matching the vessel dashboard) but Settings still isn't.

## 7. Cross-cutting checks

- [ ] Log out entirely and try navigating directly to `/`, `/containers`, `/reports`, `/map`, and
      `/settings` by URL → every one redirects to `/login` (no page renders data while logged out).
- [ ] Resize the browser window / check on a smaller viewport — tables scroll horizontally rather
      than breaking the page layout.
- [ ] Open the browser console while clicking through the whole app → no red errors during normal
      use (occasional expected 401s right at the login redirect are fine; anything else isn't).

---

**When you're done**: stop the dev servers (`Ctrl+C` on the backend/frontend terminals) and, if
you don't need the data anymore, `docker compose down` (add `-v` only if you also want to wipe the
database volume). If you changed `TRACKING_POLL_INTERVAL_SECONDS`/`ARRIVED_RETENTION_DAYS` for
faster testing, remember to revert them before treating this as a "production-like" run again.
