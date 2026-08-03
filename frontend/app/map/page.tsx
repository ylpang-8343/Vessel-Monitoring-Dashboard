"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import UserMenu from "@/app/components/UserMenu";
import { ApiError, listVessels, Vessel } from "@/lib/api";

// Leaflet touches `window`/`document` at module load time, which breaks Next.js's server
// render - load the map client-side only, same as any other browser-only widget.
const VesselMap = dynamic(() => import("@/app/components/VesselMap"), {
  ssr: false,
  loading: () => (
    <div className="flex h-[520px] w-full items-center justify-center rounded-lg border border-zinc-200 text-sm text-zinc-500 dark:border-zinc-800">
      Loading map…
    </div>
  ),
});

const MAP_REFRESH_MS = 5 * 60 * 1000;

export default function MapPage() {
  const [vessels, setVessels] = useState<Vessel[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const data = await listVessels({ archived: false });
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
      setLoading(true);
      await refresh();
    })();
    const interval = setInterval(() => refresh(), MAP_REFRESH_MS);
    return () => clearInterval(interval);
  }, [refresh]);

  return (
    <div className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">
      <div className="overflow-hidden rounded-lg border border-zinc-200 shadow-sm dark:border-zinc-800">
        <div className="flex items-center justify-between bg-[#0b3d5c] px-6 py-4">
          <div>
            <h1 className="text-lg font-semibold text-white">Map View</h1>
            <p className="text-xs text-white/70">Live vessel positions across all destinations</p>
          </div>
          <div className="flex items-center gap-3">
            <UserMenu />
            <Link
              href="/"
              className="rounded-md bg-white/10 px-3 py-1.5 text-sm font-medium text-white hover:bg-white/20"
            >
              Back to Dashboard
            </Link>
          </div>
        </div>

        <div className="bg-white p-6 dark:bg-zinc-900">
          {error && (
            <div className="mb-4 rounded-md border border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-800">
              {error}
            </div>
          )}
          {loading ? (
            <div className="flex h-[520px] items-center justify-center text-sm text-zinc-500">
              Loading vessels…
            </div>
          ) : (
            <VesselMap vessels={vessels} />
          )}
        </div>
      </div>
    </div>
  );
}
