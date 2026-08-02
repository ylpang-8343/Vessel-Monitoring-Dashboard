"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  ApiError,
  createTrackingSource,
  deleteTrackingSource,
  listTrackingSources,
  TrackingSource,
  updateTrackingSource,
} from "@/lib/api";

export default function SettingsPage() {
  const [sources, setSources] = useState<TrackingSource[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const data = await listTrackingSources();
      setSources(data);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not reach the API — is the backend running?");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void (async () => {
      await refresh();
    })();
  }, [refresh]);

  return (
    <div className="mx-auto w-full max-w-4xl flex-1 px-4 py-8">
      <div className="overflow-hidden rounded-lg border border-zinc-200 shadow-sm dark:border-zinc-800">
        <div className="flex items-center justify-between bg-[#0b3d5c] px-6 py-4">
          <div>
            <h1 className="text-lg font-semibold text-white">Tracking Sources</h1>
            <p className="text-xs text-white/70">Settings · Manage vessel-tracking website sources</p>
          </div>
          <Link
            href="/"
            className="rounded-md bg-white/10 px-3 py-1.5 text-sm font-medium text-white hover:bg-white/20"
          >
            Back to Dashboard
          </Link>
        </div>

        <div className="bg-amber-50 px-6 py-3 text-xs text-amber-800 dark:bg-amber-950 dark:text-amber-300">
          Only the Mock Tracking Feed is actually polled right now — MarineTraffic, VesselFinder, and Polestar
          GMDA have no free public API and no credentials are configured yet, so they&apos;re catalogued here but
          marked &quot;Not yet connected&quot;. Toggling the Mock Tracking Feed on/off pauses or resumes the
          simulated updates driving the dashboard.
        </div>

        {error && (
          <div className="border-b border-amber-200 bg-amber-50 px-6 py-2 text-sm text-amber-800">{error}</div>
        )}

        <div className="bg-white dark:bg-zinc-900">
          {loading ? (
            <div className="px-6 py-16 text-center text-sm text-zinc-500">Loading…</div>
          ) : (
            <table className="w-full text-sm">
              <thead className="border-b border-zinc-200 text-left text-xs uppercase tracking-wide text-zinc-500 dark:border-zinc-800">
                <tr>
                  <th className="px-6 py-3">Name</th>
                  <th className="px-6 py-3">URL</th>
                  <th className="px-6 py-3">Kind</th>
                  <th className="px-6 py-3">Status</th>
                  <th className="px-6 py-3" />
                </tr>
              </thead>
              <tbody>
                {sources.map((source) => (
                  <SourceRow key={source.id} source={source} onChanged={refresh} />
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="border-t border-zinc-200 bg-zinc-50 px-6 py-4 dark:border-zinc-800 dark:bg-zinc-900">
          {showAddForm ? (
            <AddSourceForm
              onCancel={() => setShowAddForm(false)}
              onCreated={() => {
                setShowAddForm(false);
                refresh();
              }}
            />
          ) : (
            <button
              onClick={() => setShowAddForm(true)}
              className="rounded-md bg-[#1f8a4c] px-4 py-2 text-sm font-medium text-white hover:bg-[#1a7642]"
            >
              + Add Source
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function SourceRow({ source, onChanged }: { source: TrackingSource; onChanged: () => void }) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(source.name);
  const [url, setUrl] = useState(source.url);
  const [busy, setBusy] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [rowError, setRowError] = useState<string | null>(null);

  const isConnected = source.adapter_key === "mock";

  async function toggleEnabled() {
    setBusy(true);
    setRowError(null);
    try {
      await updateTrackingSource(source.id, { enabled: !source.enabled });
      onChanged();
    } catch (err) {
      setRowError(err instanceof ApiError ? err.message : "Failed to update source");
    } finally {
      setBusy(false);
    }
  }

  async function saveEdits() {
    setBusy(true);
    setRowError(null);
    try {
      await updateTrackingSource(source.id, { name, url });
      setEditing(false);
      onChanged();
    } catch (err) {
      setRowError(err instanceof ApiError ? err.message : "Failed to update source");
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete() {
    setBusy(true);
    setRowError(null);
    try {
      await deleteTrackingSource(source.id);
      onChanged();
    } catch (err) {
      setRowError(err instanceof ApiError ? err.message : "Failed to delete source");
      setBusy(false);
    }
  }

  return (
    <tr className="border-b border-zinc-100 last:border-b-0 dark:border-zinc-800">
      <td className="px-6 py-3">
        {editing ? (
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full rounded border border-zinc-300 px-2 py-1 dark:border-zinc-700 dark:bg-zinc-800"
          />
        ) : (
          <span className="font-medium">{source.name}</span>
        )}
      </td>
      <td className="max-w-xs truncate px-6 py-3 text-zinc-500" title={source.url}>
        {editing ? (
          <input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            className="w-full rounded border border-zinc-300 px-2 py-1 dark:border-zinc-700 dark:bg-zinc-800"
          />
        ) : (
          source.url
        )}
      </td>
      <td className="px-6 py-3 text-zinc-500">{source.kind}</td>
      <td className="px-6 py-3">
        <div className="flex flex-col gap-1">
          <label className="flex items-center gap-2">
            <input type="checkbox" checked={source.enabled} disabled={busy} onChange={toggleEnabled} />
            <span>{source.enabled ? "Enabled" : "Disabled"}</span>
          </label>
          {!isConnected && (
            <span className="w-fit rounded bg-zinc-100 px-2 py-0.5 text-xs text-zinc-500 dark:bg-zinc-800">
              Not yet connected
            </span>
          )}
          {rowError && <span className="text-xs text-red-600">{rowError}</span>}
        </div>
      </td>
      <td className="px-6 py-3">
        {confirmingDelete ? (
          <div className="flex items-center gap-2 whitespace-nowrap">
            <span className="text-xs">Delete?</span>
            <button
              onClick={handleDelete}
              disabled={busy}
              className="rounded bg-red-600 px-2 py-1 text-xs font-medium text-white hover:bg-red-700 disabled:opacity-50"
            >
              Yes
            </button>
            <button
              onClick={() => setConfirmingDelete(false)}
              disabled={busy}
              className="rounded border border-zinc-300 px-2 py-1 text-xs font-medium dark:border-zinc-700"
            >
              No
            </button>
          </div>
        ) : editing ? (
          <div className="flex items-center gap-2 whitespace-nowrap">
            <button
              onClick={saveEdits}
              disabled={busy}
              className="rounded bg-[#0b3d5c] px-2 py-1 text-xs font-medium text-white hover:bg-[#0a3450] disabled:opacity-50"
            >
              Save
            </button>
            <button
              onClick={() => {
                setEditing(false);
                setName(source.name);
                setUrl(source.url);
              }}
              disabled={busy}
              className="rounded border border-zinc-300 px-2 py-1 text-xs font-medium dark:border-zinc-700"
            >
              Cancel
            </button>
          </div>
        ) : (
          <div className="flex items-center gap-2 whitespace-nowrap">
            <button
              onClick={() => setEditing(true)}
              className="rounded border border-zinc-300 px-2 py-1 text-xs font-medium hover:bg-zinc-100 dark:border-zinc-700 dark:hover:bg-zinc-800"
            >
              Edit
            </button>
            <button
              onClick={() => setConfirmingDelete(true)}
              className="rounded border border-red-300 px-2 py-1 text-xs font-medium text-red-700 hover:bg-red-50 dark:border-red-900 dark:text-red-400 dark:hover:bg-red-950"
            >
              Remove
            </button>
          </div>
        )}
      </td>
    </tr>
  );
}

function AddSourceForm({ onCancel, onCreated }: { onCancel: () => void; onCreated: () => void }) {
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [kind, setKind] = useState("vessel");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      // New sources are catalogued as "unavailable" until a real adapter backs them -
      // only the seeded Mock Tracking Feed uses adapter_key="mock" (Section 3.9 rationale).
      await createTrackingSource({ name, url, kind, adapter_key: "unavailable", enabled: false });
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to add source");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-wrap items-end gap-3">
      <div>
        <label className="block text-xs font-semibold uppercase tracking-wide text-zinc-500">Name</label>
        <input
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g. Shipping Line Tracker"
          className="mt-1 w-56 rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
        />
      </div>
      <div>
        <label className="block text-xs font-semibold uppercase tracking-wide text-zinc-500">URL</label>
        <input
          required
          type="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://…"
          className="mt-1 w-64 rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
        />
      </div>
      <div>
        <label className="block text-xs font-semibold uppercase tracking-wide text-zinc-500">Kind</label>
        <select
          value={kind}
          onChange={(e) => setKind(e.target.value)}
          className="mt-1 rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
        >
          <option value="vessel">Vessel</option>
          <option value="container">Container</option>
        </select>
      </div>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={onCancel}
          className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium dark:border-zinc-700"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={submitting}
          className="rounded-md bg-[#1f8a4c] px-4 py-2 text-sm font-medium text-white hover:bg-[#1a7642] disabled:opacity-50"
        >
          {submitting ? "Adding…" : "Add Source"}
        </button>
      </div>
      {error && <p className="w-full text-sm text-red-600">{error}</p>}
    </form>
  );
}
