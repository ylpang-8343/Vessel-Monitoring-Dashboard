"use client";

import { use, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ApiError, getVesselHistory, VesselHistory } from "@/lib/api";
import StatusDot, { statusMeta } from "@/app/components/StatusDot";

const HISTORY_REFRESH_MS = 30 * 1000;

export default function VesselHistoryPage({ params }: { params: Promise<{ imo: string }> }) {
  const { imo } = use(params);
  const [history, setHistory] = useState<VesselHistory | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const data = await getVesselHistory(imo);
      setHistory(data);
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

  const { vessel, timeline } = history;
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
          <Link
            href="/"
            className="rounded-md bg-white/10 px-3 py-1.5 text-sm font-medium text-white hover:bg-white/20"
          >
            Back to Dashboard
          </Link>
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
                    </p>
                  </li>
                );
              })}
            </ol>
          )}
        </div>
      </div>
    </div>
  );
}

function Stat({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">{label}</p>
      <div className="mt-1 text-sm font-medium">{children}</div>
    </div>
  );
}
