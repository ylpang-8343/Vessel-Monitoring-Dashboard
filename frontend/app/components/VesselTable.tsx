"use client";

import { useRouter } from "next/navigation";
import type { Vessel } from "@/lib/api";
import StatusDot from "./StatusDot";

// Main dashboard table (Section 3.4) - shared between the Active and Archived tabs (the caller
// just passes a differently-filtered `vessels` list; this component doesn't know or care which
// tab it's rendering for) and, with a custom `emptyMessage`, the Reports page's three category
// tables (Section 9 Phase 4) - a report category being empty doesn't mean *no vessels exist at
// all*, so it needs its own wording rather than defaulting to the dashboard's "+ Add" prompt.
// Clicking any row navigates to that vessel's full history page.
export default function VesselTable({
  vessels,
  emptyMessage = 'No vessels registered yet. Click "+ Add" to start monitoring one.',
}: {
  vessels: Vessel[];
  emptyMessage?: string;
}) {
  const router = useRouter();

  if (vessels.length === 0) {
    return <div className="px-6 py-16 text-center text-sm text-zinc-500">{emptyMessage}</div>;
  }

  return (
    <table className="w-full text-sm">
      <thead className="border-b border-zinc-200 text-left text-xs uppercase tracking-wide text-zinc-500 dark:border-zinc-800">
        <tr>
          <th className="px-6 py-3">Vessel Name</th>
          <th className="px-6 py-3">IMO Number</th>
          <th className="px-6 py-3">Current Location</th>
          <th className="px-6 py-3">Last Event</th>
          <th className="px-6 py-3">Destination</th>
          <th className="px-6 py-3">Source</th>
        </tr>
      </thead>
      <tbody>
        {vessels.map((v) => (
          <tr
            key={v.imo_number}
            onClick={() => router.push(`/vessels/${v.imo_number}`)}
            className="cursor-pointer border-b border-zinc-100 hover:bg-zinc-50 dark:border-zinc-800 dark:hover:bg-zinc-900"
          >
            <td className="px-6 py-3 font-medium">{v.name}</td>
            <td className="px-6 py-3 text-zinc-500">{v.imo_number}</td>
            <td className="px-6 py-3">{v.current_location ?? "—"}</td>
            <td className="px-6 py-3">
              {v.last_event_text ? (
                // Combines a colour-coded dot (6.E) with the full "what/where/when" text
                // (Section 3.4) in one column, rather than a separate status badge.
                <span className="flex items-center gap-2">
                  <StatusDot eventType={v.last_event_type} />
                  {v.last_event_text}
                </span>
              ) : (
                // No StatusEvent rows yet - the vessel was just registered and hasn't been
                // through a tracking-worker poll cycle.
                <span className="text-zinc-400">Awaiting first tracking update…</span>
              )}
            </td>
            <td className="px-6 py-3 font-medium">{v.destination_port ?? "—"}</td>
            <td className="px-6 py-3 text-zinc-500">{v.source_name ?? "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
