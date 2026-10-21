import { useState } from "react";
import type { Building, CityState, ScenarioState } from "../api/client";

export default function CityInventory({ city, scenario, selected, onSelect }: {
  city: CityState; scenario: ScenarioState | null; selected: Building | null; onSelect: (id: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [exposedOnly, setExposedOnly] = useState(false);
  const impacts = new Map(scenario?.impacts.buildings.map((impact) => [impact.entity_id, impact]) ?? []);
  const buildings = city.buildings.filter((building) => {
    const district = city.districts.find((item) => item.id === building.district_id)?.name ?? "";
    return `${building.name} ${building.id} ${building.use} ${district}`.toLowerCase().includes(query.trim().toLowerCase()) && (!exposedOnly || impacts.get(building.id)?.water_reaches_building === true);
  });
  return <div className="map-fallback searchable-inventory">
    <h3>City inventory view</h3>
    <p>Find a building by name, use or district. Depths describe the current physical simulation.</p>
    <label className="inventory-search">Search buildings<input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Try hospital, shelter or a district"/></label>
    <label className="inventory-filter"><input type="checkbox" checked={exposedOnly} disabled={!scenario} onChange={(event) => setExposedOnly(event.target.checked)}/> Only buildings reached by water</label>
    <p role="status">{buildings.length} of {city.buildings.length} buildings{!scenario ? " · physical state unavailable" : ""}</p>
    <div className="building-list" aria-label="Building inventory">
      {buildings.map((building) => {
        const impact = impacts.get(building.id);
        return <button key={building.id} onClick={() => onSelect(building.id)} aria-pressed={selected?.id === building.id}>
          <strong>{building.name}</strong><span>{building.floors} floors · {building.use}</span>
          <span>{impact ? `${impact.water_reaches_building ? "Water reaches building" : "Water has not reached building"} · ${impact.max_depth_m.toFixed(2)} m maximum depth` : "Current depth unavailable"}</span>
        </button>;
      })}
    </div>
    {!buildings.length && <p>No buildings match. Try another search or turn off the water filter.</p>}
  </div>;
}
