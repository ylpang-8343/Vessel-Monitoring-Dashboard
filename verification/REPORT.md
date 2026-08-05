# Verification Report — Phases 1-4 + Auth + Search

Tested against `Vessel_Monitoring_Dashboard_Proposal_Final.pdf`, Sections 3.1-3.9, 6.A-6.E, 7, and
Section 9 (Phases 1-4), plus the email/password authentication layer and the three search bars.
Screenshots referenced below live in `verification/screenshots/`, numbered in the order captured
during this pass. This pass fully replaces the screenshot set and findings from the previous
(pre-Phase-4) verification — the numbering has changed to make room for the new Notifications and
Reports screens.

All testing used a clean, freshly-seeded database (`docker compose down -v && docker compose up
-d`) so results reflect default configuration. The tracking poll interval was temporarily lowered
to 5 seconds (and, briefly, the arrival retention window to 0 days) via environment variables at
backend startup — not committed to `.env` — purely so the mock adapter's status cycle, the
Section 3.7 retention sweep, and the new event-triggered notifications could be observed in a few
minutes instead of hours. This pass did **not** clear the database at the end (unlike the previous
pass) — the demo data from this walkthrough (vessels, the `ops.lead@example.com` admin account,
the local-SMTP/Teams notification settings) is still in place if you want to look at it.

## Result summary

- Backend: **96/96 pytest tests pass** (`cd backend && pytest`) — 29 new tests for notifications
  and reports.
- Frontend: `tsc --noEmit` and `eslint` both clean.
- Full manual walkthrough of every requirement below, driven through the real UI in headless
  Chromium, cross-checked against the API directly where useful.
- **Notifications were verified against real local services, not mocks**: a real local SMTP
  server (`aiosmtpd`) and a real local HTTP server standing in for a Microsoft Teams webhook, both
  listening on `localhost`. See the Phase 4 section below for what was actually observed.
- **One real bug found and fixed this pass** (Reports page empty-category message — see below).
- **No other bugs or conflicts found.** See "Conflict checks" at the end for exactly what was
  checked at the Phase 1-4 boundary.

---

## Section 3.1 — Vessel Registration

| Requirement | Result | Evidence |
|---|---|---|
| Name, IMO (unique 7-digit), optional destination | Pass | `04` |
| Duplicate IMO rejected with clear message | Pass | `05` — "IMO 1234567 is already registered" |
| No destination → vessel just shows latest status indefinitely | Pass | MV Northern Light throughout `10`, `18`, `28` — never enters ETA/Arrived states, never auto-archived even while `ARRIVED_RETENTION_DAYS=0` was active for the `17` test |

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
| Status derived from source report vs. known ports vs. destination | Pass | `test_status_engine.py`, 8/8; also visible directly in the `13` timeline |
| No destination → only Sailing/At Sea/At Port ever shown | Pass | MV Northern Light throughout |

No regression of the mock-adapter duplicate-departure bug fixed in an earlier pass — `13` shows a
clean, correctly alternating cycle, and `test_mock_adapter.py`'s regression tests still pass.

## Section 3.4 — Dashboard View

Pass — table columns, "Last Event" text format, and colour-coded dots all correct (`10`).

## Section 3.5 — Vessel History Tracking

Pass — `13` shows a full, correctly-alternating timeline; current-status banner reflects the
vessel's latest event.

## Section 3.6 — Latest Status Display

Pass — `04` (no data yet, "Awaiting first tracking update…"), `13` (latest event always shown,
full history preserved underneath).

## Section 3.7 — "Arrived at Destination" Lifecycle Automation

Re-verified end-to-end through the *live* scheduler: with `ARRIVED_RETENTION_DAYS=0` temporarily
set, a freshly-registered vessel (MV Retention Test) was tracked from registration through its
first "Arrived at Destination" event and was automatically archived on the very next scheduler
tick with no manual action — `17` shows it in the Archived tab alongside three other vessels that
independently crossed into Arrived at Destination during the same short window. Retention was
then restored to the default 10 days for the rest of the pass.

## Section 3.8 — Manual Removal

Pass — archive (`14`) and remove (`16`) both work correctly under auth. The removed vessel is gone
from the Active list with no trace; the archived vessel stays fully browsable via its history page.

## Section 3.9 — Website Source Management

Pass — admin-only gating, "Not yet connected" labelling on the three real sites, and the
functional mock-source enable/disable toggle all work (`21`). The enable/disable toggle was
additionally exercised live during Phase 4 testing (paused to get a clean notifications screenshot,
then resumed) with no side effects.

