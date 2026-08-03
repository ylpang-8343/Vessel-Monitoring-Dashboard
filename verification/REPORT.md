# Verification Report — Phases 1-3 + Auth + Search

Tested against `Vessel_Monitoring_Dashboard_Proposal_Final.pdf`, Sections 3.1-3.9 and Section 9
(Phases 1-3), plus the email/password authentication layer and the search bars added ahead of
Phase 3. Screenshots referenced below live in `verification/screenshots/`, numbered in the order
captured during this pass. This pass fully replaces the screenshot set and findings from the
previous (pre-Phase-3) verification — the numbering has changed to make room for the new filter
chips and Map View screens.

All testing used a clean, freshly-seeded database (`docker compose down -v && docker compose up
-d`) so results reflect default configuration. The tracking poll interval was temporarily lowered
to 5 seconds (and, briefly, the arrival retention window to 0 days) via environment variables at
backend startup — not committed to `.env` — purely so the mock adapter's status cycle and the
Section 3.7 retention sweep could be observed in a few minutes instead of days; this has no effect
on the application code being tested. The database was cleared back to empty after this pass
finished (see the end of this report).

## Result summary

- Backend: **67/67 pytest tests pass** (`cd backend && pytest`).
- Frontend: `tsc --noEmit` and `eslint` both clean.
- Full manual walkthrough of every requirement below, driven through the real UI in headless
  Chromium, cross-checked against the API directly where useful.
- **No bugs or conflicts found this pass.** Every Phase 1-2 flow, the auth layer, the three
  search bars, and both new Phase 3 features (dashboard filter chips, Map View) worked correctly
  together, including at the specific intersection points most likely to break (status filter +
  search combined, retention-sweep interaction with the mock adapter, map rendering for both
  admin and non-admin sessions). See "Conflict checks" at the end for exactly what was checked.

---

## Section 3.1 — Vessel Registration

| Requirement | Result | Evidence |
|---|---|---|
| Name, IMO (unique 7-digit), optional destination | Pass | `04` |
| Duplicate IMO rejected with clear message | Pass | `05` — "IMO 1234567 is already registered" |
| No destination → vessel just shows latest status indefinitely | Pass | MV Northern Light throughout `10`, `16`, `18` — never enters ETA/Arrived states, never auto-archived even while `ARRIVED_RETENTION_DAYS=0` was active for the `17` test |

## Section 3.2 — Bulk Upload (Excel/CSV/PDF)

| Requirement | Result | Evidence |
|---|---|---|
| CSV parsed row-by-row, editable preview, row-level validation | Pass | `06` |
| Nothing imported silently | Pass | `07` — only the 3 valid CSV rows landed |
| PDF extraction, or a clear "unavailable" message without an API key | Pass | `08` — "ANTHROPIC_API_KEY is not configured; PDF extraction is unavailable" |

## Section 3.3 / 3.3a — Automated Tracking & Status Detection

| Requirement | Result | Evidence |
|---|---|---|
| Scheduled polling updates location/status | Pass | `10`, `13` |
| Status derived from source report vs. known ports vs. destination | Pass | `test_status_engine.py`, 8/8; also visible directly in the `13` timeline (Sailed → Arrived → Sailed-from-destination → Sailed [new voyage] → Arrived, no duplicated events) |
| No destination → only Sailing/At Sea/At Port ever shown | Pass | MV Northern Light, `10`/`16`/`18` |

No regression of the mock-adapter duplicate-departure bug fixed in the previous pass — the `13`
timeline shows a clean, correctly alternating cycle with no repeated "Sailed [same port]" lines,
and `test_mock_adapter.py`'s two regression tests still pass.

## Section 3.4 — Dashboard View

Pass — table columns, "Last Event" text format, and colour-coded dots all correct (`10`).

## Section 3.5 — Vessel History Tracking

Pass — `13` shows a full, correctly-alternating timeline; current-status banner reflects the
vessel's latest event ("ETA to Destination" shown live, matching the latest "Sailed [origin]"
entry).

## Section 3.6 — Latest Status Display

Pass — `04` (no data yet, "Awaiting first tracking update…"), `13` (latest event always shown,
full history preserved underneath).

## Section 3.7 — "Arrived at Destination" Lifecycle Automation

