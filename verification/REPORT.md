# Verification Report — Phases 1-6 + Auth (password + Microsoft) + Search

> **Latest pass: Phase 6 (Section 7 — AI features, delay/exception detection, WhatsApp).**
> See "Phase 6" and "Bugs found and fixed this pass" below; everything above that point is the
> record of earlier passes, carried forward. Screenshots `51`-`62` are fresh this pass.


Tested against `Vessel_Monitoring_Dashboard_Proposal_Final.pdf`, Sections 3.1-3.9, 4, 6.A-6.E, 7,
and Section 9 (Phases 1-5), plus the authentication layer (email/password **and** "Sign in with
Microsoft") and the four search bars (dashboard, containers, sources, users). Screenshots
referenced below live in `verification/screenshots/`. **Provenance note**: `01`-`23` and `29`-`33`
were captured during the previous (Microsoft sign-in) pass against a freshly reset database;
`24`-`28` (the detailed Notifications/Reports walkthrough with real local SMTP/Teams servers) are
carried over further still from the Phase 4 pass before that, since neither Phase 4's nor the auth
code was touched by this session's Phase 5 work. `34`-`50` are fresh this pass, covering the new
Container/Booking Tracking module end-to-end plus a light re-confirmation that Map View, Reports,
and Settings still render correctly afterwards.

This pass reused the existing database rather than resetting it (Booking/BookingEvent are brand
new tables - purely additive, so `create_all()` picks them up without needing the
`docker compose down -v` reset the previous auth pass required for its nullable-column change; see
README's migration note). The tracking/booking poll interval was temporarily lowered to 5 seconds
via `TRACKING_POLL_INTERVAL_SECONDS` at backend startup, as in previous passes - both the vessel
tracking worker and the new booking worker share this one setting. This pass did **not** clear the
database at the end.

## Result summary

*(Result summary below is from the Phase 5 pass; this pass's totals are **181/181 pytest**,
`tsc --noEmit` and `eslint` clean, with 51 new Phase 6 tests plus 1 regression test for the
login bug — see the Phase 6 section at the end.)*

- Backend: **130/130 pytest tests pass** (`cd backend && pytest`) — 23 new tests for Phase 5
  (mock booking adapter lifecycle, "Last Event" text formatting, the bookings CRUD/search/filter/
  history/archive/remove API, and the booking poll worker's gating/persistence).
- Frontend: `tsc --noEmit` and `eslint` both clean.
- **No bugs found in the new Phase 5 code.** One pre-existing UI inconsistency was caught and
  fixed while wiring Phase 5 into the shared Settings → Tracking Sources screen — see "Bug found
  and fixed this pass" below.
- **No conflicts found against Phases 1-4 or the auth layer.** See "Conflict checks" at the end.

---

## Section 3.1 — Vessel Registration

| Requirement | Result | Evidence |
|---|---|---|
| Name, IMO (unique 7-digit), optional destination | Pass | `04` |
| Duplicate IMO rejected with clear message | Pass | `05` |
| No destination → vessel just shows latest status indefinitely | Pass | MV Northern Light throughout `10`, `18` |

## Section 3.2 — Bulk Upload (Excel/CSV/PDF)

| Requirement | Result | Evidence |
|---|---|---|
| CSV parsed row-by-row, editable preview, row-level validation | Pass | `06` |
| Nothing imported silently | Pass | `07` |
| PDF extraction, or a clear "unavailable" message without an API key | Pass | `08` |

## Section 3.3-3.9 — Tracking, Dashboard, History, Lifecycle, Sources

Re-verified end-to-end, all unchanged from prior passes and unaffected by this session's auth
work:

| Requirement | Result | Evidence |
|---|---|---|
| Scheduled polling / status detection | Pass | `10`, `13` |
| Dashboard view / colour coding | Pass | `10` |
| Vessel history timeline | Pass | `13` |
| Auto-archive at destination retention | Pass | `17` — live scheduler, `ARRIVED_RETENTION_DAYS=0` |
| Manual archive / remove | Pass | `14`, `15`, `16` |
| Admin-only tracking-source management | Pass | `21` |

---

## Phase 3 — Search, Filters, Colour Coding, Map View

Re-verified, unchanged:

| Feature | Result | Evidence |
|---|---|---|
| 6.A Search (dashboard/sources/users) | Pass | `09`, `21`, `23` |
| 6.D Dashboard filter chips | Pass | `11` (Arrived at Destination), `12` (At Port) |
| 6.B Map View | Pass | `18` — reachable by a regular user, before admin promotion |

---

## Phase 4 — Notifications (6.C) and Reports (7)

Unchanged this pass - no code in `services/notification_service.py`, `report_service.py`,
`report_worker.py`, or their routers was touched by the Microsoft sign-in work.

- Detailed evidence (real local SMTP server + real local Teams-webhook receiver, event-triggered
  notifications, daily report, Excel/PDF export validity) carried over from the previous pass:
  `24`-`28`. See that pass's findings for the full breakdown, including the (expected, not a bug)
  STARTTLS failure against a bare debug SMTP server.
- This pass's own confirmation that nothing regressed: `32` (Settings → Notifications still
  renders and its cards are intact) and `33` (Reports page still renders, all three categories
  correct, including the empty-category-message fix carried over correctly).

---

## Phase 5 — Container/Booking Tracking (Section 4, new this pass)

New module at `/containers`, structured the same way as the vessel dashboard per the proposal's
own wording. Backend: `Booking`/`BookingEvent` models, `BookingSourceAdapter` interface +
`MockBookingAdapter` (`sources/booking_base.py`/`mock_booking_adapter.py`), `booking_worker.py`
(its own APScheduler instance, gated on an enabled "Mock Booking Feed" `TrackingSource` row -
reusing Section 3.9's admin screen rather than a new one), and `routers/bookings.py` (list/search/
filter/create/history/archive/remove, same access level as vessels - any logged-in user). Frontend:
`BookingTable`/`BookingStatusDot`/`AddBookingModal` components and `/containers` +
`/containers/[bookingNumber]` pages, mirroring `VesselTable`/`StatusDot`/`AddVesselModal` and the
vessel dashboard/history pages respectively.

1. Dashboard's new "Containers" nav link, next to Map View/Reports — `34`.
2. `/containers` in its empty state — `35`.
3. Registered two bookings (TCLU7788990 via Maersk Shanghai→Port Klang West, MSKU4455667 via MSC
   Ningbo→Butterworth); re-registering TCLU7788990 in lower-case was rejected as a duplicate
   (case-insensitive collision, matching the booking-number normalisation) — `36`.
4. Table immediately after registration, "Awaiting first tracking update…" for both — `37`; after
   a few live poll ticks, both show a colour-coded current stage and Current Location sourced from
   the simulated carrier feed, not vessel position data — `38`.
5. Free-text search by booking number — `39`; status filter chip ("Loaded") — `40`.
6. Booking history/timeline page for TCLU7788990, mid-lifecycle — `41`; after enough ticks to
   reach Gate Out, the full five-stage timeline is shown oldest-to-newest with matching
   colour-coded dots and correctly-worded "Last Event" text for every stage ("Booking Confirmed
   Shanghai", "Loaded Shanghai", "Departed Shanghai", "Discharged Port Klang West", "Gate Out Port
   Klang West") — `42`. Confirmed via direct DB/log inspection that no further events are produced
   for this booking on subsequent ticks - the lifecycle is genuinely terminal, not a bug.
7. Manual archive on TCLU7788990 — `43`; Archived tab shows it with history intact, no filter
   chips shown (mirroring the vessel Archived tab) — `44`. Manual remove on MSKU4455667 — `45`
   (back to the empty active state, 0 bookings).
8. Settings → Tracking Sources shows "Mock Booking Feed" (kind=container) as the only *connected*
   container source, with the five real carrier portals (ONE eCommerce, Maersk, MSC, CMA CGM,
   InterAsia) catalogued alongside it as "Not yet connected" — the same table, same admin screen,
   as the vessel sources — `46`.

| Requirement | Result | Evidence |
|---|---|---|
| Booking/Container No., Shipping Line, POL/POD, Current Location, Last Event, Source columns | Pass | `38` |
| Reliably distinguishes Loaded vs. Discharged (Section 3.10's stated gap for AIS data) | Pass | `41`, `42` - status comes directly from the simulated carrier record, no inference |
| All / Booking Confirmed / Loaded / In Transit / Discharged / Gate Out filter chips | Pass | `40` |
| Shares search/filter/colour-coding/archive patterns with the vessel dashboard | Pass | `35`-`45` throughout |
| Duplicate booking number rejected (case-insensitive) | Pass | `36`; `test_rejects_duplicate_booking_number_case_insensitively` |
| Lifecycle is linear/terminal at Gate Out, not a repeating cycle | Pass | `42`; `test_lifecycle_is_linear_not_repeating_after_gate_out`, `test_booking_lifecycle_stops_producing_events_after_gate_out` |
| Carrier sources reuse Settings → Tracking Sources (Section 3.9), not a new screen | Pass | `46` |
| Bookings require login, same as vessels | Pass | `test_bookings_require_login` |

### Bug found and fixed this pass: Tracking Sources "Not yet connected" badge would have mislabelled the Mock Booking Feed

While wiring the new "Mock Booking Feed" source into the existing Settings → Tracking Sources
table, found that the row component's `isConnected` check was hard-coded to
`source.adapter_key === "mock"` - true only for the vessel mock source. Left as-is, the actually-
polled Mock Booking Feed would have shown a "Not yet connected" badge right next to its own
"Enabled" checkbox, contradicting itself. Caught by code review before it ever reached a
screenshot (not from a failing test - there wasn't one covering this frontend-only badge logic).
**Fix**: `isConnected` now checks for either `"mock"` or `"mock_booking"`. Confirmed correct in
`46` - Mock Booking Feed shows "Enabled" with no "Not yet connected" badge, exactly like Mock
Tracking Feed.

---

## Auth — "Sign in with Microsoft" (previous pass, unaffected by Phase 5)

Added alongside the existing email/password login, for both new registrations and existing
accounts (including admins). Backend: `services/microsoft_auth_service.py` (authorize-URL
building, authorization-code → access-token exchange, Microsoft Graph `/v1.0/me` profile fetch),
new endpoints on `routers/auth.py` (`GET /microsoft/status`, `GET /microsoft/login`,
`GET /microsoft/callback`), new `User.auth_provider`/`User.microsoft_id` columns (with
`password_hash` now nullable for Microsoft-only accounts). Frontend: a shared
`MicrosoftSignInButton` on both `/login` and `/register`, shown only when the backend reports the
integration is actually configured.

**Design decisions, matching the app's existing "no self-promotion" and "graceful when
unconfigured" postures:**
- A brand-new Microsoft sign-in always creates a `user`-role account — exactly like password
  registration, there is no way to become `admin` via Microsoft sign-in. The first admin still
  has to come from `promote-admin` (README's "First-time setup").
- If the Microsoft account's email matches an **existing** account (created with a password, or
  already an admin), sign-in links to that same account by email rather than creating a
  duplicate — the existing role is untouched either way.
- The button is hidden entirely (not shown-but-broken) when `MICROSOFT_CLIENT_ID`/
  `MICROSOFT_CLIENT_SECRET` aren't set - verified via `GET /api/auth/microsoft/status` returning
  `{"configured": false}` by default (`test_status_reports_unconfigured_by_default`) and the
  frontend button rendering nothing in that case (code review of `MicrosoftSignInButton.tsx`).
- CSRF protection via a `state` token round-tripped through a short-lived cookie, checked on
  callback - `test_callback_state_mismatch_redirects_to_login_with_error`.

**Verified against a real local stand-in identity provider, not just mocks.** A minimal local
HTTP server (`fake_microsoft_idp.py`, not part of the app) implemented the actual OAuth
`/authorize`, `/token`, and Graph `/v1.0/me` endpoints, and the backend was pointed at it via
`MICROSOFT_AUTHORITY_BASE_URL`/`MICROSOFT_GRAPH_BASE_URL` (both overridable for exactly this
reason). This exercises the real HTTP calls `microsoft_auth_service.py` makes end-to-end - not an
in-process mock of the Python functions:

1. Registered `test.user@example.com` with a normal password.
2. Logged out, clicked "Sign in with Microsoft" on `/login` — a genuine full-page redirect to the
   backend's `/api/auth/microsoft/login`, which redirected again to the fake IdP's authorize page,
   clearly labelled as a local test stand-in (not a copy of Microsoft's real UI) — `29`.
3. Clicking "Continue" redirected back to the backend's real callback URL with a genuine
   authorization code and the matching CSRF state; the backend made real HTTP calls to the fake
   IdP's `/token` and `/v1.0/me` endpoints, then logged the browser in — landing back on the
   dashboard as `test.user@example.com` — `30`.
4. As admin, Settings → Users shows `test.user@example.com` with a "Microsoft" badge — `31` — even
   though the account was originally created with a password, because sign-in linked it by email
   (see the bug/fix below for why this specific check mattered).

| Check | Result | Evidence |
|---|---|---|
| New Microsoft sign-in creates a `user`-role account, never admin | Pass | `test_callback_creates_a_new_user_role_user_and_logs_in` |
| Existing local account is linked by email, not duplicated | Pass | `30`, `31`; `test_callback_links_to_an_existing_local_account_by_email` |
| Password login rejected cleanly for a Microsoft-only account (no 500) | Pass | `test_local_login_rejected_for_a_microsoft_only_account` |
| CSRF state mismatch / missing code / provider error → clean redirect with a message, no crash | Pass | `test_callback_state_mismatch_redirects_to_login_with_error`, `test_callback_missing_state_redirects_to_login_with_error`, `test_callback_provider_error_param_redirects_with_error` |
| Token-exchange/network failure → clean redirect, not a 500 | Pass | `test_callback_http_failure_redirects_with_error` |
| Button hidden when not configured | Pass | `test_status_reports_unconfigured_by_default` + code review |

### Bug found and fixed this pass: Users tab "Microsoft" badge never showed for a linked account

The Users tab's "Microsoft" badge was originally driven by `auth_provider` (set once, at account
creation, and never changed afterwards). For `test.user@example.com` - created with a password,
then linked to Microsoft sign-in - `auth_provider` correctly stayed `"local"` forever, so the
badge **never appeared**, even though Microsoft sign-in genuinely worked for that account. Caught
directly: the first capture of `31` showed no badge at all.

**Fix**: added a `User.microsoft_linked` property (`microsoft_id is not None`) to the model,
exposed as a new `microsoft_linked` field on `UserOut` alongside the existing `auth_provider`, and
switched the frontend badge condition (and its tooltip, "Signed up via..." → "Can sign in via...")
to use it instead. `auth_provider` is kept as-is for its own purpose (recording how the account
was *originally* created). Re-captured `31` (after a backend restart) confirms the badge now
appears correctly. Backend tests updated to assert `microsoft_linked` directly for both the
fresh-Microsoft-signup case and the linked-local-account case.

---

## Conflict checks — Microsoft sign-in against Phases 1-4 / existing Auth

- **`password_hash` becoming nullable doesn't weaken password login**: `login()` now checks
  `user.password_hash is None` explicitly before calling `verify_password()` (which would have
  raised on `None` otherwise) - covered by `test_local_login_rejected_for_a_microsoft_only_account`
  and confirmed no existing password-login test regressed (all prior `test_auth.py` cases still
  pass unchanged).
- **No new admin path**: reviewed `routers/auth.py`'s callback - the new-account branch hard-codes
  `role=UserRole.USER`, and the linking branch never touches `role` at all. Session cookie issuance
  reuses the exact same `_set_session_cookie()` helper as password login/register - no separate,
  possibly-weaker session logic for the OAuth path.
- **CSRF cookie doesn't collide with the session cookie**: `ms_oauth_state` is a distinctly-named,
  short-lived (10 minute) cookie, deleted on every callback outcome (success or failure) - doesn't
  linger or interfere with `session_token`.
- **Whole-app auth gating unaffected**: `AuthProvider.tsx`'s redirect rules and every backend
  router's `Depends(get_current_user)`/`Depends(require_admin)` wiring are untouched; a
  Microsoft-authenticated session is just a normal session from every other route's perspective
  (same JWT shape, same cookie) - confirmed by `18`/`19`/`21`-`23` all working normally for a
  Microsoft-originated login in the same pass.
- **Phase 1-4 features unaffected**: full walkthrough `01`-`23` re-run fresh against the new
  schema with zero regressions in the previous pass; `32`/`33` confirmed Notifications/Reports
  specifically at that time.

## Conflict checks — Phase 5 against Phases 1-4 / Auth

- **Independent scheduler, independent tables**: `booking_worker.py` runs its own
  `BackgroundScheduler` instance (like `report_worker.py`'s), separate from
  `tracking_worker.py`'s - a stuck/slow booking poll can't block vessel polling or vice versa.
  `Booking`/`BookingEvent` are new tables with no foreign keys into `vessels`/`status_events` -
  nothing in the vessel domain reads or writes them.
- **Same access level, same auth dependency**: `bookings.router` is mounted with
  `Depends(get_current_user)` in `main.py`, identical to `vessels.router` - no separate/weaker
  gating path introduced. Confirmed via `test_bookings_require_login`.
- **Shared Settings screen extended, not forked**: the five new container `TrackingSource` seed
  rows (kind=`container`) and the vessel rows (kind=`vessel`) live in the same table and the same
  admin UI; `list_tracking_sources`/create/update/delete in `tracking_sources.py` needed zero
  changes to support this - `kind` was already a generic column.
- **Reports/Notifications untouched**: neither `report_service.py`/`notification_service.py` nor
  their routers reference `Booking` at all - a booking event does not appear in `/reports` or
  trigger a notification, matching the README's explicit scope note for this module.
- **Phase 1-4 and auth full regression**: light re-confirmation this pass (Map View `47`, Reports
  `48`, Settings → Notifications `49`, Settings → Users `50`) shows all four rendering correctly
  with the existing demo data (including the Microsoft-linked account from the previous pass)
  after the Phase 5 changes to `main.py`/`models.py`/`schemas.py`/`settings/page.tsx`.

---

## Phase 6 — AI features, delay/exception detection, WhatsApp (Section 7, new this pass)

Backend: `StatusEvent.eta` (closing a Section 3.3 data gap - see below), `services/ai_service.py`
(Claude-backed voyage summary), `services/exception_detector.py` (rule-based detectors),
`services/predictive_eta.py` (median of the vessel's own completed voyages),
`services/timeutil.py` (shared naive-UTC helper, extracted from `archive_worker.py`), WhatsApp in
`notification_service.py`, new `VesselException`/`VoyageSummary` tables, and `routers/insights.py`.
Frontend: `/exceptions` page, `ExceptionBadge`, AI summary + predicted-ETA + exception panels on
the vessel history page, and a WhatsApp card in Settings → Notifications.

**Delay detection required closing a real data gap first, not working around one.** Section 3.3
lists ETA among the fields a tracking source reports, but nothing in the app captured one, which
is precisely why Phases 4/5 declined to implement delay alerts (Section 3.10's "don't guess"
reasoning, quoted in `notification_service.py`'s original scope note) and why Section 6.E's red
"Delayed" colour sat unused. Rather than inferring lateness, this pass added `StatusEvent.eta`
end-to-end (`RawReport.eta` → mock adapter → tracking worker → timeline UI), so a delay is now
arithmetic against a real reported time and is checkable against the timeline shown directly
below the alert — visible in `54`.

| Requirement (Section 7) | Result | Evidence |
|---|---|---|
| AI Voyage Summary | Pass | Panel on the vessel history page (`54`); `test_ai_service.py` (6 tests: prompt carries the real timeline, model ID, refusal handling, API failure, no-key, empty timeline); `test_insights_api.py` cache/staleness/regenerate tests |
| Unavailable-not-broken without `ANTHROPIC_API_KEY` | Pass | `54` shows the panel explaining it while the rest of the page works; `test_summary_generation_is_503_without_an_api_key` |
| AI Delay Detection | Pass | `52`, `53`; `test_exception_detector.py` (late arrival, on-time, overdue-in-transit, no-ETA, superseded-ETA) |
| AI Exception Alerts — long port stay, unexpected port call | Pass | `test_exception_detector.py`; each alerts once (`test_the_same_exception_is_only_recorded_once`) |
| AI Predictive ETA | Pass | `54`; `test_predictive_eta.py` (median not mean, outlier resistance, incomplete legs excluded, no-basis cases) |
| WhatsApp notifications | Pass | Settings card `56`; `test_whatsapp_notifications.py` (Cloud API request shape, per-recipient send, partial-failure handling, token masking) |
| Exceptions reachable by any logged-in user, not admin-only | Pass | `52` as admin; `test_insights_require_login` for the gating |

**Deliberately not implemented, and why** — consistent with how Section 3.10 was handled
throughout:
- **Route-deviation alerts** (Section 7's fourth bullet): detecting a deviation needs a planned
  route to compare against. Neither the app nor AIS-style position reporting supplies one, so
  there is no honest signal to compute. Documented in `models.ExceptionKind`'s docstring and
  surfaced to users in the Exceptions page banner rather than silently omitted.
- **ETA-change notifications**: would fire on every routine source revision — noise, not signal.
- **Detection is rule-based rather than model-inferred.** This is a design decision, not a
  shortcut: an alert is a claim that something is wrong, and its value depends on being
  checkable. "Arrived 6h 0m after the reported ETA of 06 Aug 2026, 20:34 UTC" can be verified
  against the timeline; a model's impression cannot. The AI in Phase 6 is the *narrative*, which
  is a genuine language task.

### Bugs found and fixed this pass

**1. Login was completely broken in local development (pre-existing, not from Phase 6).** Caught
immediately: the Playwright walkthrough timed out waiting for the post-login redirect. The
session cookie was hard-coded to `SameSite=None` (added in commit `d04f6a3`, presumably for the
cross-domain deployed setup) while `COOKIE_SECURE` defaults to `false` — and browsers **silently
discard** a `SameSite=None` cookie that isn't also `Secure`. The failure mode is unusually nasty:
`POST /api/auth/login` returned 200 with a valid `Set-Cookie`, the browser stored nothing, and
every subsequent request read as logged-out, so the login form simply appeared to do nothing.
Confirmed directly — a diagnostic Playwright run showed `cookies: []` after a 200 login, and
re-running with `COOKIE_SECURE=true` stored the cookie correctly.

**Fix**: `cookie_samesite` is now a config setting (default `lax`, correct for same-site setups
including local dev), `auth.py` reads it instead of hard-coding, `app/main.py` logs a loud startup
error if `samesite=none` is paired with `secure=false`, and `.env.example`/README document the
cross-domain combination. Regression test:
`test_session_cookie_defaults_to_a_combination_browsers_actually_accept`. **Deployment note for
the split-domain setup: set `COOKIE_SAMESITE=none` *and* `COOKIE_SECURE=true` together.**

**2. Unbounded exception panel buried the vessel timeline.** The first capture of `54` showed
**19** stacked alerts (later 38) for one vessel, pushing the movement timeline — the reason the
page exists — off the screen. Detection was correct (the simulated feed loops a full voyage every
few ticks, so each alert was a genuinely distinct late arrival), but the *presentation* was
unbounded, and in production a long-serving vessel accumulates one exception per late voyage
forever. **Fix**: the history endpoint returns the 5 most recent plus a true `exception_count`,
the UI renders "Showing the 5 most recent of 38 · See all exceptions", and
`GET /api/insights/exceptions` grew a `limit` (default 200), matching how the notification log is
already capped. Re-captured `54` confirms it. Tests:
`test_history_caps_the_exception_panel_but_reports_the_true_total`,
`test_exceptions_list_respects_its_limit`.

**3. Predicted ETA rendered as a misleading "median of 0h".** The backend rounded the transit
duration to one decimal place in hours; the simulated feed completes a voyage within a single
poll tick, so every prediction collapsed to `0.0` and read as instant travel. **Fix**: 4-decimal
precision server-side, and the frontend picks a sensible unit (seconds/minutes/hours) — now reads
"a median of 1 seconds" on demo data, which is at least accurate.

---

## Conflict checks — Phase 6 against Phases 1-5 / Auth

- **`StatusEvent.eta` is additive and optional**: `RawReport.eta` defaults to `None`, so the
  Phase 5 booking pipeline and every pre-existing adapter/test construct reports unchanged. All
  prior tracking/status/archive tests pass untouched.
- **Notification dispatch was refactored, not duplicated**: adding a third channel to three call
  sites would have triplicated the enabled-channel logic, so `dispatch_to_enabled_channels()` now
  owns it and `notify_vessel_event`/`notify_exception`/`send_test_notification` share it. All
  Phase 4 notification tests pass unchanged, confirming behaviour is identical for the two
  original channels.
- **`timeutil.py` extraction**: `archive_worker.py`'s private `_as_naive_utc` moved to a shared
  module and is imported back under the same name — Section 3.7's retention sweep is behaviourally
  untouched (`test_archive_worker.py`, `test_archive.py` pass unchanged).
- **Exception sweep can't break tracking**: it runs after the poll's own commit, wrapped in its
  own try/except (mirroring how Phase 4's notifications were wired), so a detector fault leaves
  already-persisted vessel data intact.
- **Phase 5 untouched**: no Container/Booking code was modified; `59` confirms the module still
  renders and polls correctly.
- **Phase 1-5 regression sweep**: `57` (dashboard), `58` (Map View), `59` (Containers), `60`
  (Reports), `61` (Settings → Users), `62` (Settings → Tracking Sources) all render correctly
  after the Phase 6 changes, with no console errors beyond the expected pre-login 401.

## Known gaps

Route-deviation alerts and ETA-change notifications are documented non-goals (see above), not
oversights. Only Microsoft is implemented as a social/SSO sign-in option — no other providers
were requested. The app still has **no migration tool**; every phase has required a dev database
reset, which is fine for demo data and must be addressed with Alembic before real data depends
on it.
