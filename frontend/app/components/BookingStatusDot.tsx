import type { BookingStatus } from "@/lib/api";

// Colour coding for the Container/Booking table (Section 4), mirroring StatusDot.tsx's approach
// for vessels (Section 6.E) - a small dot per stage, kept visually distinct from the vessel
// palette so the two modules never look interchangeable in a screenshot, while still reusing the
// same "lookup table + statusMeta() + dot component" shape for consistency.
const COLOURS: Record<BookingStatus, { dot: string; label: string; chipBg: string; chipText: string }> = {
  booking_confirmed: {
    dot: "bg-zinc-400",
    label: "Booking Confirmed",
    chipBg: "bg-zinc-100",
    chipText: "text-zinc-600",
  },
  loaded: { dot: "bg-orange-500", label: "Loaded", chipBg: "bg-orange-50", chipText: "text-orange-700" },
  in_transit: { dot: "bg-blue-500", label: "In Transit", chipBg: "bg-blue-50", chipText: "text-blue-700" },
  discharged: { dot: "bg-green-500", label: "Discharged", chipBg: "bg-green-50", chipText: "text-green-700" },
  gate_out: { dot: "bg-purple-500", label: "Gate Out", chipBg: "bg-purple-50", chipText: "text-purple-700" },
};

/** Look up the colour/label for a booking status, or a neutral "No data" style for a booking
 * that hasn't had its first tracking update yet (last_event_status is null). */
export function bookingStatusMeta(status: BookingStatus | null) {
  if (!status) return { dot: "bg-zinc-300", label: "No data", chipBg: "bg-zinc-50", chipText: "text-zinc-500" };
  return COLOURS[status];
}

/** Small colour-coded dot next to a booking's "Last Event" entry - the Container/Booking table's
 * equivalent of StatusDot for vessels. */
export default function BookingStatusDot({ status }: { status: BookingStatus | null }) {
  const meta = bookingStatusMeta(status);
  return <span className={`inline-block h-2.5 w-2.5 rounded-full ${meta.dot}`} title={meta.label} />;
}
