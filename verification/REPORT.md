# Verification Report — Phases 1-4 + Auth (password + Microsoft) + Search

Tested against `Vessel_Monitoring_Dashboard_Proposal_Final.pdf`, Sections 3.1-3.9, 6.A-6.E, 7, and
Section 9 (Phases 1-4), plus the authentication layer (now email/password **and** "Sign in with
Microsoft") and the three search bars. Screenshots referenced below live in
`verification/screenshots/`. **Provenance note**: `01`-`23` and `29`-`33` were captured fresh
during this pass (against a freshly reset database); `24`-`28` (the detailed Notifications/Reports
walkthrough with real local SMTP/Teams servers) are carried over unchanged from the previous
Phase 4 pass, since that code wasn't touched by this session's work - `32`/`33` are this pass's
light re-confirmation that Notifications and Reports still work correctly afterwards.

All testing used a clean, freshly-seeded database (`docker compose down -v && docker compose up
-d`) - required this time regardless, since `User.password_hash` becoming nullable and the new
`auth_provider`/`microsoft_id` columns are schema changes `create_all()` can't apply to an
existing table (see README's migration note). The tracking poll interval was temporarily lowered
to 5 seconds (and, briefly, the arrival retention window to 0 days) via environment variables at
backend startup, as in previous passes. This pass did **not** clear the database at the end - the
demo data (vessels, `ops.lead@example.com` admin, `test.user@example.com` linked account) is still
in place.

## Result summary

- Backend: **107/107 pytest tests pass** (`cd backend && pytest`) — 11 new tests for Microsoft
  sign-in (status, login redirect, callback success/failure/CSRF, account linking, local-login
  guard against a Microsoft-only account).
- Frontend: `tsc --noEmit` and `eslint` both clean.
- **"Sign in with Microsoft" was verified against a real local identity-provider stand-in, not
  just mocked unit tests** - a genuine OAuth authorize → token exchange → Graph profile-fetch HTTP
  round trip. See the dedicated section below.
- **One real bug found and fixed this pass** (Users tab "Microsoft" badge never appeared for an
  account that linked Microsoft sign-in after registering locally — see below).
- **No other bugs or conflicts found** against Phases 1-4. See "Conflict checks" at the end.

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

## Auth — "Sign in with Microsoft" (new this pass)

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
  schema with zero regressions; `32`/`33` confirm Notifications/Reports specifically.

## Known gaps (unchanged, out of scope for this pass)

The Container/Booking module (Phase 5) remains unbuilt. WhatsApp notifications and
delay-detection alerts/reports remain explicitly deferred (Phase 4's own scope notes). Only
Microsoft is implemented as a social/SSO sign-in option - no other providers (Google, etc.) were
requested.
