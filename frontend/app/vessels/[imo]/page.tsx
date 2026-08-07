"use client";

import { use, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  ApiError,
  archiveVessel,
  generateVoyageSummary,
  getAiStatus,
  getVesselHistory,
  getVoyageSummary,
  removeVessel,
  VesselHistory,
  VoyageSummary,
} from "@/lib/api";
import StatusDot, { statusMeta } from "@/app/components/StatusDot";
import ExceptionBadge from "@/app/components/ExceptionBadge";
import UserMenu from "@/app/components/UserMenu";

const HISTORY_REFRESH_MS = 30 * 1000;

type ConfirmAction = "archive" | "remove" | null;

// Single-vessel history page (Section 3.5) at "/vessels/[imo]" - the full movement timeline
// plus the manual archive/remove actions (Section 3.8). `params` is a Promise here (not a plain
// object) per this Next.js version's App Router API - see frontend/AGENTS.md - unwrapped with
// React's `use()`.
export default function VesselHistoryPage({ params }: { params: Promise<{ imo: string }> }) {
  const { imo } = use(params);
  const router = useRouter();
  const [history, setHistory] = useState<VesselHistory | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [confirming, setConfirming] = useState<ConfirmAction>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actioning, setActioning] = useState(false);
  // Phase 6 AI voyage summary (Section 7). Loaded alongside the history; `aiConfigured` decides
  // whether the panel offers a Generate button or explains that summaries are unavailable.
  const [summary, setSummary] = useState<VoyageSummary | null>(null);
  const [aiConfigured, setAiConfigured] = useState(false);

  const refresh = useCallback(async () => {
    try {
      // Fetched together so one round of state updates covers the whole page. The summary is a
      // plain read - it never triggers generation, so opening this page never spends an API call.
      const [data, cachedSummary, aiStatus] = await Promise.all([
        getVesselHistory(imo),
        getVoyageSummary(imo).catch(() => null),
        getAiStatus().catch(() => ({ configured: false })),
      ]);
      setHistory(data);
      setSummary(cachedSummary);
      setAiConfigured(aiStatus.configured);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not reach the API");
    } finally {
      setLoading(false);
    }
  }, [imo]);

  useEffect(() => {
    void (async () => {
      await refresh();
    })();
    const interval = setInterval(() => refresh(), HISTORY_REFRESH_MS);
    return () => clearInterval(interval);
  }, [refresh]);

  /** Manual archive (Section 3.8) - a two-step confirm (see the `confirming` state / ConfirmBar
   * below) since it's a one-way action. */
  async function handleArchive() {
    setActioning(true);
    setActionError(null);
    try {
      await archiveVessel(imo);
      setConfirming(null);
      await refresh();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Failed to archive vessel");
    } finally {
      setActioning(false);
    }
  }

  /** Manual permanent delete (Section 3.8) - unlike archive, this navigates away afterwards
   * since the vessel (and this page's own data) no longer exists. */
  async function handleRemove() {
    setActioning(true);
    setActionError(null);
    try {
      await removeVessel(imo);
      router.push("/");
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Failed to remove vessel");
      setActioning(false);
    }
  }

  if (loading) {
    return <div className="mx-auto max-w-4xl px-4 py-16 text-center text-sm text-zinc-500">Loading…</div>;
  }

  if (error || !history) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-16 text-center">
        <p className="text-sm text-red-600">{error ?? "Vessel not found"}</p>
        <Link href="/" className="mt-4 inline-block text-sm text-blue-600 underline">
          Back to Dashboard
        </Link>
      </div>
    );
  }

  const {
    vessel,
    timeline,
    predicted_eta: predictedEta,
    exceptions,
    exception_count: exceptionCount,
  } = history;
  const latestMeta = statusMeta(vessel.last_event_type);

  return (
    <div className="mx-auto w-full max-w-4xl flex-1 px-4 py-8">
      <div className="overflow-hidden rounded-lg border border-zinc-200 shadow-sm dark:border-zinc-800">
        <div className="flex items-center justify-between bg-[#0b3d5c] px-6 py-4">
          <div>
            <h1 className="text-lg font-semibold text-white">{vessel.name} — Vessel History</h1>
            <p className="text-xs text-white/70">
              IMO {vessel.imo_number} · Data source: {vessel.source_name ?? "—"}
            </p>
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

        <div className="grid grid-cols-2 gap-6 border-b border-zinc-200 bg-white px-6 py-4 sm:grid-cols-4 dark:border-zinc-800 dark:bg-zinc-900">
          <Stat label="Current Status">
            <span
              className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${latestMeta.chipBg} ${latestMeta.chipText}`}
            >
              <StatusDot eventType={vessel.last_event_type} />
              {latestMeta.label}
            </span>
          </Stat>
          <Stat label="Destination">{vessel.destination_port ?? "Not set"}</Stat>
          <Stat label="Last Updated">
            {vessel.last_event_at ? new Date(vessel.last_event_at).toLocaleString() : "—"}
          </Stat>
          <Stat label="Current Location">{vessel.current_location ?? "—"}</Stat>
        </div>

        {/* Phase 6 (Section 7). Each panel renders only when it has something real to say -
            an exception list with no exceptions, or a prediction with no history behind it,
            would be noise rather than information. */}
        {exceptions.length > 0 && (
          <div className="border-b border-zinc-200 bg-white px-6 py-4 dark:border-zinc-800 dark:bg-zinc-900">
            <h2 className="mb-3 text-sm font-semibold text-zinc-700 dark:text-zinc-300">
              Exception Alerts ({exceptionCount})
            </h2>
            <ul className="space-y-2">
              {exceptions.map((exception) => (
                <li key={exception.id} className="flex flex-wrap items-center gap-3 text-sm">
                  <ExceptionBadge kind={exception.kind} />
                  <span>{exception.message}</span>
                  <span className="text-xs text-zinc-500">
                    detected {new Date(exception.detected_at).toLocaleString()}
                  </span>
                </li>
              ))}
            </ul>
            {/* A repeatedly-late vessel accrues one exception per voyage, so the panel shows the
                current picture and points at the full list rather than growing without bound. */}
            {exceptionCount > exceptions.length && (
              <p className="mt-3 text-xs text-zinc-500">
                Showing the {exceptions.length} most recent of {exceptionCount}.{" "}
                <Link href="/exceptions" className="text-blue-600 underline">
                  See all exceptions
                </Link>
                .
              </p>
            )}
          </div>
        )}

        {predictedEta && (
          <div className="border-b border-zinc-200 bg-white px-6 py-4 dark:border-zinc-800 dark:bg-zinc-900">
            <h2 className="mb-2 text-sm font-semibold text-zinc-700 dark:text-zinc-300">Predicted Arrival</h2>
            <p className="text-sm">
              <span className="font-medium">{new Date(predictedEta.predicted_arrival).toLocaleString()}</span>{" "}
              at {vessel.destination_port}
            </p>
            {/* The evidence, stated plainly - a prediction from one prior voyage should read
                differently from one backed by a dozen, so the sample size is always shown. */}
            <p className="mt-1 text-xs text-zinc-500">
              Based on {predictedEta.sample_size} previously completed voyage
              {predictedEta.sample_size === 1 ? "" : "s"} on this route, which took a median of{" "}
              {formatDuration(predictedEta.typical_duration_hours)}. Departed {predictedEta.departed_from} on{" "}
              {new Date(predictedEta.departed_at).toLocaleString()}. Derived from this vessel&apos;s own
              history — not from speed or route data, which this app&apos;s tracking sources don&apos;t provide.
            </p>
          </div>
        )}

        <VoyageSummaryPanel
          imo={imo}
          summary={summary}
          configured={aiConfigured}
          hasEvents={timeline.length > 0}
          onGenerated={setSummary}
        />

        <div className="bg-white px-6 py-6 dark:bg-zinc-900">
          <h2 className="mb-4 text-sm font-semibold text-zinc-700 dark:text-zinc-300">Movement Timeline</h2>
          {timeline.length === 0 ? (
            <p className="text-sm text-zinc-500">
              No tracking updates yet — the tracking worker polls periodically and will populate this timeline
              automatically.
            </p>
          ) : (
            <ol className="relative border-l border-zinc-200 pl-6 dark:border-zinc-700">
              {[...timeline].reverse().map((event) => {
                const meta = statusMeta(event.event_type);
                return (
                  <li key={event.id} className="mb-6 last:mb-0">
                    <span
                      className={`absolute -left-[5px] mt-1.5 h-2.5 w-2.5 rounded-full ${meta.dot}`}
                      aria-hidden
                    />
                    <p className="text-sm font-medium">{event.last_event_text}</p>
                    <p className="text-xs text-zinc-500">
                      {new Date(event.occurred_at).toLocaleString()} · {event.source_name}
                      {/* The ETA the source reported at this event (Section 3.3's captured
                          field). Shown inline so a delay alert can be checked against the
                          timeline it was derived from. */}
                      {event.eta && <> · ETA reported: {new Date(event.eta).toLocaleString()}</>}
                    </p>
                  </li>
                );
              })}
            </ol>
          )}
        </div>

        <div className="border-t border-zinc-200 bg-zinc-50 px-6 py-4 dark:border-zinc-800 dark:bg-zinc-900">
          {actionError && <p className="mb-3 text-sm text-red-600">{actionError}</p>}

          {vessel.archived_at ? (
            <p className="text-xs text-zinc-500">
              Archived on {new Date(vessel.archived_at).toLocaleString()} · History stays available for reference
            </p>
          ) : confirming === "archive" ? (
            <ConfirmBar
              message="Archive this vessel? It will move to the Archived view; history is kept."
              confirmLabel="Archive"
              confirmClassName="bg-[#0b3d5c] hover:bg-[#0a3450]"
              busy={actioning}
              onConfirm={handleArchive}
              onCancel={() => setConfirming(null)}
            />
          ) : confirming === "remove" ? (
            <ConfirmBar
              message="Remove this vessel? This permanently deletes it and its history — this cannot be undone."
              confirmLabel="Remove"
              confirmClassName="bg-red-600 hover:bg-red-700"
              busy={actioning}
              onConfirm={handleRemove}
              onCancel={() => setConfirming(null)}
            />
          ) : (
            <div className="flex gap-3">
              <button
                onClick={() => setConfirming("archive")}
                className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-800"
              >
                Archive
              </button>
              <button
                onClick={() => setConfirming("remove")}
                className="rounded-md border border-red-300 px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-50 dark:border-red-900 dark:text-red-400 dark:hover:bg-red-950"
              >
                Remove
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

/** Render a transit duration in whatever unit reads honestly at that magnitude.
 *
 * The backend reports hours as a float, which is right for real voyages but renders as a
 * misleading "0h" for the short ones the simulated tracking feed produces (a whole voyage
 * completes in one poll tick — seconds at the demo interval, minutes at the default). Saying
 * "45 seconds" is accurate; "0h" reads as instant travel. */
function formatDuration(hours: number): string {
  const minutes = hours * 60;
  if (minutes < 1) return `${Math.max(1, Math.round(minutes * 60))} seconds`;
  if (hours < 1) return `${Math.round(minutes)} minutes`;
  return `${hours}h`;
}

// AI Voyage Summary panel (Section 7; sketched in the proposal's Figure 3 as a box on this very
// page). Deliberately generate-on-demand rather than on page load: generation costs an API call,
// so it happens when a user asks for it, and the result is cached server-side thereafter.
function VoyageSummaryPanel({
  imo,
  summary,
  configured,
  hasEvents,
  onGenerated,
}: {
  imo: string;
  summary: VoyageSummary | null;
  configured: boolean;
  hasEvents: boolean;
  onGenerated: (summary: VoyageSummary) => void;
}) {
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleGenerate() {
    setGenerating(true);
    setError(null);
    try {
      onGenerated(await generateVoyageSummary(imo));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to generate the summary");
    } finally {
      setGenerating(false);
    }
  }

  return (
    <div className="border-b border-zinc-200 bg-white px-6 py-4 dark:border-zinc-800 dark:bg-zinc-900">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">AI Voyage Summary</h2>
        {/* Hidden entirely when unconfigured rather than shown-but-failing, matching how the
            Microsoft sign-in button and PDF bulk upload behave without their credentials. */}
        {configured && hasEvents && (
          <button
            onClick={handleGenerate}
            disabled={generating}
            className="rounded-md border border-zinc-300 px-3 py-1.5 text-xs font-medium hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-800"
          >
            {generating ? "Generating…" : summary ? "Regenerate" : "Generate AI Summary"}
          </button>
        )}
      </div>

      {error && <p className="mb-2 text-sm text-red-600">{error}</p>}

      {!configured ? (
        <p className="text-sm text-zinc-500">
          Unavailable — no <code>ANTHROPIC_API_KEY</code> is configured on the backend. Everything else on
          this page works regardless.
        </p>
      ) : !hasEvents ? (
        <p className="text-sm text-zinc-500">
          Nothing to summarise yet — this vessel has no tracking events.
        </p>
      ) : summary ? (
        <>
          <p className="text-sm leading-relaxed">{summary.summary}</p>
          <p className="mt-2 text-xs text-zinc-500">
            Generated {new Date(summary.generated_at).toLocaleString()} from {summary.source_event_count} event
            {summary.source_event_count === 1 ? "" : "s"}
            {/* A cached summary written before newer events landed is visibly out of date
                rather than quietly wrong. */}
            {summary.is_stale && (
              <span className="ml-2 rounded bg-amber-50 px-1.5 py-0.5 font-medium text-amber-700 dark:bg-amber-950 dark:text-amber-300">
                New events since — regenerate to update
              </span>
            )}
          </p>
        </>
      ) : (
        <p className="text-sm text-zinc-500">
          No summary generated yet. Written from this vessel&apos;s recorded events only — it never adds
          facts the timeline doesn&apos;t contain.
        </p>
      )}
    </div>
  );
}

// Shared "are you sure?" bar for both the archive and remove actions above - which one is
// showing is driven entirely by the caller's props (message/label/colour/handler), not by any
// state of its own.
function ConfirmBar({
  message,
  confirmLabel,
  confirmClassName,
  busy,
  onConfirm,
  onCancel,
}: {
  message: string;
  confirmLabel: string;
  confirmClassName: string;
  busy: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <p className="text-sm">{message}</p>
      <div className="ml-auto flex gap-2">
        <button
          onClick={onCancel}
          disabled={busy}
          className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm font-medium disabled:opacity-50 dark:border-zinc-700"
        >
          Cancel
        </button>
        <button
          onClick={onConfirm}
          disabled={busy}
          className={`rounded-md px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50 ${confirmClassName}`}
        >
          {busy ? "Working…" : confirmLabel}
        </button>
      </div>
    </div>
  );
}

// One label/value pair in the header's stat grid (Current Status, Destination, etc.).
function Stat({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">{label}</p>
      <div className="mt-1 text-sm font-medium">{children}</div>
    </div>
  );
}
