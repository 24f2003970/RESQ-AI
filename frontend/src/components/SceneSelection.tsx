import type { Building, Mission, ScenarioPredictionSet, ScenarioState } from "../api/client";

export default function SceneSelection({ building, scenario, predictions, mission }: {
  building: Building | null; scenario: ScenarioState | null; predictions: ScenarioPredictionSet | null; mission: Mission | null;
}) {
  const impact = building ? scenario?.impacts.buildings.find((item) => item.entity_id === building.id) : null;
  const prediction = building ? predictions?.predictions.find((item) => item.building_id === building.id) : null;
  if (!building && !mission) return <p className="scene-selection-hint">Select a building in the city, or use <strong>Find a building</strong>. Select a mission in Dispatch &amp; track to follow its unit.</p>;
  return <div className="scene-selection-summary" aria-label="Selected city details" aria-live="polite">
    {building && <div><span className="eyebrow">SELECTED BUILDING</span><strong>{building.name}</strong>
      <p>{building.use} · {building.floors} floors · {building.occupants} seeded occupants</p>
      <p><b>Current physical water:</b> {impact ? `${impact.max_depth_m.toFixed(2)} m maximum depth · ${impact.water_reaches_building ? "water reaches building" : "water has not reached building"}` : "Unavailable"}</p>
      <p><b>Future ML estimate:</b> {prediction ? `${prediction.predicted_future_exposed ? "Exposure estimated" : "No exposure estimated"} at +${predictions?.horizon_minutes} simulated minutes · ${prediction.distribution_support_status.replaceAll("_", " ")}` : "No current supported estimate available"}</p>
      <a href="#building-details">More building details ↓</a>
    </div>}
    {mission && <div><span className="eyebrow">SELECTED MISSION</span><strong>{mission.unit_id} · {mission.status.replaceAll("_", " ")}</strong><p>Route progress: {mission.traversed_distance_m.toFixed(1)} m. Position and movement come from the mission clock.</p><p>{mission.status === "en_route" ? "Camera follows this unit until you choose another view." : "This unit is not moving. Arrival and completion require separate review."}</p></div>}
  </div>;
}
