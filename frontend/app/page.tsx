"use client";

import { useCallback, useEffect, useState } from "react";
import AddVesselModal from "./components/AddVesselModal";
import VesselTable from "./components/VesselTable";
import { ApiError, listVessels, Vessel } from "@/lib/api";

// Matches Figure 2's "Auto-refreshed every 5 minutes" caption.
const DASHBOARD_REFRESH_MS = 5 * 60 * 1000;

export default function DashboardPage() {
  const [vessels, setVessels] = useState<Vessel[]>([]);
  const [showAddModal, setShowAddModal] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const data = await listVessels();
      setVessels(data);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not reach the API — is the backend running?");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void (async () => {
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
            <button
              onClick={() => setShowAddModal(true)}
              className="rounded-md bg-[#1f8a4c] px-4 py-2 text-sm font-medium text-white hover:bg-[#1a7642]"
            >
              + Add
            </button>
          </div>
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
          <span>
            Showing {vessels.length} monitored vessel{vessels.length === 1 ? "" : "s"} · Auto-refreshed every 5
            minutes · Destination is optional, set per-vessel at registration
          </span>
          <span>Click any vessel row to open its full movement history and timeline</span>
        </div>
      </div>

      {showAddModal && (
        <AddVesselModal onClose={() => setShowAddModal(false)} onImported={refresh} />
      )}
    </div>
  );
}
