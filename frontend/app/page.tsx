"use client";

import { useCallback, useEffect, useState } from "react";
import AddVesselModal from "./components/AddVesselModal";
import VesselTable from "./components/VesselTable";
import { statusMeta } from "./components/StatusDot";
import {
  Chip,
  ErrorBar,
  EmptyState,
  PageBanner,
  Panel,
  PanelFooter,
  Shell,
  TabButton,
  inputClass,
} from "./components/ui";
import { ApiError, EventType, listVessels, Vessel } from "@/lib/api";

// Matches Figure 2's "Auto-refreshed every 5 minutes" caption.
const DASHBOARD_REFRESH_MS = 5 * 60 * 1000;

type View = "active" | "archived";

// Section 6.D filter chips - the neutral, verifiable statuses from Section 3.10, not a
// fixed "Pasir Gudang" filter. "Sailed from Destination" is deliberately left out: it isn't
// one of the four chips the proposal calls out.
const STATUS_FILTERS: { value: EventType; label: string }[] = [
  { value: "sailing", label: "At Sea" },
  { value: "at_port", label: "At Port" },
  { value: "eta_destination", label: "ETA to Destination" },
  { value: "arrived_destination", label: "Arrived at Destination" },
];

// Main dashboard (Section 3.4) - the app's home page ("/"). Combines the Active/Archived tabs
// (Section 3.7/3.8), free-text search (6.A), status filter chips (6.D), and the vessel table
// into one view, all driven by a single `refresh()` call whenever any of their state changes.
//
// Navigation and the user menu are no longer part of this page: they live in the shared site
// header (see components/SiteHeader.tsx), which is why this file is now only about vessels.
export default function DashboardPage() {
  const [view, setView] = useState<View>("active");
  const [vessels, setVessels] = useState<Vessel[]>([]);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<EventType | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Debounce the raw input into a separate value so `refresh` (and the effect below) only
  // change identity 250ms after typing stops, instead of on every keystroke.
  useEffect(() => {
    const handle = setTimeout(() => setDebouncedSearch(search), 250);
    return () => clearTimeout(handle);
  }, [search]);

  const refresh = useCallback(async () => {
    try {
      const data = await listVessels({
        archived: view === "archived",
        query: debouncedSearch || undefined,
        // The status chips only apply to the Active view - Archived has its own separate
        // concept of "what happened to this vessel" that doesn't fit the same four chips.
        status: view === "active" && statusFilter ? statusFilter : undefined,
      });
      setVessels(data);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not reach the API — is the backend running?");
    } finally {
      setLoading(false);
    }
  }, [view, debouncedSearch, statusFilter]);

  // Single effect drives both the initial load and the periodic auto-refresh, and re-fires
  // whenever `refresh` itself changes identity (i.e. whenever view/search/statusFilter change) -
  // this refetches once for the state change and correctly resets the interval timer, rather
  // than needing two separate effects that could disagree about which state is current.
  useEffect(() => {
    void (async () => {
      setLoading(true);
      await refresh();
    })();
    const interval = setInterval(() => refresh(), DASHBOARD_REFRESH_MS);
    return () => clearInterval(interval);
  }, [refresh]);

  return (
    <>
      <PageBanner
        title="Vessel Monitoring Dashboard"
        subtitle="Multi-port operations · Live view · Auto-refreshed every 5 minutes"
        actions={
          view === "active" && (
            <button
              onClick={() => setShowAddModal(true)}
              // White-on-orange rather than the usual solid-orange primary button, since it sits
              // on the orange banner where an orange button would disappear.
              className="inline-flex items-center gap-2 rounded-sm bg-white px-5 py-2.5 text-sm font-bold text-brand transition-colors hover:bg-brand-tint"
            >
              + Add Vessel
            </button>
          )
        }
      />

      <Shell className="py-7">
        <Panel>
          <div className="flex flex-wrap items-center justify-between gap-4 border-b border-rule px-5 pt-1">
            <div className="flex">
              <TabButton active={view === "active"} onClick={() => setView("active")}>
                Active
              </TabButton>
              <TabButton active={view === "archived"} onClick={() => setView("archived")}>
                Archived
              </TabButton>
            </div>
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search vessel, IMO, port…"
              className={`${inputClass} mb-2 w-72`}
            />
          </div>

          {view === "active" && (
            <div className="flex flex-wrap gap-2 border-b border-rule px-5 py-3">
              <Chip active={statusFilter === null} onClick={() => setStatusFilter(null)}>
                All
              </Chip>
              {STATUS_FILTERS.map(({ value, label }) => (
                <Chip key={value} active={statusFilter === value} onClick={() => setStatusFilter(value)}>
                  <span className={`mr-1.5 inline-block h-2 w-2 rounded-full ${statusMeta(value).dot}`} />
                  {label}
                </Chip>
              ))}
            </div>
          )}

          {error && <ErrorBar>{error}</ErrorBar>}

          {loading ? <EmptyState>Loading vessels…</EmptyState> : <VesselTable vessels={vessels} />}

          <PanelFooter>
            {view === "active" ? (
              <span>
                Showing {vessels.length} monitored vessel{vessels.length === 1 ? "" : "s"} · Destination is
                optional, set per-vessel at registration
              </span>
            ) : (
              <span>
                Showing {vessels.length} archived vessel{vessels.length === 1 ? "" : "s"} · History stays
                available for reference · Archiving is one-way — re-register a vessel to resume tracking
              </span>
            )}
            <span>Click any vessel row to open its full movement history and timeline</span>
          </PanelFooter>
        </Panel>
      </Shell>

      {showAddModal && <AddVesselModal onClose={() => setShowAddModal(false)} onImported={refresh} />}
    </>
  );
}
