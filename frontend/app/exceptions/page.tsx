"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import UserMenu from "@/app/components/UserMenu";
import ExceptionBadge, { exceptionMeta } from "@/app/components/ExceptionBadge";
import { ApiError, ExceptionKind, listExceptions, VesselException } from "@/lib/api";

// Same auto-refresh cadence as the dashboard, for consistency across the app's live views.
const EXCEPTIONS_REFRESH_MS = 5 * 60 * 1000;

// The three exception kinds the app can actually ground in data it holds (Section 7). Route
// deviation is deliberately absent - see backend models.py's ExceptionKind docstring.
const KIND_FILTERS: ExceptionKind[] = ["delayed", "long_port_stay", "unexpected_port_call"];

// Exceptions page (Section 7's "AI Exception Alerts") at "/exceptions" - one place to see every
// flagged vessel, structured like the dashboard (filter chips + table + row click through to the
// vessel). Reachable by any logged-in user, not just admins.
export default function ExceptionsPage() {
  const router = useRouter();
  const [exceptions, setExceptions] = useState<VesselException[]>([]);
  const [kindFilter, setKindFilter] = useState<ExceptionKind | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      setExceptions(await listExceptions(kindFilter ?? undefined));
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not reach the API — is the backend running?");
    } finally {
      setLoading(false);
    }
  }, [kindFilter]);

  useEffect(() => {
    void (async () => {
      setLoading(true);
      await refresh();
    })();
    const interval = setInterval(() => refresh(), EXCEPTIONS_REFRESH_MS);
    return () => clearInterval(interval);
  }, [refresh]);

  return (
    <div className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">
      <div className="overflow-hidden rounded-lg border border-zinc-200 shadow-sm dark:border-zinc-800">
        <div className="flex items-center justify-between bg-[#0b3d5c] px-6 py-4">
          <div>
            <h1 className="text-lg font-semibold text-white">Exception Alerts</h1>
            <p className="text-xs text-white/70">Delays · Long port stays · Unexpected port calls</p>
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

        <div className="bg-amber-50 px-6 py-3 text-xs text-amber-800 dark:bg-amber-950 dark:text-amber-300">
          Detection is rule-based, not model-guessed — every alert is arithmetic against a
          source-reported ETA or a configured threshold, so you can check it against the vessel&apos;s own
          timeline. Route-deviation alerts aren&apos;t included: detecting a deviation needs a planned
          route to compare against, which neither this app nor AIS-style tracking data provides
          (Section 3.10&apos;s reasoning).
        </div>

        <div className="flex flex-wrap gap-2 border-b border-zinc-200 bg-white px-6 py-3 dark:border-zinc-800 dark:bg-zinc-900">
          <FilterChip active={kindFilter === null} onClick={() => setKindFilter(null)}>
            All
          </FilterChip>
          {KIND_FILTERS.map((kind) => (
            <FilterChip key={kind} active={kindFilter === kind} onClick={() => setKindFilter(kind)}>
              <span className={`mr-1.5 inline-block h-2 w-2 rounded-full ${exceptionMeta(kind).dot}`} />
              {exceptionMeta(kind).label}
            </FilterChip>
          ))}
        </div>

        {error && (
          <div className="border-b border-amber-200 bg-amber-50 px-6 py-2 text-sm text-amber-800">{error}</div>
        )}

        <div className="bg-white dark:bg-zinc-900">
          {loading ? (
            <div className="px-6 py-16 text-center text-sm text-zinc-500">Loading exceptions…</div>
          ) : exceptions.length === 0 ? (
            <div className="px-6 py-16 text-center text-sm text-zinc-500">
              No exceptions detected. Vessels are arriving within their reported ETAs and staying within
              the configured port-stay threshold.
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead className="border-b border-zinc-200 text-left text-xs uppercase tracking-wide text-zinc-500 dark:border-zinc-800">
                <tr>
                  <th className="px-6 py-3">Detected</th>
                  <th className="px-6 py-3">Vessel</th>
                  <th className="px-6 py-3">Type</th>
                  <th className="px-6 py-3">Detail</th>
                </tr>
              </thead>
              <tbody>
                {exceptions.map((exception) => (
                  <tr
                    key={exception.id}
                    onClick={() => router.push(`/vessels/${exception.vessel_imo}`)}
                    className="cursor-pointer border-b border-zinc-100 last:border-b-0 hover:bg-zinc-50 dark:border-zinc-800 dark:hover:bg-zinc-900"
                  >
                    <td className="whitespace-nowrap px-6 py-3 text-zinc-500">
                      {new Date(exception.detected_at).toLocaleString()}
                    </td>
                    <td className="px-6 py-3">
                      <span className="font-medium">{exception.vessel_name}</span>
                      <span className="ml-2 text-xs text-zinc-500">IMO {exception.vessel_imo}</span>
                    </td>
                    <td className="px-6 py-3">
                      <ExceptionBadge kind={exception.kind} />
                    </td>
                    <td className="px-6 py-3">{exception.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="flex items-center justify-between border-t border-zinc-200 bg-zinc-50 px-6 py-3 text-xs text-zinc-500 dark:border-zinc-800 dark:bg-zinc-900">
          <span>
            Showing {exceptions.length} exception{exceptions.length === 1 ? "" : "s"} · Checked on every
            tracking poll · Each distinct exception alerts once
          </span>
          <span>Click any row to open that vessel&apos;s history</span>
        </div>
      </div>
    </div>
  );
}

// One filter pill, matching the dashboard's chip styling (Section 6.D's pattern reused).
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
