"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import AddBookingModal from "@/app/components/AddBookingModal";
import BookingTable from "@/app/components/BookingTable";
import UserMenu from "@/app/components/UserMenu";
import { useAuth } from "@/app/components/AuthProvider";
import { bookingStatusMeta } from "@/app/components/BookingStatusDot";
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
  const { user } = useAuth();
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
    <div className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">
      <div className="overflow-hidden rounded-lg border border-zinc-200 shadow-sm dark:border-zinc-800">
        <div className="flex items-center justify-between bg-[#0b3d5c] px-6 py-4">
          <div>
            <h1 className="text-lg font-semibold text-white">Container / Booking Tracking</h1>
            <p className="text-xs text-white/70">Companion Module · Cargo movement status</p>
          </div>
          <div className="flex items-center gap-3">
            <UserMenu />
            <Link href="/" className="rounded-md bg-white/10 px-3 py-2 text-sm font-medium text-white hover:bg-white/20">
              Vessel Dashboard
            </Link>
            {user?.role === "admin" && (
              <Link
                href="/settings"
                className="rounded-md bg-white/10 px-3 py-2 text-sm font-medium text-white hover:bg-white/20"
              >
                Settings
              </Link>
            )}
            {view === "active" && (
              <button
                onClick={() => setShowAddModal(true)}
                className="rounded-md bg-[#1f8a4c] px-4 py-2 text-sm font-medium text-white hover:bg-[#1a7642]"
              >
                + Add
              </button>
            )}
          </div>
        </div>

        <div className="flex items-center justify-between gap-4 border-b border-zinc-200 bg-white px-6 pt-3 dark:border-zinc-800 dark:bg-zinc-900">
          <div className="flex gap-2">
            <ViewTab active={view === "active"} onClick={() => setView("active")}>
              Active
            </ViewTab>
            <ViewTab active={view === "archived"} onClick={() => setView("archived")}>
              Archived
            </ViewTab>
          </div>
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search container / booking no…"
            className="mb-2 w-64 rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-800"
          />
        </div>

        {view === "active" && (
          <div className="flex flex-wrap gap-2 border-b border-zinc-200 bg-white px-6 py-3 dark:border-zinc-800 dark:bg-zinc-900">
            <FilterChip active={statusFilter === null} onClick={() => setStatusFilter(null)}>
              All
            </FilterChip>
            {STATUS_FILTERS.map(({ value, label }) => (
              <FilterChip key={value} active={statusFilter === value} onClick={() => setStatusFilter(value)}>
                <span className={`mr-1.5 inline-block h-2 w-2 rounded-full ${bookingStatusMeta(value).dot}`} />
                {label}
              </FilterChip>
            ))}
          </div>
        )}

        {error && (
          <div className="border-b border-amber-200 bg-amber-50 px-6 py-2 text-sm text-amber-800">{error}</div>
        )}

        <div className="bg-white dark:bg-zinc-900">
          {loading ? (
            <div className="px-6 py-16 text-center text-sm text-zinc-500">Loading bookings…</div>
          ) : (
            <BookingTable bookings={bookings} />
          )}
        </div>

        <div className="flex items-center justify-between border-t border-zinc-200 bg-zinc-50 px-6 py-3 text-xs text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900">
          {view === "active" ? (
            <span>
              Showing {bookings.length} tracked booking{bookings.length === 1 ? "" : "s"}/container
              {bookings.length === 1 ? "" : "s"} · Current Location and Last Event sourced from carrier booking
              records, not vessel position data
            </span>
          ) : (
            <span>
              Showing {bookings.length} archived booking{bookings.length === 1 ? "" : "s"} · History stays
              available for reference
            </span>
          )}
          <span>Click any row to open its full movement history and timeline</span>
        </div>
      </div>

      {showAddModal && <AddBookingModal onClose={() => setShowAddModal(false)} onImported={refresh} />}
    </div>
  );
}

function ViewTab({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`rounded-t-md px-4 py-2 text-sm font-medium ${
        active
          ? "border-b-2 border-[#0b3d5c] text-[#0b3d5c] dark:text-white"
          : "text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300"
      }`}
    >
      {children}
    </button>
  );
}

function FilterChip({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-medium ${
        active
          ? "border-[#0b3d5c] bg-[#0b3d5c] text-white"
          : "border-zinc-300 text-zinc-600 hover:bg-zinc-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
      }`}
    >
      {children}
    </button>
  );
}
