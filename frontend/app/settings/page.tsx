"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  ApiError,
  createTrackingSource,
  deleteTrackingSource,
  listTrackingSources,
  listUsers,
  TrackingSource,
  updateTrackingSource,
  updateUserRole,
  User,
} from "@/lib/api";
import { useAuth } from "@/app/components/AuthProvider";
import UserMenu from "@/app/components/UserMenu";

type SettingsTab = "sources" | "users";

// Admin-only Settings page at "/settings" (Section 3.9 + user-role management). AuthProvider
// already redirects non-admins away before this ever renders, so no role check is needed here.
export default function SettingsPage() {
  const [tab, setTab] = useState<SettingsTab>("sources");

  return (
    <div className="mx-auto w-full max-w-4xl flex-1 px-4 py-8">
      <div className="overflow-hidden rounded-lg border border-zinc-200 shadow-sm dark:border-zinc-800">
        <div className="flex items-center justify-between bg-[#0b3d5c] px-6 py-4">
          <div>
            <h1 className="text-lg font-semibold text-white">Settings</h1>
            <p className="text-xs text-white/70">Admin-only · Tracking sources and user roles</p>
          </div>
          <div className="flex items-center gap-3">
            <UserMenu />
            <Link
              href="/"
              className="rounded-md bg-white/10 px-3 py-1.5 text-sm font-medium text-white hover:bg-white/20"
            >
              Back to Dashboard
            </Link>
          </div>
        </div>

        <div className="flex gap-2 border-b border-zinc-200 bg-white px-6 pt-3 dark:border-zinc-800 dark:bg-zinc-900">
          <SettingsTabButton active={tab === "sources"} onClick={() => setTab("sources")}>
            Tracking Sources
          </SettingsTabButton>
          <SettingsTabButton active={tab === "users"} onClick={() => setTab("users")}>
            Users
          </SettingsTabButton>
        </div>

        {tab === "sources" ? <TrackingSourcesTab /> : <UsersTab />}
      </div>
    </div>
  );
}

// "Tracking Sources" / "Users" tab button.
function SettingsTabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`rounded-t-md px-4 py-2 text-sm font-medium ${
        active
          ? "border-b-2 border-[#0b3d5c] text-[#0b3d5c] dark:text-white"
          : "text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300"
      }`}
    >
      {children}
    </button>
  );
}

