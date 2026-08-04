import type { EventType } from "@/lib/api";

// Colour coding per proposal Section 6.E, extended to cover the two extra
// states from Section 3.3a (ETA to Destination / Sailed from Destination)
// that the 6.E table doesn't explicitly assign a colour to.
//
// Single source of truth for this palette - reused by the dashboard table's dots, the vessel
// history timeline, the filter chips (Section 6.D), and the Map View's marker colours, so all
// four stay visually consistent with each other automatically.
const COLOURS: Record<EventType, { dot: string; label: string; chipBg: string; chipText: string }> = {
  sailing: { dot: "bg-blue-500", label: "Sailing", chipBg: "bg-blue-50", chipText: "text-blue-700" },
  at_port: { dot: "bg-orange-500", label: "At Port", chipBg: "bg-orange-50", chipText: "text-orange-700" },
  eta_destination: {
    dot: "bg-amber-500",
    label: "ETA to Destination",
    chipBg: "bg-amber-50",
    chipText: "text-amber-700",
  },
  arrived_destination: {
    dot: "bg-green-500",
    label: "Arrived at Destination",
    chipBg: "bg-green-50",
    chipText: "text-green-700",
  },
  sailed_from_destination: {
    dot: "bg-zinc-400",
    label: "Sailed from Destination",
    chipBg: "bg-zinc-100",
    chipText: "text-zinc-600",
  },
};

/** Look up the colour/label for an event type, or a neutral "No data" style when a vessel has
 * no tracking events yet (last_event_type is null - see backend VesselOut). */
export function statusMeta(eventType: EventType | null) {
  if (!eventType) return { dot: "bg-zinc-300", label: "No data", chipBg: "bg-zinc-50", chipText: "text-zinc-500" };
  return COLOURS[eventType];
}

/** Small colour-coded dot next to a "Last Event" entry (Section 6.E) - `title` gives the full
 * status name on hover since the dot alone only conveys colour, not text. */
export default function StatusDot({ eventType }: { eventType: EventType | null }) {
  const meta = statusMeta(eventType);
  return <span className={`inline-block h-2.5 w-2.5 rounded-full ${meta.dot}`} title={meta.label} />;
}
