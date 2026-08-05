"use client";

import { useRouter } from "next/navigation";
import type { Booking } from "@/lib/api";
import BookingStatusDot from "./BookingStatusDot";

// Container/Booking table (Section 4) - the companion to VesselTable, same shape: a single
// sortable-by-name table combining Current Location and a colour-dot "Last Event" column, with
// row clicks navigating to that booking's full history page. Columns match Section 4's list:
// Booking/Container Number, Shipping Line, POL/POD, Current Location, Last Event, Source.
export default function BookingTable({
  bookings,
  emptyMessage = 'No bookings registered yet. Click "+ Add" to start tracking one.',
}: {
  bookings: Booking[];
  emptyMessage?: string;
}) {
  const router = useRouter();

  if (bookings.length === 0) {
    return <div className="px-6 py-16 text-center text-sm text-zinc-500">{emptyMessage}</div>;
  }

  return (
    <table className="w-full text-sm">
      <thead className="border-b border-zinc-200 text-left text-xs uppercase tracking-wide text-zinc-500 dark:border-zinc-800">
        <tr>
          <th className="px-6 py-3">Booking / Container No.</th>
          <th className="px-6 py-3">Shipping Line</th>
          <th className="px-6 py-3">POL / POD</th>
          <th className="px-6 py-3">Current Location</th>
          <th className="px-6 py-3">Last Event</th>
          <th className="px-6 py-3">Source</th>
        </tr>
      </thead>
      <tbody>
        {bookings.map((b) => (
          <tr
            key={b.booking_number}
            onClick={() => router.push(`/containers/${b.booking_number}`)}
            className="cursor-pointer border-b border-zinc-100 hover:bg-zinc-50 dark:border-zinc-800 dark:hover:bg-zinc-900"
          >
            <td className="px-6 py-3 font-medium">{b.booking_number}</td>
            <td className="px-6 py-3 text-zinc-500">{b.shipping_line}</td>
            <td className="px-6 py-3">
              {b.port_of_loading} → {b.port_of_discharge}
            </td>
            <td className="px-6 py-3">{b.current_location ?? "—"}</td>
            <td className="px-6 py-3">
              {b.last_event_text ? (
                <span className="flex items-center gap-2">
                  <BookingStatusDot status={b.last_event_status} />
                  {b.last_event_text}
                </span>
              ) : (
                // No BookingEvent rows yet - just registered, hasn't been through a poll cycle.
                <span className="text-zinc-400">Awaiting first tracking update…</span>
              )}
            </td>
            <td className="px-6 py-3 text-zinc-500">{b.source_name ?? "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
