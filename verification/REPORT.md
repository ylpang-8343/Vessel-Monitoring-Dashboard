# Phase 1-2 Verification Report

Tested against `Vessel_Monitoring_Dashboard_Proposal_Final.pdf`, Sections 3.1-3.9 and Section 9
(Phases 1-2). Screenshots referenced below live in `verification/screenshots/`, numbered in the
order they were captured during this pass. All testing used a clean, freshly-seeded database
(`docker compose down -v && docker compose up -d`) so results reflect default configuration.

## Result summary

- Backend: **42/42 pytest tests pass** (`cd backend && pytest`).
- Frontend: `tsc --noEmit` and `eslint` both clean.
- Full manual walkthrough of every Phase 1-2 requirement below, driven through the real UI in
  headless Chromium and cross-checked against the API/database.
- **One real bug found and fixed during this pass** (Section 3.7, see below) — not a cosmetic
  issue, an actual case where the auto-archive automation could never fire in live operation.
- **One minor UX gap found, not fixed** (Section 3.2, see below) — noted for a future pass.

---

## Section 3.1 — Vessel Registration

| Requirement | Result | Evidence |
|---|---|---|
| Name, IMO (unique 7-digit), optional destination | Pass | `02, 03` |
| Duplicate IMO rejected with clear message | Pass | `05` — "IMO 1234567 is already registered" |
| Destination from configurable list or free text | Pass | dropdown in `03`; free-text "Other" option in code (`AddVesselModal.tsx`), not separately screenshotted this pass |
| No destination → vessel just shows latest status indefinitely | Pass | MV Horizon Star throughout `08`, `10` — no destination column, never enters arrival flow |

**04** confirms a freshly-registered vessel shows "Awaiting first tracking update…" rather than a
guessed status (Section 3.6).

## Section 3.2 — Bulk Upload (Excel/CSV/PDF)

| Requirement | Result | Evidence |
|---|---|---|
| CSV parsed row-by-row | Pass | `07` |
| Editable preview before import | Pass | `07` — all three fields editable inline |
| Row-level validation (ok / duplicate / invalid) | Pass | `07` shows "Ready" / "Needs fix"; duplicate case covered by `test_preview_csv_flags_valid_duplicate_and_invalid_rows` |
| Nothing imported silently | Pass | Import button labelled with exact importable count, confirmed excludes duplicates/invalid (`08` shows only the 2 valid rows landed) |
| PDF extraction, or a clear "unavailable" message without an API key | Pass | `09` — "ANTHROPIC_API_KEY is not configured; PDF extraction is unavailable" |

