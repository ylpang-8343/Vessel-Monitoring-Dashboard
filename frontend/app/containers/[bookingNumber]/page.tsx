"use client";

import { use, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ApiError, archiveBooking, BookingHistory, getBookingHistory, removeBooking } from "@/lib/api";
import BookingStatusDot, { bookingStatusMeta } from "@/app/components/BookingStatusDot";
import {
  EmptyState,
  PageBanner,
  Panel,
  PanelHeader,
  Shell,
  Stat,
  btnDanger,
  btnSecondary,
  btnSecondarySm,
} from "@/app/components/ui";

const HISTORY_REFRESH_MS = 30 * 1000;

type ConfirmAction = "archive" | "remove" | null;

// Single-booking history page (Section 4) at "/containers/[bookingNumber]" - the Container/
// Booking module's equivalent of vessels/[imo]/page.tsx: full movement timeline plus manual
// archive/remove, same one-way-action confirm pattern. `params` is a Promise here per this
// Next.js version's App Router API (see frontend/AGENTS.md), unwrapped with React's `use()`.
export default function BookingHistoryPage({ params }: { params: Promise<{ bookingNumber: string }> }) {
  const { bookingNumber } = use(params);
  const router = useRouter();
  const [history, setHistory] = useState<BookingHistory | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [confirming, setConfirming] = useState<ConfirmAction>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actioning, setActioning] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const data = await getBookingHistory(bookingNumber);
      setHistory(data);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not reach the API");
    } finally {
      setLoading(false);
    }
  }, [bookingNumber]);

  useEffect(() => {
    void (async () => {
      await refresh();
    })();
    const interval = setInterval(() => refresh(), HISTORY_REFRESH_MS);
    return () => clearInterval(interval);
  }, [refresh]);

  async function handleArchive() {
    setActioning(true);
    setActionError(null);
    try {
      await archiveBooking(bookingNumber);
      setConfirming(null);
      await refresh();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Failed to archive booking");
    } finally {
      setActioning(false);
    }
  }

  async function handleRemove() {
    setActioning(true);
    setActionError(null);
    try {
      await removeBooking(bookingNumber);
      router.push("/containers");
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Failed to remove booking");
      setActioning(false);
    }
  }

  if (loading) {
    return (
      <Shell className="py-20">
        <p className="text-center text-sm text-muted">Loading…</p>
      </Shell>
    );
  }

  if (error || !history) {
    return (
      <Shell className="py-20 text-center">
        <p className="text-sm text-red-600">{error ?? "Booking not found"}</p>
        <Link href="/containers" className="mt-4 inline-block text-sm font-bold text-brand hover:underline">
          Back to Container / Booking Tracking
        </Link>
      </Shell>
    );
  }

  const { booking, timeline } = history;
  const latestMeta = bookingStatusMeta(booking.last_event_status);

  return (
    <>
      <PageBanner
        title={booking.booking_number}
        subtitle={`${booking.shipping_line} · Data source: ${booking.source_name ?? "—"}`}
      />

      <Shell className="space-y-5 py-7">
        <Panel>
          <div className="grid grid-cols-2 gap-6 px-5 py-4 sm:grid-cols-4">
            <Stat label="Current Status">
              <span
                className={`inline-flex items-center gap-1.5 rounded-sm px-2.5 py-1 text-xs font-bold ${latestMeta.chipBg} ${latestMeta.chipText}`}
              >
                <BookingStatusDot status={booking.last_event_status} />
                {latestMeta.label}
              </span>
            </Stat>
            <Stat label="POL → POD">
              {booking.port_of_loading} → {booking.port_of_discharge}
            </Stat>
            <Stat label="Last Updated">
              {booking.last_event_at ? new Date(booking.last_event_at).toLocaleString() : "—"}
            </Stat>
            <Stat label="Current Location">{booking.current_location ?? "—"}</Stat>
          </div>
        </Panel>

        <Panel>
          <PanelHeader title="Movement Timeline" />
          {timeline.length === 0 ? (
            <EmptyState>
              No tracking updates yet — the booking worker polls periodically and will populate this
              timeline automatically.
            </EmptyState>
          ) : (
            <div className="px-5 py-6">
              <ol className="relative border-l-2 border-rule pl-6">
                {[...timeline].reverse().map((event) => {
                  const meta = bookingStatusMeta(event.status);
                  return (
                    <li key={event.id} className="mb-6 last:mb-0">
                      <span
                        className={`absolute -left-[7px] mt-1.5 h-3 w-3 rounded-full border-2 border-white ${meta.dot}`}
                        aria-hidden
                      />
                      <p className="text-sm font-bold text-ink">{event.last_event_text}</p>
                      <p className="text-xs text-muted">
                        {new Date(event.occurred_at).toLocaleString()} · {event.source_name}
                      </p>
                    </li>
                  );
                })}
              </ol>
            </div>
          )}
        </Panel>

        <Panel>
          <div className="px-5 py-4">
            {actionError && <p className="mb-3 text-sm text-red-600">{actionError}</p>}

            {booking.archived_at ? (
              <p className="text-xs text-muted">
                Archived on {new Date(booking.archived_at).toLocaleString()} · History stays available for
                reference
              </p>
            ) : confirming === "archive" ? (
              <ConfirmBar
                message="Archive this booking? It will move to the Archived view; history is kept."
                confirmLabel="Archive"
                confirmClassName="bg-brand hover:bg-brand-dark"
                busy={actioning}
                onConfirm={handleArchive}
                onCancel={() => setConfirming(null)}
              />
            ) : confirming === "remove" ? (
              <ConfirmBar
                message="Remove this booking? This permanently deletes it and its history — this cannot be undone."
                confirmLabel="Remove"
                confirmClassName="bg-red-600 hover:bg-red-700"
                busy={actioning}
                onConfirm={handleRemove}
                onCancel={() => setConfirming(null)}
              />
            ) : (
              <div className="flex gap-3">
                <button onClick={() => setConfirming("archive")} className={btnSecondary}>
                  Archive
                </button>
                <button onClick={() => setConfirming("remove")} className={btnDanger}>
                  Remove
                </button>
              </div>
            )}
          </div>
        </Panel>
      </Shell>
    </>
  );
}

// Shared "are you sure?" bar - identical contract to the one in vessels/[imo]/page.tsx.
function ConfirmBar({
  message,
  confirmLabel,
  confirmClassName,
  busy,
  onConfirm,
  onCancel,
}: {
  message: string;
  confirmLabel: string;
  confirmClassName: string;
  busy: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      <p className="text-sm">{message}</p>
      <div className="ml-auto flex gap-2">
        <button onClick={onCancel} disabled={busy} className={btnSecondarySm}>
          Cancel
        </button>
        <button
          onClick={onConfirm}
          disabled={busy}
          className={`inline-flex items-center justify-center rounded-sm px-3 py-1.5 text-xs font-bold text-white transition-colors disabled:opacity-50 ${confirmClassName}`}
        >
          {busy ? "Working…" : confirmLabel}
        </button>
      </div>
    </div>
  );
}
