"use client";

import { use, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ApiError, archiveBooking, BookingHistory, getBookingHistory, removeBooking } from "@/lib/api";
import BookingStatusDot, { bookingStatusMeta } from "@/app/components/BookingStatusDot";
import UserMenu from "@/app/components/UserMenu";

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
    return <div className="mx-auto max-w-4xl px-4 py-16 text-center text-sm text-zinc-500">Loading…</div>;
  }

  if (error || !history) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-16 text-center">
        <p className="text-sm text-red-600">{error ?? "Booking not found"}</p>
        <Link href="/containers" className="mt-4 inline-block text-sm text-blue-600 underline">
          Back to Container/Booking Tracking
        </Link>
      </div>
    );
  }

  const { booking, timeline } = history;
  const latestMeta = bookingStatusMeta(booking.last_event_status);

  return (
    <div className="mx-auto w-full max-w-4xl flex-1 px-4 py-8">
      <div className="overflow-hidden rounded-lg border border-zinc-200 shadow-sm dark:border-zinc-800">
        <div className="flex items-center justify-between bg-[#0b3d5c] px-6 py-4">
          <div>
            <h1 className="text-lg font-semibold text-white">{booking.booking_number} — Booking History</h1>
            <p className="text-xs text-white/70">
              {booking.shipping_line} · Data source: {booking.source_name ?? "—"}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <UserMenu />
            <Link
              href="/containers"
              className="rounded-md bg-white/10 px-3 py-1.5 text-sm font-medium text-white hover:bg-white/20"
            >
              Back to Container/Booking Tracking
            </Link>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-6 border-b border-zinc-200 bg-white px-6 py-4 sm:grid-cols-4 dark:border-zinc-800 dark:bg-zinc-900">
          <Stat label="Current Status">
            <span
              className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${latestMeta.chipBg} ${latestMeta.chipText}`}
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

        <div className="bg-white px-6 py-6 dark:bg-zinc-900">
          <h2 className="mb-4 text-sm font-semibold text-zinc-700 dark:text-zinc-300">Movement Timeline</h2>
          {timeline.length === 0 ? (
            <p className="text-sm text-zinc-500">
              No tracking updates yet — the booking worker polls periodically and will populate this timeline
              automatically.
            </p>
          ) : (
            <ol className="relative border-l border-zinc-200 pl-6 dark:border-zinc-700">
              {[...timeline].reverse().map((event) => {
                const meta = bookingStatusMeta(event.status);
                return (
                  <li key={event.id} className="mb-6 last:mb-0">
                    <span
                      className={`absolute -left-[5px] mt-1.5 h-2.5 w-2.5 rounded-full ${meta.dot}`}
                      aria-hidden
                    />
                    <p className="text-sm font-medium">{event.last_event_text}</p>
                    <p className="text-xs text-zinc-500">
                      {new Date(event.occurred_at).toLocaleString()} · {event.source_name}
                    </p>
                  </li>
                );
              })}
            </ol>
          )}
        </div>

        <div className="border-t border-zinc-200 bg-zinc-50 px-6 py-4 dark:border-zinc-800 dark:bg-zinc-900">
          {actionError && <p className="mb-3 text-sm text-red-600">{actionError}</p>}

          {booking.archived_at ? (
            <p className="text-xs text-zinc-500">
              Archived on {new Date(booking.archived_at).toLocaleString()} · History stays available for reference
            </p>
          ) : confirming === "archive" ? (
            <ConfirmBar
              message="Archive this booking? It will move to the Archived view; history is kept."
              confirmLabel="Archive"
              confirmClassName="bg-[#0b3d5c] hover:bg-[#0a3450]"
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
              <button
                onClick={() => setConfirming("archive")}
                className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-800"
              >
                Archive
              </button>
              <button
                onClick={() => setConfirming("remove")}
                className="rounded-md border border-red-300 px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-50 dark:border-red-900 dark:text-red-400 dark:hover:bg-red-950"
              >
                Remove
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
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
        <button
          onClick={onCancel}
          disabled={busy}
          className="rounded-md border border-zinc-300 px-3 py-1.5 text-sm font-medium disabled:opacity-50 dark:border-zinc-700"
        >
          Cancel
        </button>
        <button
          onClick={onConfirm}
          disabled={busy}
          className={`rounded-md px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50 ${confirmClassName}`}
        >
          {busy ? "Working…" : confirmLabel}
        </button>
      </div>
    </div>
  );
}

function Stat({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide text-zinc-500">{label}</p>
      <div className="mt-1 text-sm font-medium">{children}</div>
    </div>
  );
}