// Settings → Tracking Sources tab (Section 3.9): list/add/edit/remove tracking sources, plus a
// client-side search over the already-fetched list (small, fixed-size catalogue - no need for
// a server round-trip per keystroke like the dashboard's search).
function TrackingSourcesTab() {
  const [sources, setSources] = useState<TrackingSource[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [search, setSearch] = useState("");

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

  // Matches on name or URL only, not Kind - deliberately, since Kind already has its own
  // visible column and isn't what an admin would be searching for.
  const filteredSources = sources.filter((s) => {
    const q = search.trim().toLowerCase();
    if (!q) return true;
    return s.name.toLowerCase().includes(q) || s.url.toLowerCase().includes(q);
  });

  return (
    <>
      <div className="bg-amber-50 px-6 py-3 text-xs text-amber-800 dark:bg-amber-950 dark:text-amber-300">
        Only the Mock Tracking Feed is actually polled right now — MarineTraffic, VesselFinder, and Polestar
        GMDA have no free public API and no credentials are configured yet, so they&apos;re catalogued here but
        marked &quot;Not yet connected&quot;. Toggling the Mock Tracking Feed on/off pauses or resumes the
        simulated updates driving the dashboard.
      </div>

      <div className="border-b border-zinc-200 bg-white px-6 py-3 dark:border-zinc-800 dark:bg-zinc-900">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search sources by name or URL…"
          className="w-64 rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-800"
        />
      </div>

      {error && (
        <div className="border-b border-amber-200 bg-amber-50 px-6 py-2 text-sm text-amber-800">{error}</div>
      )}

      <div className="bg-white dark:bg-zinc-900">
        {loading ? (
          <div className="px-6 py-16 text-center text-sm text-zinc-500">Loading…</div>
        ) : filteredSources.length === 0 ? (
          <div className="px-6 py-16 text-center text-sm text-zinc-500">No sources match &quot;{search}&quot;.</div>
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
              {filteredSources.map((source) => (
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
    </>
  );
}

// Settings → Users tab: list every account and promote/demote roles, with a client-side email
// search. `currentUser` (from AuthProvider) is needed to know which row is "you" and to refresh
// global auth state on self-demotion (see UserRow below).
function UsersTab() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const refresh = useCallback(async () => {
    try {
      const data = await listUsers();
      setUsers(data);
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

  // Computed from the full list, not the filtered one - the last-admin guard must hold
  // regardless of what the search box currently matches.
  const adminCount = users.filter((u) => u.role === "admin").length;

  const filteredUsers = users.filter((u) => {
    const q = search.trim().toLowerCase();
    return !q || u.email.toLowerCase().includes(q);
  });

  return (
    <>
      <div className="bg-amber-50 px-6 py-3 text-xs text-amber-800 dark:bg-amber-950 dark:text-amber-300">
        Registering never grants admin — the first admin is created via the <code>promote-admin</code> terminal
        command. From here, existing admins can promote or demote anyone else; the last remaining admin can&apos;t
        be demoted, or no one would be able to manage roles anymore.
      </div>

      <div className="border-b border-zinc-200 bg-white px-6 py-3 dark:border-zinc-800 dark:bg-zinc-900">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search users by email…"
          className="w-64 rounded-md border border-zinc-300 px-3 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-800"
        />
      </div>

      {error && (
        <div className="border-b border-amber-200 bg-amber-50 px-6 py-2 text-sm text-amber-800">{error}</div>
      )}

      <div className="bg-white dark:bg-zinc-900">
        {loading ? (
          <div className="px-6 py-16 text-center text-sm text-zinc-500">Loading…</div>
        ) : filteredUsers.length === 0 ? (
          <div className="px-6 py-16 text-center text-sm text-zinc-500">No users match &quot;{search}&quot;.</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="border-b border-zinc-200 text-left text-xs uppercase tracking-wide text-zinc-500 dark:border-zinc-800">
              <tr>
                <th className="px-6 py-3">Email</th>
                <th className="px-6 py-3">Role</th>
                <th className="px-6 py-3">Registered</th>
                <th className="px-6 py-3" />
              </tr>
            </thead>
            <tbody>
              {filteredUsers.map((u) => (
                <UserRow
                  key={u.id}
                  user={u}
                  isSelf={u.id === currentUser?.id}
                  isLastAdmin={u.role === "admin" && adminCount <= 1}
                  onChanged={refresh}
                />
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

// One row in the Users table - the Promote/Demote button and its confirmation-free toggle
// action. `isLastAdmin` is computed by the parent from the *unfiltered* user list (see
// UsersTab's adminCount above) so the guard stays correct regardless of the current search.
function UserRow({
  user,
  isSelf,
  isLastAdmin,
  onChanged,
}: {
  user: User;
  isSelf: boolean;
  isLastAdmin: boolean;
  onChanged: () => void;
}) {
  const { refresh: refreshAuth } = useAuth();
  const [busy, setBusy] = useState(false);
  const [rowError, setRowError] = useState<string | null>(null);

  /** Flip this user's role. The backend rejects demoting the last admin with a 409 regardless
   * of what the `isLastAdmin` prop already disabled client-side - that's the actual source of
   * truth, this UI state is just for a better error-free experience. */
  async function toggleRole() {
    setBusy(true);
    setRowError(null);
    try {
      await updateUserRole(user.id, user.role === "admin" ? "user" : "admin");
      if (isSelf) {
        // Demoting yourself revokes admin on this same session immediately - refresh the
        // global auth state so AuthProvider's redirect-away-from-/settings logic takes over,
        // instead of leaving this page showing a stale "admin access required" error.
        await refreshAuth();
      } else {
        onChanged();
      }
    } catch (err) {
      setRowError(err instanceof ApiError ? err.message : "Failed to update role");
    } finally {
      setBusy(false);
    }
  }

  return (
    <tr className="border-b border-zinc-100 last:border-b-0 dark:border-zinc-800">
      <td className="px-6 py-3 font-medium">
        {user.email}
        {isSelf && <span className="ml-2 text-xs font-normal text-zinc-400">(you)</span>}
      </td>
      <td className="px-6 py-3">
        <span
          className={`rounded px-2 py-0.5 text-xs font-medium ${
            user.role === "admin"
              ? "bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300"
              : "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400"
          }`}
        >
          {user.role}
        </span>
      </td>
      <td className="px-6 py-3 text-zinc-500">{new Date(user.created_at).toLocaleDateString()}</td>
      <td className="px-6 py-3">
        <div className="flex flex-col items-start gap-1">
          <button
            onClick={toggleRole}
            disabled={busy || (user.role === "admin" && isLastAdmin)}
            title={user.role === "admin" && isLastAdmin ? "Cannot demote the last remaining admin" : undefined}
            className="rounded border border-zinc-300 px-2 py-1 text-xs font-medium hover:bg-zinc-100 disabled:cursor-not-allowed disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-800"
          >
            {user.role === "admin" ? "Demote to user" : "Promote to admin"}
          </button>
          {rowError && <span className="text-xs text-red-600">{rowError}</span>}
        </div>
      </td>
    </tr>
  );
}

// One row in the Tracking Sources table - inline edit (name/URL), enabled/disabled toggle, and
// a two-step delete confirmation, all self-contained per row.
function SourceRow({ source, onChanged }: { source: TrackingSource; onChanged: () => void }) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(source.name);
  const [url, setUrl] = useState(source.url);
  const [busy, setBusy] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [rowError, setRowError] = useState<string | null>(null);

  // Only the seeded mock source is ever actually polled - every other source (including any
  // new one an admin adds here) is catalogued but inert, hence the "Not yet connected" badge.
  const isConnected = source.adapter_key === "mock";

  /** Toggling this is what actually pauses/resumes the tracking worker for the mock source -
   * see backend services/tracking_worker.py's `mock_source_enabled` check. */
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

// Inline "+ Add Source" form (Section 3.9), shown instead of the button once clicked. New
// sources are always inert (see the `adapter_key: "unavailable"` comment below) - there's no
// way to add a *functional* new source through the UI, since that would require real adapter
// code, not just a database row.
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