---

## Phase 3 — Search, Filters, Colour Coding, Map View

Re-verified, unchanged since the previous pass:

| Feature | Result | Evidence |
|---|---|---|
| 6.A Search (dashboard/sources/users) | Pass | `09`, `21`, `23` |
| 6.D Dashboard filter chips | Pass | `11` (Arrived at Destination), `12` (At Sea) |
| 6.E Status colour coding | Pass | consistent across dashboard, history, filter chips, and map markers |
| 6.B Map View | Pass | `18` — tiles load, markers correctly positioned, reachable pre-admin-promotion |

---

## Phase 4 — Notifications (6.C) and Reports (7 / Phase 4)

### Notifications

Backend: `services/notification_service.py` (email via `smtplib`, Teams via an incoming webhook
POST), `services/report_worker.py` (hourly check for the daily report), new `NotificationSettings`
(singleton config row) and `NotificationLog` (append-only send-attempt history) tables, admin-only
`routers/notifications.py`. Frontend: Settings → Notifications tab (`24`-`27`).

Triggered on vessel arrival, departure, and specifically arrival-at-destination (Section 6.C).
**ETA-change and delay notifications are intentionally not implemented** — the same reasoning as
Section 3.10's dashboard-status recommendation applies: this app has no *planned* ETA to compare
a report against, so a "delay" alert would be a guess dressed up as data. WhatsApp is also not
implemented — the proposal's own Figure 5 labels it "planned for phase 2 rollout" (i.e. explicitly
a later enhancement, not this phase).

**This was verified against real local services, not mocks**, to prove the actual network/protocol
integration works, not just that the right Python functions get called:
- A real local SMTP server (`aiosmtpd`, `localhost:1025`) received genuine connection attempts.
  `smtplib` connected, issued `EHLO`, and correctly refused to proceed because this debug server
  doesn't advertise `STARTTLS` support — logged as `failed` with the accurate detail "STARTTLS
  extension not supported by server" (`25`, `26`, `27`). This is expected, correct behaviour, not
  a bug: real SMTP providers (Gmail, Office 365, SendGrid, etc.) on port 587 require STARTTLS, so
  requiring it is the right default; a bare debug server without TLS support is exactly the kind
  of misconfiguration this error handling exists to report clearly instead of hanging or crashing
  the tracking-poll loop that triggered it.
- A real local HTTP server stood in for a Microsoft Teams incoming webhook (`localhost:9091`) and
  genuinely received every POST: the manual test message, every real vessel arrival/departure
  event fired automatically by the live tracking scheduler (not manually triggered), and the
  daily report's summary text — all with the exact wording the code was designed to produce, e.g.
  `"Vessel Arrived at Destination — MV Coastal Trader\nMV Coastal Trader (IMO 1112223): Arrived
  Pasir Gudang — 05 Aug 2026, 00:54\nDestination: Pasir Gudang\nSource: Mock Tracking Feed"` and
  `"Daily Vessel Report — 05 Aug 2026\n...Active: 3 · ETA to Destination: 0 · Arrived at
  Destination: 2"`.

| Check | Result | Evidence |
|---|---|---|
| Settings → Notifications: Email/Teams/Daily Report cards save independently | Pass | `24` (empty) → `25` (configured) |
| Password field never round-trips to the browser; blank-on-save leaves it unchanged | Pass | `test_notifications_api.py::test_patch_settings_updates_only_provided_fields` |
| "Send Test Notification" hits every enabled channel immediately | Pass | `25` — Teams `sent`, Email `failed` (real STARTTLS negotiation, see above) |
| Real vessel events trigger notifications automatically (not just the manual test) | Pass | `26` — log shows "Vessel Departure/Arrival/Arrived at Destination" entries with real vessel names/IMOs, generated by the live scheduler with zero manual action |
| Channel enabled but unconfigured → logged as `skipped`, not silently dropped or crashed | Pass | `test_notify_vessel_event_logs_skipped_when_enabled_but_unconfigured` |
| "Send Daily Report Now" delivers immediately, bypassing the schedule | Pass | `27` — Daily Vessel Report entries at the top of Recent Activity with accurate counts |
| Non-admin/unauthenticated requests rejected | Pass | `test_notifications_api.py::test_non_admin_user_forbidden`, `test_unauthenticated_request_rejected` |

### Reports (Section 7 / Phase 4)

