"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  ApiError,
  createTrackingSource,
  deleteTrackingSource,
  getNotificationSettings,
  listNotificationLog,
  listTrackingSources,
  listUsers,
  NotificationLogEntry,
  NotificationSettings,
  sendDailyReportNow,
  testNotifications,
  TrackingSource,
  updateNotificationSettings,
  updateTrackingSource,
  updateUserRole,
  User,
} from "@/lib/api";
import { useAuth } from "@/app/components/AuthProvider";
import UserMenu from "@/app/components/UserMenu";

type SettingsTab = "sources" | "users" | "notifications";

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
            <p className="text-xs text-white/70">Admin-only · Tracking sources, user roles, and notifications</p>
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
          <SettingsTabButton active={tab === "notifications"} onClick={() => setTab("notifications")}>
            Notifications
          </SettingsTabButton>
        </div>

        {tab === "sources" ? <TrackingSourcesTab /> : tab === "users" ? <UsersTab /> : <NotificationsTab />}
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
        Only the Mock Tracking Feed (vessels) and Mock Booking Feed (containers, Section 4) are actually polled
        right now — MarineTraffic, VesselFinder, Polestar GMDA, and the five carrier booking portals (ONE,
        Maersk, MSC, CMA CGM, InterAsia) have no free public API and no credentials are configured yet, so
        they&apos;re catalogued here but marked &quot;Not yet connected&quot;. Toggling either mock source on/off
        pauses or resumes its simulated updates.
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
        {user.microsoft_linked && (
          <span
            className="ml-2 rounded bg-zinc-100 px-1.5 py-0.5 text-xs font-normal text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400"
            title="Can sign in via Microsoft"
          >
            Microsoft
          </span>
        )}
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

  // Only the two seeded mock sources (vessel + booking, Section 4) are ever actually polled -
  // every other source (including any new one an admin adds here) is catalogued but inert,
  // hence the "Not yet connected" badge.
  const isConnected = source.adapter_key === "mock" || source.adapter_key === "mock_booking";

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

