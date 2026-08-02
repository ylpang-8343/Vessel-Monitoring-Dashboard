"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import AddVesselModal from "./components/AddVesselModal";
import VesselTable from "./components/VesselTable";
import UserMenu from "./components/UserMenu";
import { useAuth } from "./components/AuthProvider";
import { ApiError, listVessels, Vessel } from "@/lib/api";

// Matches Figure 2's "Auto-refreshed every 5 minutes" caption.
const DASHBOARD_REFRESH_MS = 5 * 60 * 1000;

type View = "active" | "archived";

export default function DashboardPage() {
  const { user } = useAuth();
  const [view, setView] = useState<View>("active");
  const [vessels, setVessels] = useState<Vessel[]>([]);
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
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
      const data = await listVessels({ archived: view === "archived", query: debouncedSearch || undefined });
      setVessels(data);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not reach the API — is the backend running?");
    } finally {
      setLoading(false);
    }
  }, [view, debouncedSearch]);

  useEffect(() => {
    void (async () => {
      setLoading(true);
      await refresh();
    })();
    const interval = setInterval(() => refresh(), DASHBOARD_REFRESH_MS);
    return () => clearInterval(interval);
  }, [refresh]);

  return (
    <div className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">
      <div className="overflow-hidden rounded-lg border border-zinc-200 shadow-sm dark:border-zinc-800">
        <div className="flex items-center justify-between bg-[#0b3d5c] px-6 py-4">
          <div>
            <h1 className="text-lg font-semibold text-white">Vessel Monitoring Dashboard</h1>
            <p className="text-xs text-white/70">Multi-Port Operations · Live View</p>
          </div>
          <div className="flex items-center gap-3">
            <UserMenu />
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
            placeholder="Search vessel, IMO, port…"
            className="mb-2 w-64 rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-800"
          />
        </div>

        {error && (
          <div className="border-b border-amber-200 bg-amber-50 px-6 py-2 text-sm text-amber-800">{error}</div>
        )}

        <div className="bg-white dark:bg-zinc-900">
          {loading ? (
            <div className="px-6 py-16 text-center text-sm text-zinc-500">Loading vessels…</div>
          ) : (
            <VesselTable vessels={vessels} />
          )}
        </div>

        <div className="flex items-center justify-between border-t border-zinc-200 bg-zinc-50 px-6 py-3 text-xs text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900">
          {view === "active" ? (
            <span>
              Showing {vessels.length} monitored vessel{vessels.length === 1 ? "" : "s"} · Auto-refreshed every 5
              minutes · Destination is optional, set per-vessel at registration
            </span>
          ) : (
            <span>
              Showing {vessels.length} archived vessel{vessels.length === 1 ? "" : "s"} · History stays available
              for reference · Archiving is one-way — re-register a vessel to resume tracking
            </span>
          )}
          <span>Click any vessel row to open its full movement history and timeline</span>
        </div>
      </div>

      {showAddModal && (
        <AddVesselModal onClose={() => setShowAddModal(false)} onImported={refresh} />
      )}
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
