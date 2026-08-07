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
import {
  EmptyState,
  PageBanner,
  Panel,
  PanelHeader,
  Shell,
  Stat,
  btnDanger,
  btnSecondary,
  btnSecondarySm,
} from "@/app/components/ui";

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
    return (
      <Shell className="py-20">
        <p className="text-center text-sm text-muted">Loading…</p>
      </Shell>
    );
  }

  if (error || !history) {
    return (
      <Shell className="py-20 text-center">
        <p className="text-sm text-red-600">{error ?? "Vessel not found"}</p>
        <Link href="/" className="mt-4 inline-block text-sm font-bold text-brand hover:underline">
          Back to Dashboard
        </Link>
      </Shell>
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
    <>
      <PageBanner
        title={vessel.name}
        subtitle={`IMO ${vessel.imo_number} · Data source: ${vessel.source_name ?? "—"}`}
      />

      <Shell className="space-y-5 py-7">
        <Panel>
          <div className="grid grid-cols-2 gap-6 px-5 py-4 sm:grid-cols-4">
            <Stat label="Current Status">
              <span
                className={`inline-flex items-center gap-1.5 rounded-sm px-2.5 py-1 text-xs font-bold ${latestMeta.chipBg} ${latestMeta.chipText}`}
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
        </Panel>

        {/* Phase 6 (Section 7). Each panel renders only when it has something real to say -
            an exception list with no exceptions, or a prediction with no history behind it,
            would be noise rather than information. */}
        {exceptions.length > 0 && (
          <Panel>
            <PanelHeader title={`Exception Alerts (${exceptionCount})`} />
            <div className="px-5 py-4">
              <ul className="space-y-2.5">
                {exceptions.map((exception) => (
                  <li key={exception.id} className="flex flex-wrap items-center gap-3 text-sm">
                    <ExceptionBadge kind={exception.kind} />
                    <span>{exception.message}</span>
                    <span className="text-xs text-muted">
                      detected {new Date(exception.detected_at).toLocaleString()}
                    </span>
                  </li>
                ))}
              </ul>
              {/* A repeatedly-late vessel accrues one exception per voyage, so the panel shows the
                  current picture and points at the full list rather than growing without bound. */}
              {exceptionCount > exceptions.length && (
                <p className="mt-3 text-xs text-muted">
                  Showing the {exceptions.length} most recent of {exceptionCount}.{" "}
                  <Link href="/exceptions" className="font-bold text-brand hover:underline">
                    See all exceptions
                  </Link>
                  .
                </p>
              )}
            </div>
          </Panel>
        )}

        {predictedEta && (
          <Panel>
            <PanelHeader title="Predicted Arrival" />
            <div className="px-5 py-4">
              <p className="text-sm">
                <span className="font-bold text-ink">
                  {new Date(predictedEta.predicted_arrival).toLocaleString()}
                </span>{" "}
                at {vessel.destination_port}
              </p>
              {/* The evidence, stated plainly - a prediction from one prior voyage should read
                  differently from one backed by a dozen, so the sample size is always shown. */}
              <p className="mt-1.5 text-xs leading-relaxed text-muted">
                Based on {predictedEta.sample_size} previously completed voyage
                {predictedEta.sample_size === 1 ? "" : "s"} on this route, which took a median of{" "}
                {formatDuration(predictedEta.typical_duration_hours)}. Departed {predictedEta.departed_from}{" "}
                on {new Date(predictedEta.departed_at).toLocaleString()}. Derived from this vessel&apos;s own
                history — not from speed or route data, which this app&apos;s tracking sources don&apos;t
                provide.
              </p>
            </div>
          </Panel>
        )}

        <VoyageSummaryPanel
          imo={imo}
          summary={summary}
          configured={aiConfigured}
          hasEvents={timeline.length > 0}
          onGenerated={setSummary}
        />

        <Panel>
          <PanelHeader title="Movement Timeline" />
          {timeline.length === 0 ? (
            <EmptyState>
              No tracking updates yet — the tracking worker polls periodically and will populate this
              timeline automatically.
            </EmptyState>
          ) : (
            <div className="px-5 py-6">
              <ol className="relative border-l-2 border-rule pl-6">
                {[...timeline].reverse().map((event) => {
                  const meta = statusMeta(event.event_type);
                  return (
                    <li key={event.id} className="mb-6 last:mb-0">
                      <span
                        className={`absolute -left-[7px] mt-1.5 h-3 w-3 rounded-full border-2 border-white ${meta.dot}`}
                        aria-hidden
                      />
                      <p className="text-sm font-bold text-ink">{event.last_event_text}</p>
                      <p className="text-xs text-muted">
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
            </div>
          )}
        </Panel>

        <Panel>
          <div className="px-5 py-4">
            {actionError && <p className="mb-3 text-sm text-red-600">{actionError}</p>}

            {vessel.archived_at ? (
              <p className="text-xs text-muted">
                Archived on {new Date(vessel.archived_at).toLocaleString()} · History stays available for
                reference
              </p>
            ) : confirming === "archive" ? (
              <ConfirmBar
                message="Archive this vessel? It will move to the Archived view; history is kept."
                confirmLabel="Archive"
                confirmClassName="bg-brand hover:bg-brand-dark"
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
                <button onClick={() => setConfirming("archive")} className={btnSecondary}>
                  Archive
                </button>
                <button onClick={() => setConfirming("remove")} className={btnDanger}>
                  Remove
                </button>
              </div>
            )}
          </div>
        </Panel>
      </Shell>
    </>
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
    <Panel>
      <PanelHeader
        title="AI Voyage Summary"
        actions={
          // Hidden entirely when unconfigured rather than shown-but-failing, matching how the
          // Microsoft sign-in button and PDF bulk upload behave without their credentials.
          configured &&
          hasEvents && (
            <button onClick={handleGenerate} disabled={generating} className={btnSecondarySm}>
              {generating ? "Generating…" : summary ? "Regenerate" : "Generate AI Summary"}
            </button>
          )
        }
      />

      <div className="px-5 py-4">
        {error && <p className="mb-2 text-sm text-red-600">{error}</p>}

        {!configured ? (
          <p className="text-sm text-muted">
            Unavailable — no <code>ANTHROPIC_API_KEY</code> is configured on the backend. Everything else on
            this page works regardless.
          </p>
        ) : !hasEvents ? (
          <p className="text-sm text-muted">Nothing to summarise yet — this vessel has no tracking events.</p>
        ) : summary ? (
          <>
            <p className="text-sm leading-relaxed">{summary.summary}</p>
            <p className="mt-2 text-xs text-muted">
              Generated {new Date(summary.generated_at).toLocaleString()} from {summary.source_event_count}{" "}
              event{summary.source_event_count === 1 ? "" : "s"}
              {/* A cached summary written before newer events landed is visibly out of date
                  rather than quietly wrong. */}
              {summary.is_stale && (
                <span className="ml-2 rounded-sm bg-amber-50 px-1.5 py-0.5 font-bold text-amber-700">
                  New events since — regenerate to update
                </span>
              )}
            </p>
          </>
        ) : (
          <p className="text-sm text-muted">
            No summary generated yet. Written from this vessel&apos;s recorded events only — it never adds
            facts the timeline doesn&apos;t contain.
          </p>
        )}
      </div>
    </Panel>
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
        <button onClick={onCancel} disabled={busy} className={btnSecondarySm}>
          Cancel
        </button>
        <button
          onClick={onConfirm}
          disabled={busy}
          className={`inline-flex items-center justify-center rounded-sm px-3 py-1.5 text-xs font-bold text-white transition-colors disabled:opacity-50 ${confirmClassName}`}
        >
          {busy ? "Working…" : confirmLabel}
        </button>
      </div>
    </div>
  );
}
