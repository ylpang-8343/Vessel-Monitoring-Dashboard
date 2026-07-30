const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type EventType =
  | "sailing"
  | "at_port"
  | "eta_destination"
  | "arrived_destination"
  | "sailed_from_destination";

export interface Vessel {
  id: number;
  name: string;
  imo_number: string;
  destination_port: string | null;
  created_at: string;
  current_location: string | null;
  last_event_type: EventType | null;
  last_event_text: string | null;
  last_event_at: string | null;
  source_name: string | null;
}

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

class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

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
  return res.json() as Promise<T>;
}

export async function listVessels(query?: string): Promise<Vessel[]> {
  const url = new URL(`${API_BASE}/api/vessels`);
  if (query) url.searchParams.set("q", query);
  return handle(await fetch(url.toString(), { cache: "no-store" }));
}

export async function createVessel(input: {
  name: string;
  imo_number: string;
  destination_port?: string | null;
}): Promise<Vessel> {
  return handle(
    await fetch(`${API_BASE}/api/vessels`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input),
    }),
  );
}

export async function getVesselHistory(imo: string): Promise<VesselHistory> {
  return handle(await fetch(`${API_BASE}/api/vessels/${imo}/history`, { cache: "no-store" }));
}

export async function previewBulkUpload(file: File): Promise<{ rows: BulkUploadRow[] }> {
  const formData = new FormData();
  formData.append("file", file);
  return handle(
    await fetch(`${API_BASE}/api/vessels/bulk/preview`, {
      method: "POST",
      body: formData,
    }),
  );
}

export async function importBulkRows(
  rows: { name: string; imo_number: string; destination_port?: string | null }[],
): Promise<BulkImportResult> {
  return handle(
    await fetch(`${API_BASE}/api/vessels/bulk/import`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rows }),
    }),
  );
}

export { ApiError };
