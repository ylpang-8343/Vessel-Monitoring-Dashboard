"use client";

import { useRouter } from "next/navigation";
import type { Booking } from "@/lib/api";
import BookingStatusDot from "./BookingStatusDot";
import { EmptyState, theadClass } from "./ui";

// Container/Booking table (Section 4) - the companion to VesselTable, same shape: a single
// sortable-by-name table combining Current Location and a colour-dot "Last Event" column, with
// row clicks navigating to that booking's full history page. Columns match Section 4's list:
// Booking/Container Number, Shipping Line, POL/POD, Current Location, Last Event, Source.
export default function BookingTable({
  bookings,
  emptyMessage = 'No bookings registered yet. Click "+ Add Booking" to start tracking one.',
}: {
  bookings: Booking[];
  emptyMessage?: string;
}) {
  const router = useRouter();

  if (bookings.length === 0) {
    return <EmptyState>{emptyMessage}</EmptyState>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[900px] text-sm">
        <thead className={theadClass}>
          <tr>
            <th className="px-5 py-3">Booking / Container No.</th>
            <th className="px-5 py-3">Shipping Line</th>
            <th className="px-5 py-3">POL / POD</th>
            <th className="px-5 py-3">Current Location</th>
            <th className="px-5 py-3">Last Event</th>
            <th className="px-5 py-3">Source</th>
          </tr>
        </thead>
        <tbody>
          {bookings.map((b) => (
            <tr
              key={b.booking_number}
              onClick={() => router.push(`/containers/${b.booking_number}`)}
              className="cursor-pointer border-b border-rule last:border-b-0 hover:bg-brand-tint"
            >
              <td className="px-5 py-3 font-bold text-ink">{b.booking_number}</td>
              <td className="px-5 py-3 text-muted">{b.shipping_line}</td>
              <td className="px-5 py-3">
                {b.port_of_loading} → {b.port_of_discharge}
              </td>
              <td className="px-5 py-3">{b.current_location ?? "—"}</td>
              <td className="px-5 py-3">
                {b.last_event_text ? (
                  <span className="flex items-center gap-2">
                    <BookingStatusDot status={b.last_event_status} />
                    {b.last_event_text}
                  </span>
                ) : (
                  // No BookingEvent rows yet - just registered, hasn't been through a poll cycle.
                  <span className="text-muted">Awaiting first tracking update…</span>
                )}
              </td>
              <td className="px-5 py-3 text-muted">{b.source_name ?? "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
