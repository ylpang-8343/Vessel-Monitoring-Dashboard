"use client";

import { useCallback, useEffect, useState } from "react";
import AddBookingModal from "@/app/components/AddBookingModal";
import BookingTable from "@/app/components/BookingTable";
import { bookingStatusMeta } from "@/app/components/BookingStatusDot";
import {
  Chip,
  EmptyState,
  ErrorBar,
  PageBanner,
  Panel,
  PanelFooter,
  Shell,
  TabButton,
  inputClass,
} from "@/app/components/ui";
import { ApiError, Booking, BookingStatus, listBookings } from "@/lib/api";

// Same auto-refresh cadence as the vessel dashboard (Section 3.4's "Auto-refreshed every 5
// minutes" convention, applied consistently across both modules).
const CONTAINERS_REFRESH_MS = 5 * 60 * 1000;

type View = "active" | "archived";

// All five BookingStatus values are shown as filter chips here (unlike the vessel dashboard,
// which deliberately leaves "Sailed from Destination" off its four Section 6.D chips) - Section
// 4's own mockup (Figure 3a) shows all five stages as chips: All / Booking Confirmed / Loaded /
// In Transit / Discharged / Gate Out.
const STATUS_FILTERS: { value: BookingStatus; label: string }[] = [
  { value: "booking_confirmed", label: "Booking Confirmed" },
  { value: "loaded", label: "Loaded" },
  { value: "in_transit", label: "In Transit" },
  { value: "discharged", label: "Discharged" },
  { value: "gate_out", label: "Gate Out" },
];

// Container/Booking Tracking module (Section 4) at "/containers" - structured the same way as
// the main vessel dashboard per the proposal's own wording: Active/Archived tabs, free-text
// search, status filter chips, and the booking table, all driven by one refresh() call.
export default function ContainersPage() {
  const [view, setView] = useState<View>("active");
  const [bookings, setBookings] = useState<Booking[]>([]);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<BookingStatus | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const handle = setTimeout(() => setDebouncedSearch(search), 250);
    return () => clearTimeout(handle);
  }, [search]);

  const refresh = useCallback(async () => {
    try {
      const data = await listBookings({
        archived: view === "archived",
        query: debouncedSearch || undefined,
        status: view === "active" && statusFilter ? statusFilter : undefined,
      });
      setBookings(data);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not reach the API — is the backend running?");
    } finally {
      setLoading(false);
    }
  }, [view, debouncedSearch, statusFilter]);

  useEffect(() => {
    void (async () => {
      setLoading(true);
      await refresh();
    })();
    const interval = setInterval(() => refresh(), CONTAINERS_REFRESH_MS);
    return () => clearInterval(interval);
  }, [refresh]);

  return (
    <>
      <PageBanner
        title="Container / Booking Tracking"
        subtitle="Companion module · Cargo movement status across carrier booking records"
        actions={
          view === "active" && (
            <button
              onClick={() => setShowAddModal(true)}
              className="inline-flex items-center gap-2 rounded-sm bg-white px-5 py-2.5 text-sm font-bold text-brand transition-colors hover:bg-brand-tint"
            >
              + Add Booking
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
              placeholder="Search container / booking no…"
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
                  <span className={`mr-1.5 inline-block h-2 w-2 rounded-full ${bookingStatusMeta(value).dot}`} />
                  {label}
                </Chip>
              ))}
            </div>
          )}

          {error && <ErrorBar>{error}</ErrorBar>}

          {loading ? <EmptyState>Loading bookings…</EmptyState> : <BookingTable bookings={bookings} />}

          <PanelFooter>
            {view === "active" ? (
              <span>
                Showing {bookings.length} tracked booking{bookings.length === 1 ? "" : "s"}/container
                {bookings.length === 1 ? "" : "s"} · Current Location and Last Event sourced from carrier
                booking records, not vessel position data
              </span>
            ) : (
              <span>
                Showing {bookings.length} archived booking{bookings.length === 1 ? "" : "s"} · History stays
                available for reference
              </span>
            )}
            <span>Click any row to open its full movement history and timeline</span>
          </PanelFooter>
        </Panel>
      </Shell>

      {showAddModal && <AddBookingModal onClose={() => setShowAddModal(false)} onImported={refresh} />}
    </>
  );
}
