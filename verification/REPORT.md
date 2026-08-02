# Verification Report — Phases 1-2 + Auth + Search

Tested against `Vessel_Monitoring_Dashboard_Proposal_Final.pdf`, Sections 3.1-3.9 and Section 9
(Phases 1-2), plus the subsequently-added email/password authentication and the three search bars
(dashboard, Settings → Tracking Sources, Settings → Users). Screenshots referenced below live in
`verification/screenshots/`, numbered in the order captured during this pass. This pass fully
replaces the screenshot set and findings from the pre-auth verification — the numbering has
changed since every flow now starts from a login.

All testing used a clean, freshly-seeded database (`docker compose down -v && docker compose up
-d`) so results reflect default configuration.

## Result summary

- Backend: **66/66 pytest tests pass** (`cd backend && pytest`).
- Frontend: `tsc --noEmit` and `eslint` both clean.
- Full manual walkthrough of every requirement below, driven through the real UI in headless
  Chromium (now via `/register` → `/login` first, since the whole app is gated) and cross-checked
  against the API/database directly.
- **One real bug found and fixed this pass** (mock tracking adapter — see below). It predates
  auth/search and was never caught by the earlier verification pass or by unit tests calling the
  adapter in isolation; a longer live-scheduler run this time surfaced it.
- **No conflicts found** between auth/search and any Phase 1-2 behavior — see the dedicated
  section at the end.

---

## Section 3.1 — Vessel Registration

| Requirement | Result | Evidence |
|---|---|---|
| Name, IMO (unique 7-digit), optional destination | Pass | `04` |
| Duplicate IMO rejected with clear message | Pass | `05` — "IMO 1234567 is already registered" |
| No destination → vessel just shows latest status indefinitely | Pass | MV Horizon Star throughout `07`, `10` — never enters arrival flow |

## Section 3.2 — Bulk Upload (Excel/CSV/PDF)

| Requirement | Result | Evidence |
|---|---|---|
| CSV parsed row-by-row, editable preview, row-level validation | Pass | `06` — "Ready" / "Needs fix" statuses |
| Nothing imported silently | Pass | `07` — only the 2 valid rows landed |
| PDF extraction, or a clear "unavailable" message without an API key | Pass | `08` |

Still-open minor UX gap from the previous pass (unchanged, not re-verified in depth this time):
the Bulk Upload panel has no Cancel button when a PDF preview errors out, only the modal header ✕.

## Section 3.3 / 3.3a — Automated Tracking & Status Detection

| Requirement | Result | Evidence |
|---|---|---|
| Scheduled polling updates location/status | Pass | `10` |
| Status derived from source report vs. known ports vs. destination | Pass | `test_status_engine.py`, 8/8 |
| No destination → only Sailing/At Sea/At Port ever shown | Pass | `10` |

### New bug found and fixed: duplicate "departed" event on every voyage-cycle reset

The mock adapter's "cycle back to a new voyage" branch (`mock_adapter.py`) set
`state["step"] = -1` and emitted a "departed [new origin]" report; the shared
`state["step"] += 1` at the bottom of the loop then left `step` at **0**, not 1. On the *next*
tick, the adapter re-executed the `step == 0` branch — re-emitting an identical "departed
[same origin]" report a second time — instead of advancing to "arrived". Visible directly in a
vessel's history as two consecutive, identical "Sailed X" lines every time it completed a voyage
cycle (caught in an earlier draft of screenshot `11`, before the fix).

This wasn't caught earlier because:
- The original Phase 1-2 verification pass only ran the mock adapter for a few ticks — not
  enough to reach a full cycle-reset.
- No test exercised more than one full voyage cycle end-to-end.

**Fix**: `state["step"] = 0` instead of `-1` in the reset branch, so the trailing `+= 1` correctly
lands on step 1 (`"arrived"`) for the next tick. Two new tests in
`backend/tests/test_mock_adapter.py` drive a full cycle and assert no duplicate "departed" report
and that internal state lands on step 1 after a reset. `11` (captured post-fix) shows three clean
voyage cycles with no repeated lines.

## Section 3.4 — Dashboard View

Pass — table columns, "Last Event" text format, and colour-coded dots all unchanged and correct
(`01`, `10`).

