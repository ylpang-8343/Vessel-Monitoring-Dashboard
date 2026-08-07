"use client";

import { useRouter } from "next/navigation";
import type { Vessel } from "@/lib/api";
import StatusDot from "./StatusDot";
import { EmptyState, theadClass } from "./ui";

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
    return <EmptyState>{emptyMessage}</EmptyState>;
  }

  return (
    // The table scrolls inside its own box rather than forcing the whole page sideways on a
    // narrow screen - six columns don't fit a laptop-width window at this font size.
    <div className="overflow-x-auto">
      <table className="w-full min-w-[900px] text-sm">
        <thead className={theadClass}>
          <tr>
            <th className="px-5 py-3">Vessel Name</th>
            <th className="px-5 py-3">IMO Number</th>
            <th className="px-5 py-3">Current Location</th>
            <th className="px-5 py-3">Last Event</th>
            <th className="px-5 py-3">Destination</th>
            <th className="px-5 py-3">Source</th>
          </tr>
        </thead>
        <tbody>
          {vessels.map((v) => (
            <tr
              key={v.imo_number}
              onClick={() => router.push(`/vessels/${v.imo_number}`)}
              className="cursor-pointer border-b border-rule last:border-b-0 hover:bg-brand-tint"
            >
              <td className="px-5 py-3 font-bold text-ink">{v.name}</td>
              <td className="px-5 py-3 text-muted">{v.imo_number}</td>
              <td className="px-5 py-3">{v.current_location ?? "—"}</td>
              <td className="px-5 py-3">
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
                  <span className="text-muted">Awaiting first tracking update…</span>
                )}
              </td>
              <td className="px-5 py-3 font-bold text-ink">{v.destination_port ?? "—"}</td>
              <td className="px-5 py-3 text-muted">{v.source_name ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
