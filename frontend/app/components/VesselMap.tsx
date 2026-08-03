"use client";

import "leaflet/dist/leaflet.css";
import L from "leaflet";
import { useMemo } from "react";
import { MapContainer, Marker, Popup, TileLayer } from "react-leaflet";
import type { Vessel } from "@/lib/api";
import { statusMeta } from "./StatusDot";
import { DESTINATION_PORTS, LOCATION_COORDS } from "@/lib/portCoordinates";

// Default centre/zoom when there's nothing to fit bounds to yet (roughly the South China Sea,
// centred between the mock adapter's China-coast origins and the Malaysia destination ports).
const DEFAULT_CENTER: [number, number] = [10, 110];
const DEFAULT_ZOOM = 4;

function dotIcon(colourClass: string) {
  // Tailwind's `bg-*` classes resolve fine inside a divIcon since it's rendered into the same
  // document, avoiding the separate marker-image asset pipeline `L.Icon.Default` needs (which
  // Next.js's bundler doesn't wire up automatically).
  return L.divIcon({
    className: "",
    html: `<span class="block h-3.5 w-3.5 rounded-full border-2 border-white shadow ${colourClass}"></span>`,
    iconSize: [14, 14],
    iconAnchor: [7, 7],
  });
}

const DESTINATION_ICON = L.divIcon({
  className: "",
  html: `<span class="flex h-5 w-5 items-center justify-center rounded-full border-2 border-white bg-[#0b3d5c] text-[10px] text-white shadow">⚓</span>`,
  iconSize: [20, 20],
  iconAnchor: [10, 10],
});

export default function VesselMap({ vessels }: { vessels: Vessel[] }) {
  const plottable = useMemo(
    () => vessels.filter((v) => v.current_location && LOCATION_COORDS[v.current_location]),
    [vessels],
  );
  const unplottable = useMemo(
    () => vessels.filter((v) => !v.current_location || !LOCATION_COORDS[v.current_location]),
    [vessels],
  );

  const bounds = useMemo(() => {
    const points: [number, number][] = plottable.map((v) => LOCATION_COORDS[v.current_location!]);
    DESTINATION_PORTS.forEach((port) => points.push(LOCATION_COORDS[port]));
    return points.length > 0 ? L.latLngBounds(points) : null;
  }, [plottable]);

  return (
    <div>
      <div className="h-[520px] w-full overflow-hidden rounded-lg border border-zinc-200 dark:border-zinc-800">
        <MapContainer
          center={DEFAULT_CENTER}
          zoom={DEFAULT_ZOOM}
          bounds={bounds ?? undefined}
          boundsOptions={{ padding: [40, 40] }}
          style={{ height: "100%", width: "100%" }}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          {DESTINATION_PORTS.map((port) => (
            <Marker key={port} position={LOCATION_COORDS[port]} icon={DESTINATION_ICON}>
              <Popup>
                <strong>{port}</strong>
                <br />
                Destination port
              </Popup>
            </Marker>
          ))}

          {plottable.map((v) => {
            const meta = statusMeta(v.last_event_type);
            return (
              <Marker key={v.imo_number} position={LOCATION_COORDS[v.current_location!]} icon={dotIcon(meta.dot)}>
                <Popup>
                  <strong>{v.name}</strong> (IMO {v.imo_number})
                  <br />
                  {v.last_event_text ?? "No tracking data yet"}
                  <br />
                  {v.destination_port ? `Destination: ${v.destination_port}` : "No destination set"}
                </Popup>
              </Marker>
            );
          })}
        </MapContainer>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-4 text-xs text-zinc-600 dark:text-zinc-400">
        <LegendItem colourClass="bg-[#0b3d5c]" label="Destination port" />
        <LegendItem colourClass="bg-blue-500" label="Sailing" />
        <LegendItem colourClass="bg-orange-500" label="At Port" />
        <LegendItem colourClass="bg-amber-500" label="ETA to Destination" />
        <LegendItem colourClass="bg-green-500" label="Arrived at Destination" />
        <LegendItem colourClass="bg-zinc-400" label="Sailed from Destination" />
      </div>

      {unplottable.length > 0 && (
        <div className="mt-4 rounded-md border border-zinc-200 bg-zinc-50 px-4 py-3 text-xs text-zinc-600 dark:border-zinc-800 dark:bg-zinc-900 dark:text-zinc-400">
          <p className="mb-1 font-medium text-zinc-700 dark:text-zinc-300">
            Not shown on map ({unplottable.length}) — location not yet mapped to coordinates:
          </p>
          <ul className="space-y-0.5">
            {unplottable.map((v) => (
              <li key={v.imo_number}>
                {v.name} — {v.current_location ?? "no tracking data yet"}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function LegendItem({ colourClass, label }: { colourClass: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={`inline-block h-2.5 w-2.5 rounded-full ${colourClass}`} />
      {label}
    </span>
  );
}
