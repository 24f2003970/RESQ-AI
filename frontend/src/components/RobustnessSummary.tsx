import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, ShieldAlert } from "lucide-react";
import type { RobustnessStudy, ScenarioState } from "../api/client";
import { fetchRobustnessStudies } from "../api/client";
import { Badge, Panel } from "./ui";

export default function RobustnessSummary({scenario}:{scenario:ScenarioState|null}){
  const scenarioId=scenario?.id;
  const scenarioEpoch=scenario?.epoch;
  const stateVersion=scenario?.state_version;
  const [study,setStudy]=useState<RobustnessStudy|null>(null);
  const [loaded,setLoaded]=useState(false);
  useEffect(()=>{
    if(!scenarioId){setStudy(null);setLoaded(true);return;}
    setLoaded(false);setStudy(null);
    const controller=new AbortController();
    fetchRobustnessStudies(scenarioId,controller.signal).then(studies=>{setStudy(studies[0]??null);setLoaded(true);}).catch(()=>{if(!controller.signal.aborted)setLoaded(true);});
    return ()=>controller.abort();
  },[scenarioId,scenarioEpoch,stateVersion]);
  const results=study?.results;
  const conditionRows=results&&Array.isArray(results.conditions)?results.conditions as {original_plan_feasibility?:{invalidated_routes?:number}}[]:[];
  const invalidated=conditionRows.reduce((total,row)=>total+(row.original_plan_feasibility?.invalidated_routes??0),0);
  const conditionCount=study?.conditions.length??0;
  return <Panel title="Decision robustness" eyebrow="SAVED HYPOTHETICAL EVIDENCE" action={<Link className="text-action" to="/robustness">Open lab <ArrowRight size={13}/></Link>}>
    {!loaded?<p className="muted">Checking saved studies…</p>:study?<div className="robustness-summary-body"><div><Badge tone={study.stale?"amber":study.status==="completed"?"green":"neutral"}>{study.stale?"HISTORICAL":study.status.toUpperCase()}</Badge><span className="mono"> tick {study.simulation_tick} · v{study.simulation_state_version}</span></div>{study.stale?<p>This study is historical because its source state or infrastructure changed.</p>:study.status==="completed"?<p>{conditionCount} tested conditions · {invalidated} original-plan route checks invalidated across the saved cases.</p>:<p>Study {study.status.toLowerCase()}; incomplete results are not presented as evidence.</p>}<Link to="/robustness" className="robustness-summary-link">{study.study_id.slice(0,10)} · inspect saved study</Link></div>:<div className="robustness-summary-body"><div><ShieldAlert size={15}/><span>No saved study for this scenario snapshot.</span></div><p>Counterfactual conditions can be analyzed in the isolated lab.</p></div>}
  </Panel>;
}