## Section 3.5 — Vessel History

Pass — `11` shows a full, correctly-alternating timeline (departed → arrived → sailed-from-
destination → departed → arrived …), current-status banner reflects the latest event.

## Section 3.6 — Latest Status Display

Pass — `04` (no data yet, "Awaiting first tracking update…"), `10`/`11` (latest event always
shown, full history preserved underneath).

## Section 3.7 — "Arrived at Destination" Lifecycle Automation

Re-verified with tracking temporarily disabled (via Settings) so the live scheduler couldn't
overwrite the test vessel mid-check, then a backdated arrival + `run_archive_sweep()`:
auto-archived correctly (`archived_count: 1`), and a control case (fresh arrival, not yet past
retention) correctly archived nothing (`archived_count: 0`). Result visible in the dashboard
Archived tab with no manual action taken: `15`.

## Section 3.8 — Manual Removal

Pass — archive (`12`, `13`) and remove (`14`) both still work correctly under auth, exactly as
before. `GET /history` returns 404 after removal; the vessel's history stays fully browsable
after archiving.

## Section 3.9 — Website Source Management

Pass — admin-only gating (`18`), "Not yet connected" labelling on the three real sites, and the
functional mock-source enable/disable toggle all still work. Add/edit/remove CRUD unchanged from
the previous pass (not re-screenshotted this time, covered by `test_tracking_sources_api.py`).

---

## Auth (email/password login, admin bootstrap via terminal, role management)

| Check | Result | Evidence |
|---|---|---|
| Unauthenticated visit to any page redirects to `/login` | Pass | `01`; also checked a direct deep link to `/vessels/2233445` — redirects cleanly, no data leak |
| Register → live password-rule checklist → account created as `user`, never `admin` | Pass | `02`, `03`, `04` |
| Non-admin has no Settings link and is bounced from `/settings` if navigated directly | Pass | `04` (no link); direct-nav bounce confirmed in the prior auth-focused pass, unchanged |
| `python -m app.cli promote-admin <email>` is the only way to create an admin | Pass | used to promote `owner@example.com` mid-pass; no in-app self-promotion path exists |
| Already-logged-in user visiting `/login` redirects to dashboard instead of showing the form | Pass | `17` — a specific edge case checked this pass, no stale/broken state |
| Admin can promote/demote; last remaining admin can't be demoted | Pass | `20` — "Demote to user" correctly disabled/would-409 when it's the only admin |
| Self-demotion cleanly redirects out of Settings (fixed in the prior auth pass) | Not re-broken | unchanged code path, not re-exercised this pass |

## Search bars (dashboard, Tracking Sources, Users)

| Check | Result | Evidence |
|---|---|---|
| Dashboard search filters by name/IMO/destination (server-side), works alongside Active/Archived tabs | Pass | `09` |
| Tracking Sources search filters by name/URL only (client-side) — doesn't match on Kind, which is correct given its own label | Pass | `18` |
| Users search filters by email (client-side); last-admin guard still computed from the *unfiltered* list | Pass | `20` |
| No interference between search debouncing and the dashboard's 5-minute auto-refresh interval | Pass | reviewed the effect dependencies directly (`debouncedSearch` state avoids the stale-closure issue a naive implementation would hit) |

---

## Conflicts between the new auth/search work and Phase 1-2: none found

Specifically checked for and ruled out:
- Auth cookies (`credentials: "include"`) interfering with the existing `FormData` bulk-upload
  request — still works (`06`, `07`).
- The `apiFetch` wrapper's automatic `Content-Type` header breaking multipart uploads — it
  correctly skips setting `Content-Type` when the body is `FormData`.
- Router-level auth dependencies (`Depends(get_current_user)` / `Depends(require_admin)`)
  changing any response shape or status code for the *authorized* case — no schema changes, only
  401/403 added for the unauthorized case (already covered by dedicated tests).
- Search state fighting the existing view/archived-tab state or the periodic refresh — traced
  through the effect dependencies by hand in addition to the browser check.

## Known gaps (unchanged, out of scope for this pass)

Search/filters/map view beyond what's now built (Phase 3 still owes filter chips and the map),
notifications/reports (Phase 4), and the Container/Booking module (Phase 5) remain unbuilt.
