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

type Tab = "single" | "bulk";

export default function AddVesselModal({
  onClose,
  onImported,
}: {
  onClose: () => void;
  onImported: () => void;
}) {
  const [tab, setTab] = useState<Tab>("single");

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-2xl rounded-lg bg-white shadow-xl dark:bg-zinc-900">
        <div className="flex items-center justify-between rounded-t-lg bg-[#0b3d5c] px-6 py-4">
          <h2 className="text-lg font-semibold text-white">Add Vessel</h2>
          <button onClick={onClose} className="text-white/80 hover:text-white" aria-label="Close">
            ✕
          </button>
        </div>

        <div className="flex gap-2 border-b border-zinc-200 px-6 pt-4 dark:border-zinc-800">
          <TabButton active={tab === "single"} onClick={() => setTab("single")}>
            Single Vessel
          </TabButton>
          <TabButton active={tab === "bulk"} onClick={() => setTab("bulk")}>
            Bulk Upload (Excel/CSV/PDF)
          </TabButton>
        </div>

        <div className="px-6 py-5">
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

function TabButton({
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

function SingleVesselForm({ onClose, onImported }: { onClose: () => void; onImported: () => void }) {
  const [name, setName] = useState("");
  const [imo, setImo] = useState("");
  const [destination, setDestination] = useState("");
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
        <label className="block text-xs font-semibold uppercase tracking-wide text-zinc-500">Vessel Name</label>
        <input
          required
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="e.g. MV ABC"
          className="mt-1 w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
        />
      </div>

      <div>
        <label className="block text-xs font-semibold uppercase tracking-wide text-zinc-500">IMO Number</label>
        <input
          required
          value={imo}
          onChange={(e) => setImo(e.target.value.replace(/[^0-9]/g, "").slice(0, 7))}
          placeholder="7-digit number"
          className="mt-1 w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
        />
      </div>

      <div>
        <label className="block text-xs font-semibold uppercase tracking-wide text-zinc-500">
          Destination Port (optional)
        </label>
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
            className="mt-1 w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
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
            className="mt-1 w-full rounded-md border border-zinc-300 px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-800"
          />
        )}
        <p className="mt-1 text-xs text-zinc-500">
          Duplicate IMO numbers are automatically rejected. If no destination is set, the vessel stays on the
          dashboard indefinitely and is never auto-archived.
        </p>
      </div>

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
          {submitting ? "Adding…" : "Add Vessel"}
        </button>
      </div>
    </form>
  );
}

function BulkUploadForm({ onClose, onImported }: { onClose: () => void; onImported: () => void }) {
  const [rows, setRows] = useState<BulkUploadRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [fileName, setFileName] = useState<string | null>(null);

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
      <label className="flex cursor-pointer flex-col items-center gap-2 rounded-lg border-2 border-dashed border-zinc-300 px-4 py-8 text-center hover:border-zinc-400 dark:border-zinc-700">
        <span className="font-medium">Drag &amp; drop your .xlsx, .csv, or .pdf file here</span>
        <span className="text-xs text-zinc-500">PDF lists are read with AI extraction, then shown below to check before import</span>
        <span className="mt-2 rounded-md bg-[#0b3d5c] px-4 py-2 text-sm font-medium text-white">Choose File</span>
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

      {fileName && <p className="text-xs text-zinc-500">Selected: {fileName}</p>}
      {loading && <p className="text-sm text-zinc-500">Reading file…</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}

      {rows.length > 0 && (
        <div className="space-y-3">
          <div className="max-h-64 overflow-auto rounded-md border border-zinc-200 dark:border-zinc-800">
            <table className="w-full text-sm">
              <thead className="bg-zinc-50 text-left text-xs uppercase text-zinc-500 dark:bg-zinc-800">
                <tr>
                  <th className="px-3 py-2">Vessel Name</th>
                  <th className="px-3 py-2">IMO Number</th>
                  <th className="px-3 py-2">Destination (optional)</th>
                  <th className="px-3 py-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row, i) => (
                  <tr key={i} className="border-t border-zinc-100 dark:border-zinc-800">
                    <td className="px-3 py-1.5">
                      <input
                        value={row.name ?? ""}
                        onChange={(e) => updateRow(i, { name: e.target.value })}
                        className="w-full rounded border border-zinc-200 px-2 py-1 dark:border-zinc-700 dark:bg-zinc-900"
                      />
                    </td>
                    <td className="px-3 py-1.5">
                      <input
                        value={row.imo_number ?? ""}
                        onChange={(e) => updateRow(i, { imo_number: e.target.value })}
                        className="w-full rounded border border-zinc-200 px-2 py-1 dark:border-zinc-700 dark:bg-zinc-900"
                      />
                    </td>
                    <td className="px-3 py-1.5">
                      <input
                        value={row.destination_port ?? ""}
                        onChange={(e) => updateRow(i, { destination_port: e.target.value })}
                        placeholder="— (not set)"
                        className="w-full rounded border border-zinc-200 px-2 py-1 dark:border-zinc-700 dark:bg-zinc-900"
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
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border border-zinc-300 px-4 py-2 text-sm font-medium dark:border-zinc-700"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleImport}
              disabled={importing || importableCount === 0}
              className="rounded-md bg-[#1f8a4c] px-4 py-2 text-sm font-medium text-white hover:bg-[#1a7642] disabled:opacity-50"
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
    <span className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${styles[status]}`} title={message ?? ""}>
      {label}
    </span>
  );
}
