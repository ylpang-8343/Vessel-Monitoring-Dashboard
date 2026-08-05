"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import UserMenu from "@/app/components/UserMenu";
import VesselTable from "@/app/components/VesselTable";
import { ApiError, downloadReportExcel, downloadReportPdf, getReportSummary, ReportSummary } from "@/lib/api";

const REPORTS_REFRESH_MS = 5 * 60 * 1000;

// Reports page (Section 9 Phase 4 / Section 7) at "/reports" - the same three vessel categories
// as the Excel/PDF exports, shown on-screen first so a user can sanity-check what they're about
// to download. Reachable by any logged-in user, not just admins (unlike Settings).
export default function ReportsPage() {
  const [summary, setSummary] = useState<ReportSummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState<"xlsx" | "pdf" | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await getReportSummary();
      setSummary(data);
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
    const interval = setInterval(() => refresh(), REPORTS_REFRESH_MS);
    return () => clearInterval(interval);
  }, [refresh]);

  async function handleExport(format: "xlsx" | "pdf") {
    setExporting(format);
    setExportError(null);
    try {
      await (format === "xlsx" ? downloadReportExcel() : downloadReportPdf());
    } catch (err) {
      setExportError(err instanceof ApiError ? err.message : "Export failed");
    } finally {
      setExporting(null);
    }
  }

  return (
    <div className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">
      <div className="overflow-hidden rounded-lg border border-zinc-200 shadow-sm dark:border-zinc-800">
        <div className="flex items-center justify-between bg-[#0b3d5c] px-6 py-4">
          <div>
            <h1 className="text-lg font-semibold text-white">Reports</h1>
            <p className="text-xs text-white/70">Active vessels · ETA to Destination · Arrived at Destination</p>
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

        <div className="flex flex-wrap items-center gap-3 border-b border-zinc-200 bg-white px-6 py-3 dark:border-zinc-800 dark:bg-zinc-900">
          <button
            onClick={() => handleExport("xlsx")}
            disabled={exporting !== null}
            className="rounded-md bg-[#1f8a4c] px-4 py-2 text-sm font-medium text-white hover:bg-[#1a7642] disabled:opacity-50"
          >
            {exporting === "xlsx" ? "Exporting…" : "Export to Excel"}
          </button>
          <button
            onClick={() => handleExport("pdf")}
            disabled={exporting !== null}
            className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium hover:bg-zinc-50 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-800"
          >
            {exporting === "pdf" ? "Exporting…" : "Export to PDF"}
          </button>
          {exportError && <span className="text-sm text-red-600">{exportError}</span>}
          {summary && (
            <span className="ml-auto text-xs text-zinc-500">
              Generated {new Date(summary.generated_at).toLocaleString()}
            </span>
          )}
        </div>

        {error && (
          <div className="border-b border-amber-200 bg-amber-50 px-6 py-2 text-sm text-amber-800">{error}</div>
        )}

        <div className="bg-white dark:bg-zinc-900">
          {loading || !summary ? (
            <div className="px-6 py-16 text-center text-sm text-zinc-500">Loading report…</div>
          ) : (
            <>
              <ReportSection title="Active Vessels" vessels={summary.active} />
              <ReportSection title="ETA to Destination" vessels={summary.eta_to_destination} />
              <ReportSection title="Arrived at Destination" vessels={summary.arrived_at_destination} />
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function ReportSection({ title, vessels }: { title: string; vessels: ReportSummary["active"] }) {
  return (
    <div className="border-b border-zinc-200 last:border-b-0 dark:border-zinc-800">
      <h2 className="px-6 pt-4 text-sm font-semibold text-zinc-700 dark:text-zinc-300">
        {title} ({vessels.length})
      </h2>
      {/* Distinct from VesselTable's default "no vessels at all" message (which points at a
          "+ Add" button that doesn't even exist on this page) - an empty category here just
          means no vessel currently matches it, not that nothing is registered. */}
      <VesselTable vessels={vessels} emptyMessage="No vessels in this category right now." />
    </div>
  );
}
