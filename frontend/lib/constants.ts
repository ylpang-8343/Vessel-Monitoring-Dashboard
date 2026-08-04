// Initial destination list per proposal Section 3.1 / Section 10 — configurable,
// with free text accepted for any other port. Used to populate the destination <select> in
// AddVesselModal (falling back to a free-text input for "Other"), and duplicated in
// lib/portCoordinates.ts's DESTINATION_PORTS for the Map View's fixed port markers.
export const COMMON_DESTINATION_PORTS = ["Pasir Gudang", "Port Klang West", "Port Klang South", "Butterworth"];
