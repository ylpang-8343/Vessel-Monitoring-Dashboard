"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useState } from "react";
import { ErrorBar, PageBanner, Panel, PanelFooter, Shell } from "@/app/components/ui";
import { ApiError, listVessels, Vessel } from "@/lib/api";

// Leaflet touches `window`/`document` at module load time, which breaks Next.js's server
// render - load the map client-side only, same as any other browser-only widget.
const VesselMap = dynamic(() => import("@/app/components/VesselMap"), {
  ssr: false,
  loading: () => (
    <div className="flex h-[520px] w-full items-center justify-center border border-rule text-sm text-muted">
      Loading map…
    </div>
  ),
});

const MAP_REFRESH_MS = 5 * 60 * 1000;

// Page shell for Map View (Section 6.B) at "/map" - fetches the active-vessel list itself and
// hands it to the (dynamically-loaded) VesselMap component to render. Reachable by any logged-in
// user, not just admins - unlike /settings, this route has no extra role check.
export default function MapPage() {
  const [vessels, setVessels] = useState<Vessel[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      // Only active vessels are plotted - archived ones are no longer "live positions".
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
    <>
      <PageBanner title="Map View" subtitle="Live vessel positions across all destinations" />

      <Shell className="py-7">
        <Panel>
          {error && <ErrorBar>{error}</ErrorBar>}

          <div className="p-5">
            {loading ? (
              <div className="flex h-[520px] items-center justify-center text-sm text-muted">
                Loading vessels…
              </div>
            ) : (
              // Rendered even with no vessels: the destination-port markers alone still make a
              // useful map, so an empty-state message here would be a downgrade.
              <VesselMap vessels={vessels} />
            )}
          </div>

          <PanelFooter>
            <span>
              Showing {vessels.length} active vessel{vessels.length === 1 ? "" : "s"} · Positions come from the
              tracking sources&apos; reported location, not live AIS coordinates
            </span>
            <span>Click any marker for that vessel&apos;s latest event</span>
          </PanelFooter>
        </Panel>
      </Shell>
    </>
  );
}
