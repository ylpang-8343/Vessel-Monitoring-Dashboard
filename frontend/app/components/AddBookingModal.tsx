"use client";

import { useState } from "react";
import { ApiError, createBooking } from "@/lib/api";
import { btnPrimary, btnSecondary, inputClass, labelClass } from "./ui";

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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4">
      <div className="w-full max-w-lg border border-rule bg-white shadow-2xl">
        <div className="flex items-center justify-between bg-brand px-5 py-3.5">
          <h2 className="text-base font-bold uppercase tracking-wide text-white">Add Booking / Container</h2>
          <button onClick={onClose} className="text-white/80 hover:text-white" aria-label="Close">
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 px-5 py-5">
          <div>
            <label className={labelClass}>Booking / Container Number</label>
            <input
              required
              value={bookingNumber}
              onChange={(e) => setBookingNumber(e.target.value)}
              placeholder="e.g. ONEYBOOKG12345"
              className={`${inputClass} mt-1 w-full`}
            />
          </div>

          <div>
            <label className={labelClass}>Shipping Line</label>
            <input
              required
              value={shippingLine}
              onChange={(e) => setShippingLine(e.target.value)}
              placeholder="e.g. ONE, Maersk, MSC, CMA CGM"
              className={`${inputClass} mt-1 w-full`}
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={labelClass}>Port of Loading</label>
              <input
                required
                value={pol}
                onChange={(e) => setPol(e.target.value)}
                placeholder="e.g. Shanghai"
                className={`${inputClass} mt-1 w-full`}
              />
            </div>
            <div>
              <label className={labelClass}>Port of Discharge</label>
              <input
                required
                value={pod}
                onChange={(e) => setPod(e.target.value)}
                placeholder="e.g. Pasir Gudang"
                className={`${inputClass} mt-1 w-full`}
              />
            </div>
          </div>

          <p className="text-xs text-muted">
            Duplicate booking/container numbers are automatically rejected (matching case-insensitively).
          </p>

          {error && <p className="text-sm text-red-600">{error}</p>}

          <div className="flex justify-end gap-3 pt-2">
            <button type="button" onClick={onClose} className={btnSecondary}>
              Cancel
            </button>
            <button type="submit" disabled={submitting} className={btnPrimary}>
              {submitting ? "Adding…" : "Add Booking"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
