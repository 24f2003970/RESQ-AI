import { ArrowRight, Box, Building2, CircleDot, X } from "lucide-react";
import type { Building, CityState } from "../api/client";
import type { ScenarioPredictionSet } from "../api/client";
import { Badge, Panel } from "./ui";

export default function Inspector({
  selected,
  city,
  loading,
  error,
  close,
  choose,
  predictions,
}: {
  selected: Building | null;
  city: CityState;
  loading: boolean;
  error: string;
  close: () => void;
  choose: (id: string) => void;
  predictions: ScenarioPredictionSet | null;
}) {
  return (
    <Panel
      title="Object inspector"
      eyebrow="CITY INTELLIGENCE"
      action={
        selected ? (
          <button
            className="icon-button"
            aria-label="Close inspector"
            onClick={close}
          >
            <X size={15} />
          </button>
        ) : (
          <Box size={17} />
        )
      }
    >
      {loading ? (
        <div className="inspector-empty" role="status">
          Loading building details…
        </div>
      ) : error ? (
        <div className="inline-error" role="alert">
          {error}
        </div>
      ) : selected ? (
        <div className="inspector-body">
          <div className={`building-glyph ${selected.use}`}>
            <Building2 size={32} />
            <span>{selected.floors}F</span>
          </div>
          <h3>{selected.name}</h3>
          <p className="entity-id">{selected.id}</p>
          <Badge>{selected.use}</Badge>
          <dl>
            <div>
              <dt>District</dt>
              <dd>
                {
                  city.districts.find((d) => d.id === selected.district_id)
                    ?.name
                }
              </dd>
            </div>
            <div>
              <dt>Height / floors</dt>
              <dd>
                {selected.height_m.toFixed(1)} m / {selected.floors}
              </dd>
            </div>
            <div>
              <dt>Seeded occupants</dt>
              <dd>{selected.occupants}</dd>
            </div>
            <div>
              <dt>Footprint</dt>
              <dd>
                {selected.width_m.toFixed(0)} × {selected.depth_m.toFixed(0)} m
              </dd>
            </div>
            <div>
              <dt>Position E / N</dt>
              <dd>
                {selected.position.x_m} / {selected.position.y_m} m
              </dd>
            </div>
            <div>
              <dt>Condition</dt>
              <dd>Baseline</dd>
            </div>
          </dl>
          <p className="inspector-note">
            <CircleDot size={12} /> Verified against building API
          </p>
          {(() => { const prediction = predictions?.predictions.find((p) => p.building_id === selected.id); return prediction ? <div className="inspector-ml"><small>ML estimate · +{predictions?.horizon_minutes} min</small><strong>{prediction.predicted_future_exposed ? "Predicted exposed" : "Predicted not exposed"}</strong><span>Current: {prediction.current_exposed ? `${prediction.current_exposure_category} · ${prediction.current_max_depth_m.toFixed(2)} m` : "not exposed"}</span><span>Uncalibrated score: {prediction.uncalibrated_model_score.toFixed(3)}</span></div> : null; })()}
        </div>
      ) : (
        <div className="inspector-empty">
          <div className="selection-box">
            <Box size={28} />
          </div>
          <h3>A city of connected details.</h3>
          <p>Select a building in the twin to inspect its real seed data.</p>
          <button
            className="text-button"
            onClick={() => choose(city.hospitals[0].building_id)}
          >
            Inspect Riverside General <ArrowRight size={13} />
          </button>
        </div>
      )}
    </Panel>
  );
}
