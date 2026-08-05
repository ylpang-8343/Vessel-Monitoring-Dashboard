"use client";

import { useState } from "react";
import { ApiError, createBooking } from "@/lib/api";

// "+ Add" modal for the Container/Booking Tracking module (Section 4) - single-entry only,
// unlike AddVesselModal: the proposal's Section 4 doesn't call for a bulk-upload path for this
// module the way Section 3.2 does for vessels, so this mirrors just the "Single Vessel" tab's
// shape rather than the full two-tab modal.
export default function AddBookingModal({
  onClose,
  onImported,
}: {
  onClose: () => void;
  onImported: () => void;
}) {
  const [bookingNumber, setBookingNumber] = useState("");
  const [shippingLine, setShippingLine] = useState("");
  const [pol, setPol] = useState("");
  const [pod, setPod] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await createBooking({
        booking_number: bookingNumber,
        shipping_line: shippingLine,
        port_of_loading: pol,
        port_of_discharge: pod,
      });
      onImported();
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to add booking");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-lg rounded-lg bg-white shadow-xl dark:bg-zinc-900">
        <div className="flex items-center justify-between rounded-t-lg bg-[#0b3d5c] px-6 py-4">
          <h2 className="text-lg font-semibold text-white">Add Booking / Container</h2>
          <button onClick={onClose} className="text-white/80 hover:text-white" aria-label="Close">
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 px-6 py-5">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wide text-zinc-500">
              Booking / Container Number
            </label>
            <input
              required
              value={bookingNumber}
              onChange={(e) => setBookingNumber(e.target.value)}
              placeholder="e.g. ONEYBOOKG12345"
              className="mt-1 w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold uppercase tracking-wide text-zinc-500">
              Shipping Line
            </label>
            <input
              required
              value={shippingLine}
              onChange={(e) => setShippingLine(e.target.value)}
              placeholder="e.g. ONE, Maersk, MSC, CMA CGM"
              className="mt-1 w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wide text-zinc-500">
                Port of Loading
              </label>
              <input
                required
                value={pol}
                onChange={(e) => setPol(e.target.value)}
                placeholder="e.g. Shanghai"
                className="mt-1 w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold uppercase tracking-wide text-zinc-500">
                Port of Discharge
              </label>
              <input
                required
                value={pod}
                onChange={(e) => setPod(e.target.value)}
                placeholder="e.g. Pasir Gudang"
                className="mt-1 w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
              />
            </div>
          </div>

          <p className="text-xs text-zinc-500">
            Duplicate booking/container numbers are automatically rejected (matching case-insensitively).
          </p>

          {error && <p className="text-sm text-red-600">{error}</p>}

          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium dark:border-zinc-700"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="rounded-md bg-[#1f8a4c] px-4 py-2 text-sm font-medium text-white hover:bg-[#1a7642] disabled:opacity-50"
            >
              {submitting ? "Adding…" : "Add Booking"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
