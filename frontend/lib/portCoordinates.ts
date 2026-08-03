// Real-world lat/lng for every location string the mock tracking adapter (or a manually
// entered destination) can produce, so the Map View (Section 6.B) can place a marker for it.
// Keyed by exact string match against `current_location` / `destination_port` - locations
// that aren't in this table (e.g. a free-text destination the mock adapter never emits) are
// simply not plottable and are listed separately on the map page instead of guessed at.
export const LOCATION_COORDS: Record<string, [number, number]> = {
  // Destination ports (frontend/lib/constants.ts's COMMON_DESTINATION_PORTS)
  "Pasir Gudang": [1.4649, 103.9025],
  "Port Klang West": [3.0002, 101.3903],
  "Port Klang South": [2.9958, 101.3944],
  Butterworth: [5.3991, 100.3638],

  // Origin ports the mock adapter departs vessels from
  Qingdao: [36.0671, 120.3826],
  Shanghai: [31.2304, 121.4737],
  Xiamen: [24.4798, 118.0894],
  Ningbo: [29.8683, 121.544],

  // Waypoint ports the mock adapter can report a vessel arriving at
  "Singapore Anchorage": [1.25, 103.83],

  // Sea regions the mock adapter reports a vessel's current location as while sailing -
  // approximate open-water centroids, since these aren't single fixed points in reality
  "South China Sea": [12.0, 114.0],
  "Strait of Malacca": [3.5, 100.3],
  "Singapore Strait": [1.15, 104.0],
  "Andaman Sea": [10.0, 96.5],
};

// Destination ports get their own fixed marker set on the map (Figure 4's green "Destination
// port" legend entry), independent of which vessels currently happen to be en route to them.
export const DESTINATION_PORTS: string[] = ["Pasir Gudang", "Port Klang West", "Port Klang South", "Butterworth"];