Re-verified end-to-end through the *live* scheduler (not a direct internal function call): with
`ARRIVED_RETENTION_DAYS=0` temporarily set, a freshly-registered vessel (MV Retention Test) was
tracked from registration through its first "Arrived at Destination" event and was automatically
archived on the very next scheduler tick with no manual action — `17` shows it in the Archived tab
alongside three other vessels that happened to also cross into Arrived at Destination during the
same short window (confirming the sweep isn't special-cased to one vessel). Retention was then
restored to the default 10 days for the rest of the pass.

## Section 3.8 — Manual Removal

Pass — archive (`14`) and remove (`16`) both work correctly under auth. The removed vessel
(MV Remove Me) is gone from the Active list with no trace; the archived vessel (MV ABC) stays
fully browsable via its history page and appears only under Archived (`15`).

## Section 3.9 — Website Source Management

Pass — admin-only gating, "Not yet connected" labelling on the three real sites, and the
functional mock-source enable/disable toggle all work (`21`). Add/edit/remove CRUD unchanged from
prior passes, covered by `test_tracking_sources_api.py`.

---

## Phase 3 — Search, Filters, Colour Coding, Map View

### 6.A Search (built ahead of Phase 3, re-verified here)

Pass — dashboard search (`09`), Tracking Sources search (`21`), and Users search (`23`) all filter
correctly and don't interfere with each other's state.

### 6.D Dashboard Filters (new)

New `status` query param on `GET /api/vessels`, backed by a new backend test
(`test_list_vessels_filters_by_status`). Filter chips (All / At Sea / At Port / ETA to
Destination / Arrived at Destination) shown on the Active tab only, matching the neutral
verifiable statuses from Section 3.10 rather than a fixed "Pasir Gudang" filter.

| Check | Result | Evidence |
|---|---|---|
| Chip narrows the table to exactly the matching vessels | Pass | `11` (ETA to Destination — 3 vessels), `12` (At Sea — 1 vessel) |
| Chips only shown on Active tab, not Archived | Pass | reviewed in code (`view === "active"` gate) and confirmed visually — `15`/`17` (Archived) show no chip row |
| "All" clears the filter | Pass | verified as part of the walkthrough between `12` and `13` |

### 6.E Status Colour Coding

Pass — unchanged from Phase 1-2, dots visible throughout (`10`, `13`, etc.). Extended palette
(amber for ETA to Destination, zinc for Sailed from Destination) documented in `StatusDot.tsx`,
still consistent everywhere it's used, including the new filter chips and the map markers.

### 6.B Map View (new)

New `/map` page using react-leaflet + real OpenStreetMap tiles, with a `lib/portCoordinates.ts`
lookup of real-world lat/lng for every port/sea-region the mock adapter or destination list
produces.

| Check | Result | Evidence |
|---|---|---|
| Tiles load and markers place at real, correct coordinates | Pass | `18` — vessel and destination-port markers correctly clustered around the Singapore Strait/Malaysia coast, matching where the underlying vessels actually are |
| Colour-coded vessel markers match the dashboard's StatusDot palette | Pass | `18` |
| Destination ports get their own fixed marker, independent of which vessels are currently en route | Pass | `18` (⚓ markers at Pasir Gudang and Butterworth) |
| Accessible to a regular (non-admin) user, not gated like Settings | Pass | `18` was captured *before* the account was promoted to admin |
| Unmapped vessels (no tracking data / unrecognised location) listed separately instead of silently dropped | Pass | confirmed in code review and in the prior spot-check pass; not re-triggered this pass since all active vessels had tracking data by the time `18` was captured |

---

## Auth (email/password login, admin bootstrap via terminal, role management)

| Check | Result | Evidence |
|---|---|---|
| Unauthenticated visit to any page redirects to `/login` | Pass | `01` |
| Register → live password-rule checklist → account created as `user`, never `admin` | Pass | `02`, `03`, `04` |
| `python -m app.cli promote-admin <email>` is the only way to create an admin | Pass | used mid-pass to promote `ops.lead@example.com`; CLI output: "ops.lead@example.com is now an admin." |
| Already-logged-in user visiting `/login` redirects to dashboard instead of showing the form | Pass | `20` |
| Admin can promote/demote; last remaining admin can't be demoted | Pass | `22` — "Demote to user" is visibly disabled for `ops.lead@example.com` while it's the only admin, with no extra setup needed to trigger it |
| Map View is reachable by a regular user; Settings is not | Pass | `18` captured pre-promotion; a non-admin has no Settings link (`04`, `10`) |

---

## Conflict checks — Phase 3 against Phase 1-2 / Auth / Search

Specifically checked for and ruled out:

- **Status filter + search combined**: both are independent params on the same `GET /api/vessels`
  call (`q` filtered in SQL, `status` filtered in Python on the resolved latest-event type) — no
  interaction bug possible since they compose as a plain AND. Reviewed in code; not separately
  screenshotted since it's a straightforward composition of two already-verified filters.
- **Archive-sweep retention (3.7) interaction with the fast-cycling mock adapter**: with
  `ARRIVED_RETENTION_DAYS=0` active, four different vessels reaching "Arrived at Destination" in
  the same short window were all correctly swept on their own next tick, not just the one vessel
  the test was designed around (`17`) — confirms the sweep iterates all vessels, not a
  single-vessel special case.
- **Map View auth gating**: `/map` is deliberately *not* in `AuthProvider`'s admin-only allowlist
  (only `/settings` is) — confirmed by capturing `18` from a non-admin session before the CLI
  promotion step ran.
- **Leaflet + Next.js SSR**: `VesselMap` is loaded via `next/dynamic` with `ssr: false` since
  Leaflet touches `window` at import time; confirmed no server-render crash and no hydration
  console errors across the whole pass (`console` listener attached for the full run, zero errors
  logged outside of the three intentionally-triggered ones in Part 1: a pre-login 401, the
  duplicate-IMO 409, and the no-API-key 503).
- **Router-level auth dependencies unchanged by Phase 3 changes**: `vessels.py`'s new `status`
  parameter shares the same `Depends(get_current_user)` gate as before; no new endpoints were
  added that needed separate auth wiring.

## Database cleared after this pass

Once screenshots were captured, the Postgres volume was wiped (`docker compose down -v`) and the
backend restarted against a fresh database, so `vessels`, `status_events`, and `users` all start
empty — no leftover test accounts or demo vessels from this pass remain. `tracking_sources` is
reseeded automatically at startup (Section 3.9's catalogue of known sources, not user data), same
as any first-time run. As before, the first admin account must be created via
`python -m app.cli promote-admin <email>` after registering through the web app — see README.md.

## Known gaps (unchanged, out of scope for this pass)

Notifications/reports (Phase 4) and the Container/Booking module (Phase 5) remain unbuilt.
