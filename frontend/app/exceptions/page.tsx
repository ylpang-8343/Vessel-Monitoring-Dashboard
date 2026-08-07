"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import ExceptionBadge, { exceptionMeta } from "@/app/components/ExceptionBadge";
import {
  Chip,
  EmptyState,
  ErrorBar,
  NoticeBar,
  PageBanner,
  Panel,
  PanelFooter,
  Shell,
  theadClass,
} from "@/app/components/ui";
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
    <>
      <PageBanner
        title="Exception Alerts"
        subtitle="Delays · Long port stays · Unexpected port calls"
      />

      <Shell className="py-7">
        <Panel>
          <NoticeBar>
            Detection is rule-based, not model-guessed — every alert is arithmetic against a
            source-reported ETA or a configured threshold, so you can check it against the vessel&apos;s own
            timeline. Route-deviation alerts aren&apos;t included: detecting a deviation needs a planned
            route to compare against, which neither this app nor AIS-style tracking data provides
            (Section 3.10&apos;s reasoning).
          </NoticeBar>

          <div className="flex flex-wrap gap-2 border-b border-rule px-5 py-3">
            <Chip active={kindFilter === null} onClick={() => setKindFilter(null)}>
              All
            </Chip>
            {KIND_FILTERS.map((kind) => (
              <Chip key={kind} active={kindFilter === kind} onClick={() => setKindFilter(kind)}>
                <span className={`mr-1.5 inline-block h-2 w-2 rounded-full ${exceptionMeta(kind).dot}`} />
                {exceptionMeta(kind).label}
              </Chip>
            ))}
          </div>

          {error && <ErrorBar>{error}</ErrorBar>}

          {loading ? (
            <EmptyState>Loading exceptions…</EmptyState>
          ) : exceptions.length === 0 ? (
            <EmptyState>
              No exceptions detected. Vessels are arriving within their reported ETAs and staying within
              the configured port-stay threshold.
            </EmptyState>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[860px] text-sm">
                <thead className={theadClass}>
                  <tr>
                    <th className="px-5 py-3">Detected</th>
                    <th className="px-5 py-3">Vessel</th>
                    <th className="px-5 py-3">Type</th>
                    <th className="px-5 py-3">Detail</th>
                  </tr>
                </thead>
                <tbody>
                  {exceptions.map((exception) => (
                    <tr
                      key={exception.id}
                      onClick={() => router.push(`/vessels/${exception.vessel_imo}`)}
                      className="cursor-pointer border-b border-rule last:border-b-0 hover:bg-brand-tint"
                    >
                      <td className="whitespace-nowrap px-5 py-3 text-muted">
                        {new Date(exception.detected_at).toLocaleString()}
                      </td>
                      <td className="px-5 py-3">
                        <span className="font-bold text-ink">{exception.vessel_name}</span>
                        <span className="ml-2 text-xs text-muted">IMO {exception.vessel_imo}</span>
                      </td>
                      <td className="px-5 py-3">
                        <ExceptionBadge kind={exception.kind} />
                      </td>
                      <td className="px-5 py-3">{exception.message}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <PanelFooter>
            <span>
              Showing {exceptions.length} exception{exceptions.length === 1 ? "" : "s"} · Checked on every
              tracking poll · Each distinct exception alerts once
            </span>
            <span>Click any row to open that vessel&apos;s history</span>
          </PanelFooter>
        </Panel>
      </Shell>
    </>
  );
}
