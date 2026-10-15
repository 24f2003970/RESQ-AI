"""Emergence-only analysis on the unchanged scenario-grouped held-out test split."""
import json
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
from sklearn.metrics import precision_recall_fscore_support

from ..city_service import generate_city
from ..flood import SimulationParameters, impact_assessment, initial_depth, step
from .dataset import OBSERVATION_TICKS
from .features import HORIZON_TICKS, build_feature_rows, feature_matrix, heuristic_prediction, target_exposed
from ..ml_service import _load_model_bundle


def emergence_report(output: str | Path | None = None):
    """Evaluate only currently unexposed held-out examples without changing training or test split."""
    artifact_dir=Path(__file__).resolve().parents[2]/"ml_artifacts"
    metadata=json.loads((artifact_dir/"model_metadata.json").read_text(encoding="utf-8"))
    data_meta=json.loads((artifact_dir/"dataset_metadata.json").read_text(encoding="utf-8"))
    test_ids=set(metadata["split_scenario_ids"]["test"])
    parameters={item["scenario_id"]:item["parameters"] for item in data_meta["simulation_seeds"]}
    estimator=_load_model_bundle()[0]["estimator"]
    labels=[]; predicted=[]; heuristic=[]
    for scenario_id in sorted(test_ids):
        seed=int(scenario_id.rsplit("-",1)[1]); params=SimulationParameters(**parameters[scenario_id]); city=generate_city(seed)
        depth=initial_depth(seed,params.river_level_m); tick=0
        for target_tick in OBSERVATION_TICKS:
            if target_tick>tick: depth,_=step(depth,seed,params,steps=target_tick-tick); tick=target_tick
            current=impact_assessment(city,depth,seed,params.river_level_m)
            current_exposed={item["entity_id"] for item in current["buildings"] if item["water_reaches_building"]}
            future_depth,_=step(depth,seed,params,steps=HORIZON_TICKS)
            future=target_exposed(city,future_depth,seed,params.river_level_m)
            rows=build_feature_rows(city,depth,seed,params,target_tick)
            subset=[idx for idx,b in enumerate(city.buildings) if b.id not in current_exposed]
            if not subset:
                continue
            labels.extend(future[city.buildings[i].id] for i in subset)
            predicted.extend(estimator.predict(feature_matrix([rows[i] for i in subset])).astype(int).tolist())
            heuristic.extend(heuristic_prediction(rows[i]) for i in subset)
    y=np.asarray(labels,dtype=int)
    def metrics(pred):
        precision,recall,f1,_=precision_recall_fscore_support(y,pred,average="binary",zero_division=0)
        return {"precision":round(float(precision),4),"recall":round(float(recall),4),"f1":round(float(f1),4)}
    report={"evaluation":"currently_unexposed_to_exposed_within_30_simulated_minutes","created_at_utc":datetime.now(timezone.utc).isoformat(),"test_scenarios":sorted(test_ids),"subset_size":len(y),"positive_count":int(y.sum()),"negative_count":int(len(y)-y.sum()),"model":metrics(np.asarray(predicted)),"heuristic":metrics(np.asarray(heuristic)),"unchanged_held_out_split":True,"limitations":"Synthetic simulator-only subset; excludes currently exposed buildings and does not establish real-world forecast performance."}
    destination=Path(output) if output else artifact_dir/"emergence_evaluation.json"
    destination.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    return report


if __name__=="__main__":
    print(json.dumps(emergence_report(),indent=2))