Backend: `services/report_service.py` (Excel via `openpyxl`, PDF via `reportlab`), any-logged-in-user
`routers/reports.py`. Frontend: `/reports` page (`28`), reachable via a new "Reports" link next to
"Map View" on the dashboard header.

Covers three of the proposal's four report categories — Active Vessels, ETA to Destination, and
Arrived at Destination. **"Delayed vessels" is intentionally not included**, for the same reason
notifications skip delay alerts (see above) — there's no planned-ETA data to compute a delay from,
and Section 3.10 already established that this app doesn't guess at that; real delay detection is
explicitly Phase 6 (AI Delay Detection).

| Check | Result | Evidence |
|---|---|---|
| Summary view shows the three categories with correct counts and vessel data | Pass | `28` |
| Reachable by a regular (non-admin) user | Pass | `test_reports_api.py::test_regular_user_can_access_reports` |
| Excel export downloads a real, valid, multi-sheet .xlsx | Pass | Playwright captured a genuine browser download event (`vessel-report.xlsx`); `test_build_excel_report_has_one_sheet_per_category_with_correct_rows` opens the generated bytes back with `openpyxl` and checks sheet names/headers/data |
| PDF export downloads a real, valid PDF | Pass | Playwright captured a genuine browser download event (`vessel-report.pdf`); `test_build_pdf_report_produces_a_valid_pdf` checks the `%PDF` signature |
| Unauthenticated requests rejected | Pass | `test_reports_api.py::test_unauthenticated_request_rejected` |

### Bug found and fixed this pass: Reports page showed the wrong empty-category message

`VesselTable` (shared by the dashboard and, new this phase, the Reports page) hard-coded its
empty-state text as *"No vessels registered yet. Click "+ Add" to start monitoring one."* On the
Reports page, an empty category (e.g. "ETA to Destination (0)" while 3 vessels were Active) showed
this exact text — wrong and misleading, since vessels plainly *were* registered, and the Reports
page doesn't even have a "+ Add" button. Screenshot `28`'s first capture showed this directly.

**Fix**: added an optional `emptyMessage` prop to `VesselTable` (default preserves the dashboard's
existing wording), and the Reports page now passes `"No vessels in this category right now."` -
`28` (re-captured after the fix) shows the corrected message. `tsc`/`eslint` re-checked clean
afterwards; no test previously covered this frontend-only string, so none needed updating.

---

## Auth (unchanged, re-verified)

| Check | Result | Evidence |
|---|---|---|
| Unauthenticated visit to any page redirects to `/login` | Pass | `01` |
| Register → live password-rule checklist → account created as `user`, never `admin` | Pass | `02`, `03`, `04` |
| `python -m app.cli promote-admin <email>` is the only way to create an admin | Pass | used mid-pass to promote `ops.lead@example.com` |
| Admin can promote/demote; last remaining admin can't be demoted | Pass | `22` |
| Reports and Map View reachable by a regular user; Settings is not | Pass | `18`/`28` captured pre-promotion |

---

## Conflict checks — Phase 4 against Phase 1-3 / Auth

- **Notification failures never block tracking updates**: `run_tracking_poll()` persists every
  StatusEvent and commits *before* attempting any notification; each `notify_vessel_event()` call
  is separately wrapped in `try/except`. Confirmed live - hundreds of real tracking ticks ran
  throughout this pass with the Email channel continuously failing (STARTTLS), and the dashboard,
  history, and archive sweep all kept working normally the entire time.
- **Daily-report scheduler is a separate APScheduler instance from the tracking-poll scheduler**
  (`report_worker._scheduler` vs. `tracking_worker._scheduler`) — starting/stopping one doesn't
  affect the other; both are correctly no-op'd in tests via `conftest.py`'s monkeypatches (needed
  a new one this pass for `report_worker`, added alongside the existing `tracking_worker` patch).
- **Reports/Notifications auth gating matches their intended scope**: Reports mounted with
  `Depends(get_current_user)` (any user, like vessels/history/bulk_upload), Notifications mounted
  admin-gated within its own router (like Users) — reviewed against `main.py`'s `include_router`
  calls and confirmed via the dedicated 401/403 tests.
- **VesselTable reuse between the dashboard and Reports**: this is exactly where the empty-message
  bug above was found - now fixed and both call sites re-verified (`04`/`15` for the dashboard's
  default message, `28` for the Reports override).

## Known gaps (unchanged, out of scope for this pass)

The Container/Booking module (Phase 5) remains unbuilt. Within Phase 4 itself: WhatsApp
notifications and delay-detection alerts/reports are explicitly deferred (see above), matching the
proposal's own phasing.
