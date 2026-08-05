// Thin typed wrapper around the backend REST API. Every exported function here corresponds to
// exactly one backend endpoint (see backend/app/routers/*.py) - components call these instead
// of using `fetch` directly, so the request shape, auth cookie handling, and error handling
// only need to be right in one place.

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// Mirrors backend/app/models.py's EventType enum exactly - keep these in sync by hand, since
// the two sides aren't code-generated from a shared source.
export type EventType =
  | "sailing"
  | "at_port"
  | "eta_destination"
  | "arrived_destination"
  | "sailed_from_destination";

export type UserRole = "user" | "admin";

export interface User {
  id: number;
  email: string;
  role: UserRole;
  created_at: string;
}

// Matches backend VesselOut - a vessel's own fields plus its latest event flattened in
// (current_location/last_event_*/source_name), so no separate lookup is needed to show a
// vessel's current status.
export interface Vessel {
  id: number;
  name: string;
  imo_number: string;
  destination_port: string | null;
  created_at: string;
  archived_at: string | null;
  current_location: string | null;
  last_event_type: EventType | null;
  last_event_text: string | null;
  last_event_at: string | null;
  source_name: string | null;
}

export interface TrackingSource {
  id: number;
  name: string;
  url: string;
  kind: string;
  adapter_key: string;
  enabled: boolean;
}

// One row of a vessel's movement timeline (Section 3.5).
export interface StatusEvent {
  id: number;
  event_type: EventType;
  current_location: string;
  last_event_text: string;
  source_name: string;
  occurred_at: string;
  recorded_at: string;
}

export interface VesselHistory {
  vessel: Vessel;
  timeline: StatusEvent[];
}

// One row of a bulk-upload preview (Section 3.2), before the user has confirmed import.
export interface BulkUploadRow {
  row_number: number;
  name: string | null;
  imo_number: string | null;
  destination_port: string | null;
  status: "ok" | "duplicate" | "invalid";
  message: string | null;
}

export interface BulkImportResult {
  imported: Vessel[];
  skipped: BulkUploadRow[];
}

// Matches backend NotificationSettingsOut - `smtp_password_set` stands in for the actual
// password, which the API never sends back (see backend/app/schemas.py's docstring).
export interface NotificationSettings {
  email_enabled: boolean;
  smtp_host: string | null;
  smtp_port: number;
  smtp_username: string | null;
  smtp_password_set: boolean;
  smtp_from_address: string | null;
  email_recipients: string | null;
  teams_enabled: boolean;
  teams_webhook_url: string | null;
  daily_report_enabled: boolean;
  daily_report_hour_utc: number;
  daily_report_last_sent_date: string | null;
}

export type NotificationChannelKind = "email" | "teams";
export type NotificationLogStatus = "sent" | "skipped" | "failed";

// One row of the Settings → Notifications "recent activity" table.
export interface NotificationLogEntry {
  id: number;
  channel: NotificationChannelKind;
  status: NotificationLogStatus;
  subject: string;
  vessel_name: string | null;
  vessel_imo: string | null;
  detail: string | null;
  created_at: string;
}

// Matches backend ReportSummaryOut (Section 7 / Phase 4) - the same three vessel-category
// lists shown on the Reports page and behind both file exports.
export interface ReportSummary {
  active: Vessel[];
  eta_to_destination: Vessel[];
  arrived_at_destination: Vessel[];
  generated_at: string;
}

/** Thrown by every API call below on a non-2xx response, carrying the HTTP status and the
 * backend's error `detail` message (falling back to the status text if the body isn't JSON). */
class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

/** Shared response handling for every apiFetch call: throws ApiError on failure, returns
 * parsed JSON on success (or undefined for a 204 No Content). */
async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      // no JSON body
    }
    throw new ApiError(detail, res.status);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// Every request carries the session cookie - the backend gates almost everything behind
// authentication (and Settings/tracking-sources behind the admin role), so this can't be
// opt-in per call.
function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  return fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: "include",
    // Skip setting Content-Type for FormData bodies (bulk-upload file uploads) - the browser
    // needs to set its own multipart boundary, which providing our own header would break.
    headers: init?.body && !(init.body instanceof FormData) ? { "Content-Type": "application/json", ...init.headers } : init?.headers,
  });
}

export async function register(input: {
  email: string;
  password: string;
  confirm_password: string;
}): Promise<User> {
  return handle(await apiFetch("/api/auth/register", { method: "POST", body: JSON.stringify(input) }));
}

export async function login(input: { email: string; password: string }): Promise<User> {
  return handle(await apiFetch("/api/auth/login", { method: "POST", body: JSON.stringify(input) }));
}

export async function logout(): Promise<void> {
  return handle(await apiFetch("/api/auth/logout", { method: "POST" }));
}

/** Who's currently logged in, based on the session cookie - used by AuthProvider on every page
 * load. Rejects with a 401 ApiError when nobody is logged in. */
export async function getCurrentUser(): Promise<User> {
  return handle(await apiFetch("/api/auth/me", { cache: "no-store" }));
}

export async function listUsers(): Promise<User[]> {
  return handle(await apiFetch("/api/users", { cache: "no-store" }));
}

export async function updateUserRole(id: number, role: UserRole): Promise<User> {
  return handle(await apiFetch(`/api/users/${id}/role`, { method: "PATCH", body: JSON.stringify({ role }) }));
}

/** List vessels for the dashboard. `query` is the free-text search (6.A), `archived` switches
 * between the Active/Archived tabs, and `status` is a 6.D filter chip - all three compose as an
 * AND when combined, matching the backend's GET /api/vessels query params. */
