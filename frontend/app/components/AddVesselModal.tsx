"use client";

import { useState } from "react";
import {
  ApiError,
  BulkUploadRow,
  createVessel,
  importBulkRows,
  previewBulkUpload,
} from "@/lib/api";
import { COMMON_DESTINATION_PORTS } from "@/lib/constants";
import { TabButton, btnPrimary, btnSecondary, inputClass, labelClass, theadClass } from "./ui";

type Tab = "single" | "bulk";

// The "+ Add" modal (Section 3.2's "two-option form": add a single vessel manually, or
// bulk-import many at once). `onImported` is called after either path successfully adds at
// least one vessel, so the dashboard can refresh its list.
export default function AddVesselModal({
  onClose,
  onImported,
}: {
  onClose: () => void;
  onImported: () => void;
}) {
  const [tab, setTab] = useState<Tab>("single");

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4">
      <div className="w-full max-w-2xl border border-rule bg-white shadow-2xl">
        <div className="flex items-center justify-between bg-brand px-5 py-3.5">
          <h2 className="text-base font-bold uppercase tracking-wide text-white">Add Vessel</h2>
          <button onClick={onClose} className="text-white/80 hover:text-white" aria-label="Close">
            ✕
          </button>
        </div>

        <div className="flex border-b border-rule px-5 pt-1">
          <TabButton active={tab === "single"} onClick={() => setTab("single")}>
            Single Vessel
          </TabButton>
          <TabButton active={tab === "bulk"} onClick={() => setTab("bulk")}>
            Bulk Upload (Excel/CSV/PDF)
          </TabButton>
        </div>

        <div className="px-5 py-5">
          {tab === "single" ? (
            <SingleVesselForm onClose={onClose} onImported={onImported} />
          ) : (
            <BulkUploadForm onClose={onClose} onImported={onImported} />
          )}
        </div>
      </div>
    </div>
  );
}

// "Single Vessel" tab of the Add Vessel modal (Section 3.1).
function SingleVesselForm({ onClose, onImported }: { onClose: () => void; onImported: () => void }) {
  const [name, setName] = useState("");
  const [imo, setImo] = useState("");
  const [destination, setDestination] = useState("");
  // Whether the destination field is a free-text input instead of the preset <select> - flipped
  // on once the user picks "Other (type manually)…" below.
  const [customDestination, setCustomDestination] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await createVessel({
        name,
        imo_number: imo,
        destination_port: destination.trim() || null,
      });
      onImported();
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to add vessel");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className={labelClass}>Vessel Name</label>
        <input
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g. MV ABC"
          className={`${inputClass} mt-1 w-full`}
        />
      </div>

      <div>
        <label className={labelClass}>IMO Number</label>
        <input
          required
          value={imo}
          // Strip non-digits and cap at 7 characters as the user types, so the field can never
          // even contain an invalid IMO - the backend still re-validates on submit regardless.
          onChange={(e) => setImo(e.target.value.replace(/[^0-9]/g, "").slice(0, 7))}
          placeholder="7-digit number"
          className={`${inputClass} mt-1 w-full`}
        />
      </div>

      <div>
        <label className={labelClass}>Destination Port (optional)</label>
        {!customDestination ? (
          <select
            value={destination}
            onChange={(e) => {
              if (e.target.value === "__custom__") {
                setCustomDestination(true);
                setDestination("");
              } else {
                setDestination(e.target.value);
              }
            }}
            className={`${inputClass} mt-1 w-full`}
          >
            <option value="">— Not set —</option>
            {COMMON_DESTINATION_PORTS.map((port) => (
              <option key={port} value={port}>
                {port}
              </option>
            ))}
            <option value="__custom__">Other (type manually)…</option>
          </select>
        ) : (
          <input
            value={destination}
            onChange={(e) => setDestination(e.target.value)}
            placeholder="Enter destination port"
            className={`${inputClass} mt-1 w-full`}
          />
        )}
        <p className="mt-1.5 text-xs text-muted">
          Duplicate IMO numbers are automatically rejected. If no destination is set, the vessel stays on the
          dashboard indefinitely and is never auto-archived.
        </p>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="flex justify-end gap-3 pt-2">
        <button type="button" onClick={onClose} className={btnSecondary}>
          Cancel
        </button>
        <button type="submit" disabled={submitting} className={btnPrimary}>
          {submitting ? "Adding…" : "Add Vessel"}
        </button>
      </div>
    </form>
  );
}

