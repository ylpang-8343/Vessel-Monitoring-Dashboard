import type { EventType } from "@/lib/api";

// Colour coding per proposal Section 6.E, extended to cover the two extra
// states from Section 3.3a (ETA to Destination / Sailed from Destination)
// that the 6.E table doesn't explicitly assign a colour to.
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

export function statusMeta(eventType: EventType | null) {
  if (!eventType) return { dot: "bg-zinc-300", label: "No data", chipBg: "bg-zinc-50", chipText: "text-zinc-500" };
  return COLOURS[eventType];
}

export default function StatusDot({ eventType }: { eventType: EventType | null }) {
  const meta = statusMeta(eventType);
  return <span className={`inline-block h-2.5 w-2.5 rounded-full ${meta.dot}`} title={meta.label} />;
}