export async function listVessels(opts?: {
  query?: string;
  archived?: boolean;
  status?: EventType;
}): Promise<Vessel[]> {
  const url = new URL(`${API_BASE}/api/vessels`);
  if (opts?.query) url.searchParams.set("q", opts.query);
  if (opts?.archived) url.searchParams.set("archived", "true");
  if (opts?.status) url.searchParams.set("status", opts.status);
  return handle(await apiFetch(url.pathname + url.search, { cache: "no-store" }));
}

export async function archiveVessel(imo: string): Promise<Vessel> {
  return handle(await apiFetch(`/api/vessels/${imo}/archive`, { method: "POST" }));
}

export async function removeVessel(imo: string): Promise<void> {
  return handle(await apiFetch(`/api/vessels/${imo}`, { method: "DELETE" }));
}

export async function createVessel(input: {
  name: string;
  imo_number: string;
  destination_port?: string | null;
}): Promise<Vessel> {
  return handle(await apiFetch("/api/vessels", { method: "POST", body: JSON.stringify(input) }));
}

export async function getVesselHistory(imo: string): Promise<VesselHistory> {
  return handle(await apiFetch(`/api/vessels/${imo}/history`, { cache: "no-store" }));
}

/** Upload a .xlsx/.csv/.pdf for the editable bulk-upload preview (Section 3.2) - doesn't
 * import anything yet, see importBulkRows. */
export async function previewBulkUpload(file: File): Promise<{ rows: BulkUploadRow[] }> {
  const formData = new FormData();
  formData.append("file", file);
  return handle(await apiFetch("/api/vessels/bulk/preview", { method: "POST", body: formData }));
}

/** Actually create vessels from rows the user has reviewed in the preview table. */
export async function importBulkRows(
  rows: { name: string; imo_number: string; destination_port?: string | null }[],
): Promise<BulkImportResult> {
  return handle(await apiFetch("/api/vessels/bulk/import", { method: "POST", body: JSON.stringify({ rows }) }));
}

export async function listTrackingSources(): Promise<TrackingSource[]> {
  return handle(await apiFetch("/api/tracking-sources", { cache: "no-store" }));
}

export async function createTrackingSource(input: {
  name: string;
  url: string;
  kind?: string;
  adapter_key?: string;
  enabled?: boolean;
}): Promise<TrackingSource> {
  return handle(await apiFetch("/api/tracking-sources", { method: "POST", body: JSON.stringify(input) }));
}

export async function updateTrackingSource(
  id: number,
  patch: Partial<Pick<TrackingSource, "name" | "url" | "kind" | "adapter_key" | "enabled">>,
): Promise<TrackingSource> {
  return handle(await apiFetch(`/api/tracking-sources/${id}`, { method: "PATCH", body: JSON.stringify(patch) }));
}

export async function deleteTrackingSource(id: number): Promise<void> {
  return handle(await apiFetch(`/api/tracking-sources/${id}`, { method: "DELETE" }));
}

export async function getNotificationSettings(): Promise<NotificationSettings> {
  return handle(await apiFetch("/api/notifications/settings", { cache: "no-store" }));
}

/** Partial update - only pass the fields that changed (mirrors the backend PATCH's
 * exclude_unset behaviour), so saving the Email card never clobbers the Teams fields. */
export async function updateNotificationSettings(
  patch: Partial<{
    email_enabled: boolean;
    smtp_host: string;
    smtp_port: number;
    smtp_username: string;
    smtp_password: string;
    smtp_from_address: string;
    email_recipients: string;
    teams_enabled: boolean;
    teams_webhook_url: string;
    daily_report_enabled: boolean;
    daily_report_hour_utc: number;
  }>,
): Promise<NotificationSettings> {
  return handle(await apiFetch("/api/notifications/settings", { method: "PATCH", body: JSON.stringify(patch) }));
}

export async function listNotificationLog(): Promise<NotificationLogEntry[]> {
  return handle(await apiFetch("/api/notifications/log", { cache: "no-store" }));
}

/** Send a one-off test message through every enabled channel right now. */
export async function testNotifications(): Promise<NotificationLogEntry[]> {
  return handle(await apiFetch("/api/notifications/test", { method: "POST" }));
}

/** Trigger the daily report immediately, bypassing its scheduled hour. */
export async function sendDailyReportNow(): Promise<NotificationLogEntry[]> {
  return handle(await apiFetch("/api/notifications/send-daily-report", { method: "POST" }));
}

export async function getReportSummary(): Promise<ReportSummary> {
  return handle(await apiFetch("/api/reports/summary", { cache: "no-store" }));
}

/** Download a report export as a Blob and trigger a browser save-as, via a throwaway <a> click.
 * Can't just link straight to the API URL: the export needs the session cookie, which a plain
 * cross-origin <a href> navigation would send, but any error response (e.g. a 401 if the
 * session expired) would otherwise render as a broken download instead of a visible error. */
async function downloadReport(path: string, filename: string): Promise<void> {
  const res = await apiFetch(path, { cache: "no-store" });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail || detail;
    } catch {
      // no JSON body
    }
    throw new ApiError(detail, res.status);
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export function downloadReportExcel(): Promise<void> {
  return downloadReport("/api/reports/export.xlsx", "vessel-report.xlsx");
}

export function downloadReportPdf(): Promise<void> {
  return downloadReport("/api/reports/export.pdf", "vessel-report.pdf");
}

export { ApiError };