// "Bulk Upload" tab of the Add Vessel modal (Section 3.2) - two-step flow: pick a file to get
// an editable preview (`rows`), fix up anything flagged, then import only the "ok" rows.
function BulkUploadForm({ onClose, onImported }: { onClose: () => void; onImported: () => void }) {
  const [rows, setRows] = useState<BulkUploadRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [fileName, setFileName] = useState<string | null>(null);

  /** Send the picked file to the backend for parsing/AI-extraction and populate the preview
   * table. Nothing is imported at this point - see handleImport. */
  async function handleFile(file: File) {
    setError(null);
    setLoading(true);
    setFileName(file.name);
    try {
      const preview = await previewBulkUpload(file);
      setRows(preview.rows);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to read file");
      setRows([]);
    } finally {
      setLoading(false);
    }
  }

  /** Apply an inline edit to one preview row (e.g. the user typed in a corrected IMO number)
   * and re-run client-side validation on just that row, so its status/message update live
   * without waiting for another round-trip to the server. */
  function updateRow(index: number, patch: Partial<BulkUploadRow>) {
    setRows((prev) =>
      prev.map((r, i) => {
        if (i !== index) return r;
        const next = { ...r, ...patch };
        // The user just edited this row (e.g. fixed a duplicate/invalid IMO) — re-check the
        // fields we can validate client-side. True duplicate checks still happen server-side
        // on import, which is the final authority.
        const imoValid = !!next.imo_number && /^\d{7}$/.test(next.imo_number);
        if (next.name && imoValid) {
          next.status = "ok";
          next.message = null;
        } else {
          next.status = "invalid";
          next.message = "Missing vessel name or a valid 7-digit IMO number";
        }
        return next;
      }),
    );
  }

  /** Import only the rows currently flagged "ok" - duplicate/invalid rows are left out
   * entirely rather than sent to the backend, which is the final gate against bad data. */
  async function handleImport() {
    const importable = rows.filter((r) => r.status === "ok" && r.name && r.imo_number);
    if (importable.length === 0) return;
    setImporting(true);
    setError(null);
    try {
      await importBulkRows(
        importable.map((r) => ({
          name: r.name!,
          imo_number: r.imo_number!,
          destination_port: r.destination_port || null,
        })),
      );
      onImported();
      onClose();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Import failed");
    } finally {
      setImporting(false);
    }
  }

  const importableCount = rows.filter((r) => r.status === "ok" && r.name && r.imo_number).length;

  return (
    <div className="space-y-4">
      <label className="flex cursor-pointer flex-col items-center gap-2 border-2 border-dashed border-rule-strong px-4 py-8 text-center transition-colors hover:border-brand hover:bg-brand-tint">
        <span className="font-bold text-ink">Drag &amp; drop your .xlsx, .csv, or .pdf file here</span>
        <span className="text-xs text-muted">
          PDF lists are read with AI extraction, then shown below to check before import
        </span>
        <span className="mt-2 rounded-sm bg-brand px-4 py-2 text-sm font-bold text-white">Choose File</span>
        <input
          type="file"
          accept=".xlsx,.xls,.csv,.pdf"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) handleFile(file);
          }}
        />
      </label>

      {fileName && <p className="text-xs text-muted">Selected: {fileName}</p>}
      {loading && <p className="text-sm text-muted">Reading file…</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}

      {rows.length > 0 && (
        <div className="space-y-3">
          <div className="max-h-64 overflow-auto border border-rule">
            <table className="w-full text-sm">
              <thead className={theadClass}>
                <tr>
                  <th className="px-3 py-2">Vessel Name</th>
                  <th className="px-3 py-2">IMO Number</th>
                  <th className="px-3 py-2">Destination (optional)</th>
                  <th className="px-3 py-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row, i) => (
                  <tr key={i} className="border-b border-rule last:border-b-0">
                    <td className="px-3 py-1.5">
                      <input
                        value={row.name ?? ""}
                        onChange={(e) => updateRow(i, { name: e.target.value })}
                        className="w-full rounded-sm border border-rule px-2 py-1 focus:border-brand focus:outline-none"
                      />
                    </td>
                    <td className="px-3 py-1.5">
                      <input
                        value={row.imo_number ?? ""}
                        onChange={(e) => updateRow(i, { imo_number: e.target.value })}
                        className="w-full rounded-sm border border-rule px-2 py-1 focus:border-brand focus:outline-none"
                      />
                    </td>
                    <td className="px-3 py-1.5">
                      <input
                        value={row.destination_port ?? ""}
                        onChange={(e) => updateRow(i, { destination_port: e.target.value })}
                        placeholder="— (not set)"
                        className="w-full rounded-sm border border-rule px-2 py-1 focus:border-brand focus:outline-none"
                      />
                    </td>
                    <td className="px-3 py-1.5">
                      <StatusBadge status={row.status} message={row.message} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex justify-end gap-3">
            <button type="button" onClick={onClose} className={btnSecondary}>
              Cancel
            </button>
            <button
              type="button"
              onClick={handleImport}
              disabled={importing || importableCount === 0}
              className={btnPrimary}
            >
              {importing
                ? "Importing…"
                : `Import ${importableCount} Vessel${importableCount === 1 ? "" : "s"}`}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function StatusBadge({ status, message }: { status: BulkUploadRow["status"]; message: string | null }) {
  const styles: Record<BulkUploadRow["status"], string> = {
    ok: "bg-green-50 text-green-700",
    duplicate: "bg-amber-50 text-amber-700",
    invalid: "bg-red-50 text-red-700",
  };
  const label = status === "ok" ? "Ready" : status === "duplicate" ? "Duplicate" : "Needs fix";
  return (
    <span className={`inline-block rounded-sm px-2 py-0.5 text-xs font-bold ${styles[status]}`} title={message ?? ""}>
      {label}
    </span>
  );
}