**Minor UX gap found (not fixed):** when a PDF preview fails, the Bulk Upload panel has no
`Cancel` button (only the modal's header ✕) because the panel only renders Cancel/Import once
`rows.length > 0`, and a failed preview leaves `rows` empty. Not a functional blocker — the
header ✕ still closes it — but worth a follow-up (`frontend/app/components/AddVesselModal.tsx`,
`BulkUploadForm`).

## Section 3.3 / 3.3a — Automated Tracking & Status Detection

| Requirement | Result | Evidence |
|---|---|---|
| Scheduled polling updates location/status | Pass | `10` — 4 vessels advanced via the tracking worker |
| Status derived from source report vs. known ports vs. destination | Pass | `backend/tests/test_status_engine.py`, 8/8 tests covering all 5 states, case-insensitivity, whitespace |
| No destination → only Sailing/At Sea/At Port ever shown | Pass | MV Horizon Star / MV Northern Light in `10` never show ETA/Arrived statuses |

## Section 3.4 — Dashboard View

| Requirement | Result | Evidence |
|---|---|---|
| Single sortable table: name, IMO, location, last event, destination, source | Pass | `01`, `10` |
| "Last Event" states exactly what/where/when | Pass | e.g. "Sailed Pasir Gudang — 02 Aug 2026, 09:04" in `10` |
| Colour-coded dot per category (3.4 references 6.E) | Pass | `10` — blue (Sailing), grey (Sailed from Destination); green/orange verified in `14`/`20` |

## Section 3.5 — Vessel History

| Requirement | Result | Evidence |
|---|---|---|
| Full timeline reconstructed from every status update | Pass | `11` |
| Current status reflects latest event, not a stale one | Pass | `11` — status correctly reads "Sailed from Destination" after departure, matching the proposal's own worked example almost verbatim |

## Section 3.6 — Latest Status Display

Pass — `04` (no data yet), `10`/`11` (latest event always shown, history preserved underneath,
confirmed via `GET /history` returning the full event list every time).

## Section 3.7 — "Arrived at Destination" Lifecycle Automation

**A real bug was found here and fixed.** Original design: the mock tracking adapter advanced
every vessel by one step on every poll tick unconditionally, and the retention sweep ran *after*
polling within the same tick. Consequence: a vessel's latest event could never remain
`ARRIVED_DESTINATION` across two ticks — the very next tick's poll always moved it to "departed"
before the sweep got a chance to see it sitting there. **The retention sweep was unreachable via
the live scheduler**, even though calling it directly (as the original Phase 2 unit tests did)
looked correct in isolation. This is exactly the kind of bug that per-function unit tests miss and
an end-to-end pass catches.

Fix (`backend/app/sources/mock_adapter.py`, `backend/app/services/tracking_worker.py`):
1. A vessel now *dwells* at `ARRIVED_DESTINATION` for `DWELL_TICKS` (2) polls — no new event is
   emitted while dwelling — before departing again, so it has a real window during which "days
   since arrival" can be evaluated.
2. `run_archive_sweep()` now runs *before* polling in each tick, not after, so a vessel that has
   aged past retention is archived and excluded from that same tick's poll — instead of the poll
   always winning the race.

Verified via the **actual live scheduler** (not a direct function call): registered a vessel,
temporarily ran the backend with `ARRIVED_RETENTION_DAYS=0` / `TRACKING_POLL_INTERVAL_SECONDS=8`,
and watched it depart → arrive → auto-archive with zero manual intervention:

```
09:22:08  Sailed Ningbo         (ETA to Destination)
09:22:16  Arrived Butterworth   (Arrived at Destination)
09:22:24  archived_at set       (retention sweep, next tick)
```

No spurious third "departed" event was created — confirming the vessel was correctly excluded
from polling the instant it was archived. Evidence: `12`, `13`, `14`, `15`.

Two new regression tests guard this specifically (not just the isolated sweep logic, already
covered by 5 existing `test_archive_worker.py` tests):
`test_vessel_dwells_at_arrived_destination_across_ticks_instead_of_departing_immediately` and
`test_live_poll_pathway_auto_archives_vessel_past_retention_without_manual_sweep_call`.

Under **default settings** (10-day retention, 5-minute polling, 2-tick/10-minute dwell), a vessel
still departs again on its own well before the retention window would apply — matching Section
3.5's expected "Sailed from Destination" behavior for the normal case. The sweep exists for
vessels that genuinely sit arrived for a long time (a real adapter may simply stop reporting after
arrival), which the mock now models by dwelling instead of always advancing.

## Section 3.8 — Manual Removal

| Requirement | Result | Evidence |
|---|---|---|
| Archive (keep history) at any point | Pass | `16`, `17` — confirmation step, "Archived on" badge, history intact |
| Remove (delete) at any point, regardless of destination | Pass | `18`, `19` — confirmed gone from dashboard and `GET /history` returns 404 after |
| Cascading delete of history | Pass | `test_remove_vessel_deletes_it_and_its_history` |

## Section 3.9 — Website Source Management

| Requirement | Result | Evidence |
|---|---|---|
| Admin can add, edit, remove sources | Pass | `23`/`24` (add), `25`/`26` (edit), `27` (remove) |
| Settings screen, no code change needed to catalogue a new site | Pass | same |
| Enable/disable is honest about what's actually connected | Pass | `21` — MarineTraffic/VesselFinder/Polestar GMDA permanently labelled "Not yet connected" |
| Toggling the functional (mock) source actually pauses/resumes tracking | Pass | `20`→`21`: 2 ticks while disabled created 0 events (confirmed via API); `22`: re-enabled, next tick created 1 event |

---

## Known gaps (out of scope for Phases 1-2, previously communicated)

Search/filters/map view (Phase 3), notifications/reports (Phase 4), Container/Booking module
(Phase 5), and any authentication/role system (never scoped in any phase — flagged separately in
conversation) remain unbuilt. Section 3.10's neutral status categorisation is satisfied by
construction — the status engine only ever produces the five states in `EventType`, never a
load/discharge guess.
