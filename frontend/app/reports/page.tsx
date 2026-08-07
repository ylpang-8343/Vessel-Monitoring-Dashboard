"use client";

import { useCallback, useEffect, useState } from "react";
import VesselTable from "@/app/components/VesselTable";
import { EmptyState, ErrorBar, PageBanner, Panel, PanelHeader, Shell } from "@/app/components/ui";
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
    <>
      <PageBanner
        title="Reports"
        subtitle="Active vessels · ETA to Destination · Arrived at Destination"
        actions={
          <>
            <button
              onClick={() => handleExport("xlsx")}
              disabled={exporting !== null}
              className="inline-flex items-center gap-2 rounded-sm bg-white px-5 py-2.5 text-sm font-bold text-brand transition-colors hover:bg-brand-tint disabled:opacity-60"
            >
              {exporting === "xlsx" ? "Exporting…" : "Export to Excel"}
            </button>
            <button
              onClick={() => handleExport("pdf")}
              disabled={exporting !== null}
              className="inline-flex items-center gap-2 rounded-sm border border-white/70 px-5 py-2.5 text-sm font-bold text-white transition-colors hover:bg-white/15 disabled:opacity-60"
            >
              {exporting === "pdf" ? "Exporting…" : "Export to PDF"}
            </button>
          </>
        }
      />

      <Shell className="space-y-5 py-7">
        {exportError && (
          <Panel>
            <ErrorBar>{exportError}</ErrorBar>
          </Panel>
        )}
        {error && (
          <Panel>
            <ErrorBar>{error}</ErrorBar>
          </Panel>
        )}

        {loading || !summary ? (
          <Panel>
            <EmptyState>Loading report…</EmptyState>
          </Panel>
        ) : (
          <>
            {/* One panel per category rather than three sections stacked inside a single card -
                each is a self-contained block in the same way the source site lays its content
                out in separate modules. */}
            <ReportSection
              title="Active Vessels"
              vessels={summary.active}
              generatedAt={summary.generated_at}
            />
            <ReportSection title="ETA to Destination" vessels={summary.eta_to_destination} />
            <ReportSection title="Arrived at Destination" vessels={summary.arrived_at_destination} />
          </>
        )}
      </Shell>
    </>
  );
}

function ReportSection({
  title,
  vessels,
  generatedAt,
}: {
  title: string;
  vessels: ReportSummary["active"];
  /** Only passed to the first section, so the "generated at" stamp appears once on the page
   * rather than being repeated identically above all three tables. */
  generatedAt?: string;
}) {
  return (
    <Panel>
      <PanelHeader
        title={`${title} (${vessels.length})`}
        actions={
          generatedAt && (
            <span className="text-xs text-muted">Generated {new Date(generatedAt).toLocaleString()}</span>
          )
        }
      />
      {/* Distinct from VesselTable's default "no vessels at all" message (which points at a
          "+ Add" button that doesn't even exist on this page) - an empty category here just
          means no vessel currently matches it, not that nothing is registered. */}
      <VesselTable vessels={vessels} emptyMessage="No vessels in this category right now." />
    </Panel>
  );
}