// Settings → Notifications tab (Section 6.C event alerts + Phase 4's daily report). Three
// independent cards - Email, Microsoft Teams, Daily Report - each save separately via a partial
// PATCH, plus a "recent activity" log so an admin can verify a channel is actually working.
function NotificationsTab() {
  const [settings, setSettings] = useState<NotificationSettings | null>(null);
  const [log, setLog] = useState<NotificationLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [testResult, setTestResult] = useState<string | null>(null);
  const [testing, setTesting] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [settingsData, logData] = await Promise.all([getNotificationSettings(), listNotificationLog()]);
      setSettings(settingsData);
      setLog(logData);
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

  async function handleTest() {
    setTesting(true);
    setTestResult(null);
    try {
      const entries = await testNotifications();
      setTestResult(
        entries.length === 0
          ? "No channels are enabled - turn on Email or Teams below first."
          : entries.map((e) => `${e.channel}: ${e.status}`).join(", "),
      );
      await refresh();
    } catch (err) {
      setTestResult(err instanceof ApiError ? err.message : "Failed to send test notification");
    } finally {
      setTesting(false);
    }
  }

  async function handleSendDailyReportNow() {
    setTesting(true);
    setTestResult(null);
    try {
      const entries = await sendDailyReportNow();
      setTestResult(
        entries.length === 0
          ? "No channels are enabled - turn on Email or Teams below first."
          : `Daily report sent: ${entries.map((e) => `${e.channel}: ${e.status}`).join(", ")}`,
      );
      await refresh();
    } catch (err) {
      setTestResult(err instanceof ApiError ? err.message : "Failed to send daily report");
    } finally {
      setTesting(false);
    }
  }

  if (loading || !settings) {
    return <div className="px-6 py-16 text-center text-sm text-zinc-500">Loading…</div>;
  }

  return (
    <>
      <div className="bg-amber-50 px-6 py-3 text-xs text-amber-800 dark:bg-amber-950 dark:text-amber-300">
        Triggered on vessel arrival, departure, and arrival at destination (Section 6.C). ETA-change and delay
        alerts aren&apos;t included — this app doesn&apos;t track a planned ETA to compare against, the same reason
        the dashboard itself never shows a &quot;Delayed&quot; status (Section 3.10). Every attempt is logged below,
        including when a channel is enabled but not fully configured.
      </div>

      {error && <div className="border-b border-amber-200 bg-amber-50 px-6 py-2 text-sm text-amber-800">{error}</div>}

      <div className="grid grid-cols-1 gap-4 bg-white px-6 py-4 md:grid-cols-2 dark:bg-zinc-900">
        <EmailSettingsCard settings={settings} onSaved={refresh} />
        <TeamsSettingsCard settings={settings} onSaved={refresh} />
      </div>

      <div className="bg-white px-6 pb-4 dark:bg-zinc-900">
        <DailyReportCard settings={settings} onSaved={refresh} />
      </div>

      <div className="flex flex-wrap items-center gap-3 border-t border-zinc-200 bg-zinc-50 px-6 py-4 dark:border-zinc-800 dark:bg-zinc-900">
        <button
          onClick={handleTest}
          disabled={testing}
          className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-800"
        >
          {testing ? "Sending…" : "Send Test Notification"}
        </button>
        <button
          onClick={handleSendDailyReportNow}
          disabled={testing}
          className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:hover:bg-zinc-800"
        >
          {testing ? "Sending…" : "Send Daily Report Now"}
        </button>
        {testResult && <span className="text-sm text-zinc-600 dark:text-zinc-400">{testResult}</span>}
      </div>

      <div className="border-t border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
        <h2 className="px-6 pt-4 text-sm font-semibold text-zinc-700 dark:text-zinc-300">Recent Activity</h2>
        {log.length === 0 ? (
          <p className="px-6 py-8 text-center text-sm text-zinc-500">
            No notifications sent yet - they&apos;ll show up here once a vessel event fires or you send a test.
          </p>
        ) : (
          <table className="w-full text-sm">
            <thead className="border-b border-zinc-200 text-left text-xs uppercase tracking-wide text-zinc-500 dark:border-zinc-800">
              <tr>
                <th className="px-6 py-3">When</th>
                <th className="px-6 py-3">Channel</th>
                <th className="px-6 py-3">Status</th>
                <th className="px-6 py-3">Subject</th>
                <th className="px-6 py-3">Vessel</th>
                <th className="px-6 py-3">Detail</th>
              </tr>
            </thead>
            <tbody>
              {log.map((entry) => (
                <tr key={entry.id} className="border-b border-zinc-100 last:border-b-0 dark:border-zinc-800">
                  <td className="px-6 py-3 text-zinc-500">{new Date(entry.created_at).toLocaleString()}</td>
                  <td className="px-6 py-3 capitalize">{entry.channel}</td>
                  <td className="px-6 py-3">
                    <span
                      className={`rounded px-2 py-0.5 text-xs font-medium ${
                        entry.status === "sent"
                          ? "bg-green-50 text-green-700 dark:bg-green-950 dark:text-green-300"
                          : entry.status === "skipped"
                            ? "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400"
                            : "bg-red-50 text-red-700 dark:bg-red-950 dark:text-red-300"
                      }`}
                    >
                      {entry.status}
                    </span>
                  </td>
                  <td className="px-6 py-3">{entry.subject}</td>
                  <td className="px-6 py-3 text-zinc-500">{entry.vessel_name ?? "—"}</td>
                  <td className="max-w-xs truncate px-6 py-3 text-zinc-500" title={entry.detail ?? undefined}>
                    {entry.detail ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

// Email channel config card. `password` starts blank regardless of whether one is already
// stored (see NotificationSettings.smtp_password_set) - leaving it blank on save keeps the
// existing stored password untouched (see updateNotificationSettings's partial-PATCH contract).
function EmailSettingsCard({ settings, onSaved }: { settings: NotificationSettings; onSaved: () => void }) {
  const [enabled, setEnabled] = useState(settings.email_enabled);
  const [host, setHost] = useState(settings.smtp_host ?? "");
  const [port, setPort] = useState(settings.smtp_port);
  const [username, setUsername] = useState(settings.smtp_username ?? "");
  const [password, setPassword] = useState("");
  const [fromAddress, setFromAddress] = useState(settings.smtp_from_address ?? "");
  const [recipients, setRecipients] = useState(settings.email_recipients ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      await updateNotificationSettings({
        email_enabled: enabled,
        smtp_host: host,
        smtp_port: port,
        smtp_username: username,
        // Omit smtp_password entirely when left blank, rather than sending an empty string
        // that would overwrite a previously-saved password with nothing.
        ...(password ? { smtp_password: password } : {}),
        smtp_from_address: fromAddress,
        email_recipients: recipients,
      });
      setPassword("");
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save email settings");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
      <label className="mb-3 flex items-center gap-2 text-sm font-semibold">
        <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
        Email
      </label>
      <div className="space-y-2">
        <FieldRow label="SMTP Host" value={host} onChange={setHost} placeholder="smtp.example.com" />
        <FieldRow label="SMTP Port" value={String(port)} onChange={(v) => setPort(Number(v) || 587)} />
        <FieldRow label="Username" value={username} onChange={setUsername} />
        <FieldRow
          label="Password"
          value={password}
          onChange={setPassword}
          type="password"
          placeholder={settings.smtp_password_set ? "•••••••• (unchanged)" : ""}
        />
        <FieldRow label="From Address" value={fromAddress} onChange={setFromAddress} placeholder="alerts@example.com" />
        <FieldRow
          label="Recipients"
          value={recipients}
          onChange={setRecipients}
          placeholder="ops@example.com, second@example.com"
        />
      </div>
      {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
      <button
        onClick={handleSave}
        disabled={saving}
        className="mt-3 rounded-md bg-[#0b3d5c] px-3 py-1.5 text-xs font-medium text-white hover:bg-[#0a3450] disabled:opacity-50"
      >
        {saving ? "Saving…" : "Save Email Settings"}
      </button>
    </div>
  );
}

// Microsoft Teams channel config card - just an incoming-webhook URL (Section 6.C).
function TeamsSettingsCard({ settings, onSaved }: { settings: NotificationSettings; onSaved: () => void }) {
  const [enabled, setEnabled] = useState(settings.teams_enabled);
  const [webhookUrl, setWebhookUrl] = useState(settings.teams_webhook_url ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      await updateNotificationSettings({ teams_enabled: enabled, teams_webhook_url: webhookUrl });
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save Teams settings");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
      <label className="mb-3 flex items-center gap-2 text-sm font-semibold">
        <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
        Microsoft Teams
      </label>
      <div className="space-y-2">
        <FieldRow
          label="Webhook URL"
          value={webhookUrl}
          onChange={setWebhookUrl}
          placeholder="https://…webhook.office.com/…"
        />
      </div>
      {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
      <button
        onClick={handleSave}
        disabled={saving}
        className="mt-3 rounded-md bg-[#0b3d5c] px-3 py-1.5 text-xs font-medium text-white hover:bg-[#0a3450] disabled:opacity-50"
      >
        {saving ? "Saving…" : "Save Teams Settings"}
      </button>
    </div>
  );
}

// Daily report schedule card (Phase 4 / Section 7) - what hour (UTC) to send, and when it last
// actually went out, so an admin can confirm the schedule is really running day to day.
function DailyReportCard({ settings, onSaved }: { settings: NotificationSettings; onSaved: () => void }) {
  const [enabled, setEnabled] = useState(settings.daily_report_enabled);
  const [hour, setHour] = useState(settings.daily_report_hour_utc);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSave() {
    setSaving(true);
    setError(null);
    try {
      await updateNotificationSettings({ daily_report_enabled: enabled, daily_report_hour_utc: hour });
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save report schedule");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800">
      <label className="mb-3 flex items-center gap-2 text-sm font-semibold">
        <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
        Daily Report
      </label>
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <label className="flex items-center gap-2">
          Send at
          <select
            value={hour}
            onChange={(e) => setHour(Number(e.target.value))}
            className="rounded-md border border-zinc-300 px-2 py-1 text-sm dark:border-zinc-700 dark:bg-zinc-800"
          >
            {Array.from({ length: 24 }, (_, h) => (
              <option key={h} value={h}>
                {String(h).padStart(2, "0")}:00 UTC
              </option>
            ))}
          </select>
        </label>
        <span className="text-xs text-zinc-500">
          Last sent: {settings.daily_report_last_sent_date ?? "never"}
        </span>
      </div>
      {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
      <button
        onClick={handleSave}
        disabled={saving}
        className="mt-3 rounded-md bg-[#0b3d5c] px-3 py-1.5 text-xs font-medium text-white hover:bg-[#0a3450] disabled:opacity-50"
      >
        {saving ? "Saving…" : "Save Report Schedule"}
      </button>
    </div>
  );
}

// Shared label+input row used by the three settings cards above.
function FieldRow({
  label,
  value,
  onChange,
  placeholder,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  type?: string;
}) {
  return (
    <div>
      <label className="block text-xs font-semibold uppercase tracking-wide text-zinc-500">{label}</label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="mt-1 w-full rounded-md border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-800"
      />
    </div>
  );
}
