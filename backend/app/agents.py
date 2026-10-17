"""Durable local event processor and six deterministic algorithmic agents."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone

from .agent_contracts import (
    AgentDashboard, AgentDefinition, AgentEventEnvelope, AgentRunRecord, AgentTrace,
    AgentTraceDetail, ensure_agent_event_table, persist_agent_event,
)
from .city_service import generate_city
from .ml_service import ModelUnavailable, predictions
from .rescue import PlanStore, RescuePlan, build_road_graph, generate_plan, priorities, route
from .scenarios import ScenarioError, ScenarioStore


AGENTS = [
    AgentDefinition(name="hazard_intelligence", title="Hazard Intelligence", responsibility="Measured flood state and local 30-minute exposure estimates", position=1),
    AgentDefinition(name="impact_assessment", title="Impact Assessment", responsibility="Building exposure and physical road/bridge accessibility transitions", position=2),
    AgentDefinition(name="rescue_priority", title="Rescue Priority", responsibility="Existing explainable priority score and ranking changes", position=3),
    AgentDefinition(name="routing", title="Routing", responsibility="Flood- and closure-aware ground routes and unreachable destinations", position=4),
    AgentDefinition(name="resource_allocation", title="Resource Allocation", responsibility="Reserved-resource-aware optimal assignment and baseline comparison", position=5),
    AgentDefinition(name="commander_strategy", title="Commander / Strategy", responsibility="Material-change gate and human-review proposal coordination", position=6),
]
AGENT_NAMES = [agent.name for agent in AGENTS]
TRIGGER_EVENT_TYPES = {"scenario_created", "simulation_advanced", "parameters_changed", "scenario_reset", "infrastructure_changed", "rescue_plan_approved", "rescue_plan_rejected", "manual_assessment", "mission_dispatched", "mission_blocked", "mission_arrived", "mission_completed", "mission_cancelled", "mission_cancelled_unit_unavailable", "unit_returned_to_service", "mission_route_revision_approved"}
POLICY = {"minimum_depth_increase_m": 0.05, "minimum_priority_score_change": 3.0, "duplicate_proposal": "same epoch, infrastructure revision, ranked scores, route edges and assignment signature is suppressed", "cooldown": "No time cooldown; deterministic material-change comparison avoids delaying a real route closure or new exposure."}


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


class AgentOrchestrator:
    """SQLite outbox processor. A run is idempotent by (event_id, agent_name)."""

    def __init__(self, scenario_store: ScenarioStore, plan_store: PlanStore):
        self.scenarios = scenario_store
        self.plans = plan_store
        self.path = str(scenario_store.path)
        self._lock = threading.RLock()
        with sqlite3.connect(self.path) as db:
            ensure_agent_event_table(db)
            db.executescript("""
                CREATE TABLE IF NOT EXISTS agent_runs (
                    run_id TEXT PRIMARY KEY, event_id TEXT NOT NULL, correlation_id TEXT NOT NULL,
                    scenario_id TEXT NOT NULL, scenario_epoch INTEGER NOT NULL,
                    state_version INTEGER NOT NULL, infrastructure_revision INTEGER,
                    agent_name TEXT NOT NULL, status TEXT NOT NULL, started_at TEXT, completed_at TEXT,
                    duration_ms REAL, input_hash TEXT NOT NULL, input_snapshot_ref TEXT NOT NULL,
                    output_json TEXT NOT NULL DEFAULT '{}', evidence_json TEXT NOT NULL DEFAULT '{}',
                    proposed_action TEXT, explanation TEXT NOT NULL DEFAULT '', error TEXT, attempt INTEGER NOT NULL DEFAULT 0,
                    UNIQUE(event_id,agent_name)
                );
                CREATE INDEX IF NOT EXISTS agent_runs_recent ON agent_runs(scenario_id,scenario_epoch,started_at);
                CREATE TABLE IF NOT EXISTS decision_traces (
                    trace_id TEXT PRIMARY KEY, event_id TEXT NOT NULL UNIQUE, correlation_id TEXT NOT NULL,
                    scenario_id TEXT NOT NULL, scenario_epoch INTEGER NOT NULL, state_version INTEGER NOT NULL,
                    infrastructure_revision INTEGER, status TEXT NOT NULL, plan_id TEXT,
                    summary TEXT NOT NULL, evidence_json TEXT NOT NULL, created_at TEXT NOT NULL
                );
            """)

    def enqueue(self, *, event_type: str, scenario_id: str, state, infrastructure_revision=None,
                source_module="api", payload=None, affected_entity_ids=None, causation_event_id=None):
        with sqlite3.connect(self.path, timeout=10, isolation_level=None) as db:
            db.execute("BEGIN IMMEDIATE")
            event = persist_agent_event(db,event_type=event_type,scenario_id=scenario_id,
                scenario_epoch=state.epoch,simulation_tick=state.tick,state_version=state.state_version,
                infrastructure_revision=infrastructure_revision,source_module=source_module,
                payload=payload,affected_entity_ids=affected_entity_ids,causation_event_id=causation_event_id)
            db.commit()
            return event

    def recover(self):
        """Retry abandoned in-flight events after restart and drain durable pending events."""
        with sqlite3.connect(self.path, timeout=10, isolation_level=None) as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute("UPDATE agent_event_outbox SET status='pending',error=NULL WHERE status IN ('processing','failed') AND attempts<3")
            ids=[row[0] for row in db.execute("SELECT event_id FROM agent_event_outbox WHERE status='pending' ORDER BY created_at_utc,event_id")]
            db.commit()
        for event_id in ids:
            self.process_event(event_id)

    def schedule_pending(self,background_tasks,scenario_id,state_version,scenario_epoch=None):
        with sqlite3.connect(self.path,timeout=10,isolation_level=None) as db:
            db.execute("BEGIN IMMEDIATE")
            if scenario_epoch is not None:
                stale_rows=db.execute("SELECT event_id,envelope_json FROM agent_event_outbox WHERE scenario_id=? AND status='pending' AND (scenario_epoch<>? OR simulation_state_version<?)",
                                      (scenario_id,scenario_epoch,state_version)).fetchall()
                reason="A newer committed scenario snapshot superseded this unprocessed trigger before it was claimed."
                for stale_id,envelope_json in stale_rows:
                    event=AgentEventEnvelope.model_validate_json(envelope_json)
                    db.execute("UPDATE agent_event_outbox SET status='superseded',error=?,processed_at_utc=? WHERE event_id=? AND status='pending'",(reason,_utc(),stale_id))
                    db.execute("INSERT OR IGNORE INTO decision_traces(trace_id,event_id,correlation_id,scenario_id,scenario_epoch,state_version,infrastructure_revision,status,plan_id,summary,evidence_json,created_at) VALUES(?,?,?,?,?,?,?,'superseded',NULL,?,?,?)",
                        (stale_id,stale_id,event.correlation_id,scenario_id,event.scenario_epoch,event.simulation_state_version,event.infrastructure_revision,
                         reason,_canonical({"superseded_by_state_version":state_version}),_utc()))
            if scenario_epoch is None:
                rows=db.execute("SELECT event_id FROM agent_event_outbox WHERE scenario_id=? AND simulation_state_version=? AND status='pending' ORDER BY created_at_utc,event_id",(scenario_id,state_version)).fetchall()
            else:
                rows=db.execute("SELECT event_id FROM agent_event_outbox WHERE scenario_id=? AND scenario_epoch=? AND simulation_state_version=? AND status='pending' ORDER BY created_at_utc,event_id",(scenario_id,scenario_epoch,state_version)).fetchall()
            db.commit()
        for (event_id,) in rows:
            background_tasks.add_task(self.process_event,event_id)
        return len(rows)

    def retry(self,event_id):
        with sqlite3.connect(self.path,timeout=10,isolation_level=None) as db:
            db.execute("BEGIN IMMEDIATE")
            row=db.execute("SELECT status,attempts FROM agent_event_outbox WHERE event_id=?",(event_id,)).fetchone()
            if not row:
                db.rollback();return False
            if row[0] not in ("failed","pending") or row[1]>=3:
                db.rollback();return False
            db.execute("UPDATE agent_event_outbox SET status='pending',error=NULL WHERE event_id=?",(event_id,))
            db.commit()
        self.process_event(event_id)
        return True

    def process_event(self, event_id: str):
        with self._lock:
            with sqlite3.connect(self.path, timeout=10, isolation_level=None) as db:
                db.row_factory=sqlite3.Row
                db.execute("BEGIN IMMEDIATE")
                row=db.execute("SELECT * FROM agent_event_outbox WHERE event_id=?",(event_id,)).fetchone()
                if not row or row["status"] in ("completed","superseded","processing") or row["attempts"]>=3:
                    db.rollback()
                    return
                envelope=AgentEventEnvelope.model_validate_json(row["envelope_json"])
                attempt=row["attempts"]+1
                db.execute("UPDATE agent_event_outbox SET status='processing',attempts=?,error=NULL WHERE event_id=?",(attempt,event_id))
                db.commit()
            started=time.perf_counter()
            try:
                state=self.scenarios.get(envelope.scenario_id).state
                revision,closures=self.plans.infrastructure(envelope.scenario_id,state.epoch)
                if state.epoch!=envelope.scenario_epoch or state.state_version!=envelope.simulation_state_version or (
                    envelope.infrastructure_revision is not None and envelope.infrastructure_revision!=revision
                ):
                    self._finish_stale(envelope,"The scenario version, epoch, or infrastructure revision changed before agent processing.")
                    return
                self.plans.supersede_stale(envelope.scenario_id,state.epoch,state.state_version,revision,
                    "A newer simulation snapshot or infrastructure revision invalidated this unapproved proposal.")
                if envelope.event_type not in TRIGGER_EVENT_TYPES:
                    self._finish_stale(envelope,"This event type is recorded for audit but is not an intelligence trigger.")
                    return
                city=generate_city(state.seed)
                reserved=self.plans.reserved_units(state.id,state.epoch)
                try:
                    inference_started=time.perf_counter()
                    prediction_set=predictions(state.id)
                    inference_ms=round((time.perf_counter()-inference_started)*1000,3)
                    model_status="ready"
                    model_error=None
                except ModelUnavailable as exc:
                    inference_ms=None
                    prediction_set=None
                    model_status="unavailable"
                    model_error=str(exc)
                context={"city":city,"state":state,"event":envelope,"revision":revision,"closures":closures,
                         "reserved":reserved,"prediction_set":prediction_set,"model_status":model_status,
                         "model_error":model_error,"ml_inference_ms":inference_ms,"outputs":{}}
                stages=[self._hazard,self._impact,self._priority,self._routing,self._allocation,self._commander]
                failed=False
                for definition,stage in zip(AGENTS,stages):
                    if failed:
                        self._record_run(envelope,definition.name,"skipped",context,{},"A required upstream agent failed; this stage did not execute.",attempt=attempt)
                        continue
                    if not self._is_current(envelope):
                        self._supersede_remaining(envelope,definition.name,context,attempt)
                        self._finish_stale(envelope,"Scenario assumptions changed during agent execution.")
                        return
                    try:
                        output=self._run_once(envelope,definition.name,context,stage,attempt)
                        context["outputs"][definition.name]=output
                    except Exception as exc:
                        self._record_run(envelope,definition.name,"failed",context,{},f"{definition.title} failed: {exc}",error=str(exc),attempt=attempt)
                        failed=True
                status="failed" if failed else "completed"
                if not failed and any(self._run_status(envelope.event_id,name)=="degraded" for name in AGENT_NAMES):
                    status="degraded"
                self._write_trace(envelope,status,context,time.perf_counter()-started)
                with sqlite3.connect(self.path,timeout=10,isolation_level=None) as db:
                    db.execute("UPDATE agent_event_outbox SET status=?,processed_at_utc=?,error=? WHERE event_id=?",
                               (status,_utc(),"One or more agents failed; see their run records." if failed else None,event_id))
            except Exception as exc:
                # A broken event must remain visible and retryable; never let a
                # background task exception erase its durable failure record.
                with sqlite3.connect(self.path,timeout=10,isolation_level=None) as db:
                    db.execute("UPDATE agent_event_outbox SET status='failed',error=?,processed_at_utc=? WHERE event_id=?",(str(exc)[:1000],_utc(),event_id))

    def _is_current(self,event):
        try:
            # Hot-path validation must not rebuild the flood state or acquire
            # the full scenario object before each agent and proposal commit.
            with sqlite3.connect(self.path) as db:
                row=db.execute("SELECT epoch,state_version FROM scenarios WHERE id=?",(event.scenario_id,)).fetchone()
                if not row:return False
                infra=db.execute("SELECT revision FROM scenario_infrastructure WHERE scenario_id=? AND epoch=?",
                                 (event.scenario_id,event.scenario_epoch)).fetchone()
            revision=infra[0] if infra else 0
            return (row[0]==event.scenario_epoch and row[1]==event.simulation_state_version
                    and (event.infrastructure_revision is None or revision==event.infrastructure_revision))
        except Exception:
            return False

    def _run_once(self,event,name,context,stage,attempt):
        with sqlite3.connect(self.path) as db:
            db.row_factory=sqlite3.Row
            row=db.execute("SELECT * FROM agent_runs WHERE event_id=? AND agent_name=?",(event.event_id,name)).fetchone()
            if row and row["status"] in ("completed","degraded"):
                return json.loads(row["output_json"])
        input_material={"event":event.model_dump(mode="json"),"state_version":context["state"].state_version,
                        "epoch":context["state"].epoch,"infrastructure_revision":context["revision"],
                        "upstream":context["outputs"].copy()}
        started_at=_utc(); started=time.perf_counter()
        run_id=self._begin_run(event,name,input_material,started_at,attempt)
        output=stage(context)
        duration=(time.perf_counter()-started)*1000
        status="degraded" if output.pop("_degraded",False) else "completed"
        explanation=output.pop("_explanation",f"{name} completed from the saved scenario and upstream algorithm outputs.")
        evidence=output.pop("_evidence",{})
        action=output.pop("_proposed_action",None)
        self._complete_run(run_id,status,output,evidence,explanation,action,duration)
        context["outputs"][name]=output
        return output

    def _begin_run(self,event,name,input_material,started_at,attempt):
        run_id=uuid.uuid4().hex
        digest=_hash(input_material)
        with sqlite3.connect(self.path,timeout=10,isolation_level=None) as db:
            db.execute("BEGIN IMMEDIATE")
            existing=db.execute("SELECT run_id,status,attempt FROM agent_runs WHERE event_id=? AND agent_name=?",(event.event_id,name)).fetchone()
            if existing and existing[1] in ("completed","degraded"):
                db.rollback()
                return existing[0]
            if existing:
                run_id=existing[0]
                attempt=max(attempt,existing[2]+1)
                db.execute("UPDATE agent_runs SET status='running',started_at=?,completed_at=NULL,duration_ms=NULL,error=NULL,attempt=?,input_hash=?,input_snapshot_ref=? WHERE run_id=?",
                    (started_at,attempt,digest,f"scenario:{event.scenario_id}:epoch:{event.scenario_epoch}:version:{event.simulation_state_version}",run_id))
            else:
                db.execute("INSERT INTO agent_runs(run_id,event_id,correlation_id,scenario_id,scenario_epoch,state_version,infrastructure_revision,agent_name,status,started_at,input_hash,input_snapshot_ref,attempt) VALUES(?,?,?,?,?,?,?,?,'running',?,?,?,?)",
                    (run_id,event.event_id,event.correlation_id,event.scenario_id,event.scenario_epoch,event.simulation_state_version,event.infrastructure_revision,name,started_at,digest,f"scenario:{event.scenario_id}:epoch:{event.scenario_epoch}:version:{event.simulation_state_version}",attempt))
            db.commit()
        return run_id

    def _complete_run(self,run_id,status,output,evidence,explanation,action,duration,error=None):
        with sqlite3.connect(self.path,timeout=10,isolation_level=None) as db:
            db.execute("UPDATE agent_runs SET status=?,completed_at=?,duration_ms=?,output_json=?,evidence_json=?,explanation=?,proposed_action=?,error=? WHERE run_id=?",
                (status,_utc(),round(duration,3),_canonical(output),_canonical(evidence),explanation,action,error[:1000] if error else None,run_id))

    def _record_run(self,event,name,status,context,output,explanation,error=None,attempt=1):
        with sqlite3.connect(self.path) as db:
            existing=db.execute("SELECT run_id FROM agent_runs WHERE event_id=? AND agent_name=?",(event.event_id,name)).fetchone()
        if existing:
            run_id=existing[0]
        else:
            input_material={"event_id":event.event_id,"state_version":event.simulation_state_version,"agent":name}
            run_id=self._begin_run(event,name,input_material,_utc(),attempt)
        self._complete_run(run_id,status,output,{},explanation,None,0.0,error)
        context["outputs"][name]=output

    def _run_status(self,event_id,name):
        with sqlite3.connect(self.path) as db:
            row=db.execute("SELECT status FROM agent_runs WHERE event_id=? AND agent_name=?",(event_id,name)).fetchone()
            return row[0] if row else "waiting"

    def _latest_output(self,name,scenario_id,epoch):
        with sqlite3.connect(self.path) as db:
            row=db.execute("""SELECT r.output_json FROM agent_runs r JOIN agent_event_outbox e ON e.event_id=r.event_id
                WHERE r.agent_name=? AND r.scenario_id=? AND r.scenario_epoch=? AND r.status IN ('completed','degraded')
                ORDER BY e.created_at_utc DESC LIMIT 1""",(name,scenario_id,epoch)).fetchone()
            return json.loads(row[0]) if row else {}

    def _hazard(self,c):
        state=c["state"]; event=c["event"]; pred=c["prediction_set"]
        current={item.entity_id:item for item in state.impacts.buildings}
        current_ids=sorted(i for i,item in current.items() if item.water_reaches_building)
        supported_predictions=[p for p in pred.predictions if getattr(p,"distribution_support_status","unavailable") in
            ("within_observed_support","edge_of_observed_support")] if pred else []
        predicted_ids=sorted(p.building_id for p in supported_predictions if p.predicted_future_exposed)
        support_counts={}
        if pred:
            for item in pred.predictions:
                support_counts[item.distribution_support_status]=support_counts.get(item.distribution_support_status,0)+1
        reliability_warnings=list(getattr(pred,"reliability_warnings",[])) if pred else []
        out_of_support_count=support_counts.get("outside_observed_support",0)
        if out_of_support_count:
            reliability_warnings.append(f"{out_of_support_count} building inputs are outside observed training support; their ML labels were excluded from forecast-based planning eligibility.")
        previous=self._latest_output("hazard_intelligence",state.id,state.epoch)
        previous_current=set(previous.get("current_exposed_building_ids",[]))
        previous_predicted=set(previous.get("predicted_exposed_building_ids",[]))
        previous_depth=previous.get("building_depth_m",{})
        escalated=sorted({entity for entity,item in current.items() if item.water_reaches_building and
                          item.max_depth_m-float(previous_depth.get(entity,0))>=POLICY["minimum_depth_increase_m"]})
        newly=sorted((set(current_ids)-previous_current)|(set(predicted_ids)-previous_predicted))
        changes=c["event"].payload.get("changes",{})
        evidence={"maximum_depth_m":state.maximum_depth_m,"affected_buildings":state.affected_buildings,
                  "rainfall_mm_h":state.parameters.rainfall_mm_h,"river_level_m":state.parameters.river_level_m,
                  "newly_threatened_count":len(newly),"depth_escalation_count":len(escalated),
                  "model_version":pred.model_version if pred else None,"model_status":c["model_status"],
                  "reliability_status":getattr(pred,"reliability_status","degraded") if pred else "unavailable",
                  "calibration_status":getattr(pred,"calibration_status","unavailable") if pred else "unavailable",
                  "distribution_support_counts":support_counts,"reliability_warnings":reliability_warnings}
        output={"current_exposed_building_ids":current_ids,"predicted_exposed_building_ids":predicted_ids,
                "newly_threatened_building_ids":newly,"escalating_depth_building_ids":escalated,
                "building_depth_m":{key:round(item.max_depth_m,4) for key,item in current.items()},
                "model_status":c["model_status"],"model_version":pred.model_version if pred else None,
                "model_limitation":"Synthetic simulator only; calibrated output, when available, is a synthetic-label estimate and not a real-world disaster probability." if pred else None,
                "reliability_status":getattr(pred,"reliability_status","degraded") if pred else "unavailable",
                "calibration_status":getattr(pred,"calibration_status","unavailable") if pred else "unavailable",
                "distribution_support_counts":support_counts,"reliability_warnings":reliability_warnings,
                "unsupported_prediction_count":out_of_support_count,
                "changed_parameters":changes,"event_reason":event.event_type}
        if not pred:
            output["_degraded"]=True
            output["_explanation"]=f"Rule-based physical hazard evidence is available; local ML predictions are unavailable ({c['model_error']}). No prediction was fabricated."
        else:
            degraded=getattr(pred,"reliability_status","degraded")!="available" or out_of_support_count>0
            if degraded:
                output["_degraded"]=True
                output["_explanation"]=f"Physical flood evidence is authoritative. The local model is {getattr(pred,'reliability_status','degraded')}; {out_of_support_count} out-of-support labels were excluded from planning eligibility. Reliability warnings are attached to this trace."
            else:
                output["_explanation"]=f"Physical exposure uses saved flood impacts; supported future labels come from local model {pred.model_version}. They are synthetic-only estimates, not operational certainty."
        output["_evidence"]=evidence
        return output

    def _impact(self,c):
        state=c["state"]; previous=self._latest_output("impact_assessment",state.id,state.epoch)
        old=previous.get("physical_access_status",{})
        new={}
        for group in ("roads","bridges"):
            for item in getattr(state.impacts,group):
                new[item.entity_id]=item.status
        roads={key:value for key,value in new.items() if key.startswith("road-")}
        bridges={key:value for key,value in new.items() if key.startswith("bridge-")}
        changed=sorted(key for key,value in new.items() if old.get(key)!=value and key in old)
        exposed_buildings=sorted(item.entity_id for item in state.impacts.buildings if item.water_reaches_building)
        city=c["city"]; facilities={h.building_id:"hospital" for h in city.hospitals}
        facilities.update({s.building_id:"shelter" for s in city.shelters})
        facility_exposure=sorted([{"building_id":item.entity_id,"facility_type":facilities[item.entity_id],"exposed":bool(item.water_reaches_building),"depth_m":round(item.max_depth_m,3)} for item in state.impacts.buildings if item.entity_id in facilities],key=lambda item:item["building_id"])
        output={"newly_exposed_building_ids":sorted(set(exposed_buildings)-set(previous.get("exposed_building_ids",[]))),
                "exposed_building_ids":exposed_buildings,"changed_road_or_bridge_ids":changed,
                "physical_access_status":new,"road_statuses":roads,"bridge_statuses":bridges,
                "facility_exposure":facility_exposure,"manual_closures":c["closures"]}
        output["_evidence"]={"current_exposed_buildings":len(exposed_buildings),"changed_physical_access_assets":len(changed),
                              "roads_open_or_caution":sum(value in ("open","caution") for value in roads.values()),
                              "bridges_closed":sum(value=="closed" for value in bridges.values())}
        output["_explanation"]=f"Compared current flood-derived building and infrastructure impacts with the previous assessment in epoch {state.epoch}; no structural damage is inferred."
        return output

    def _priority(self,c):
        state=c["state"]; result=priorities(c["city"],state,c["prediction_set"],c["closures"],c["reserved"])
        previous=self._latest_output("rescue_priority",state.id,state.epoch)
        old={item["building_id"]:item["priority_score"] for item in previous.get("ranked_destinations",[])}
        deltas=[{"building_id":item["building_id"],"previous_score":old[item["building_id"]],
                 "current_score":item["priority_score"],"delta":round(item["priority_score"]-old[item["building_id"]],2)}
                for item in result if item["building_id"] in old and abs(item["priority_score"]-old[item["building_id"]])>=POLICY["minimum_priority_score_change"]]
        top_ids=[item["building_id"] for item in result[:5]]
        old_top=previous.get("top_destination_ids",[])
        output={"ranked_destinations":result,"top_destination_ids":top_ids,"score_changes":deltas,
                "newly_critical_destination_ids":sorted(set(top_ids)-set(old_top))}
        output["_evidence"]={"eligible_destinations":len(result),"top_destination_ids":top_ids,
                              "significant_score_changes":deltas,"priority_algorithm":"Part 5 transparent 0–100 rule index"}
        output["_explanation"]=f"Reused the Part 5 priority formula for {len(result)} currently or locally forecast-eligible destinations; score-change threshold is {POLICY['minimum_priority_score_change']:.1f} points."
        return output

    def _routing(self,c):
        city=c["city"]; state=c["state"]; ranked=c["outputs"]["rescue_priority"]["ranked_destinations"]
        graph=build_road_graph(city,state,c["closures"])
        positions=self.plans.unit_positions(state.id,state.epoch)
        units=[unit.model_copy(update={"position":unit.position.model_copy(update=positions[unit.id])}) if unit.id in positions else unit
               for unit in city.rescue_units if unit.status=="standby" and unit.type!="boat" and unit.id not in c["reserved"]]
        buildings={building.id:building for building in city.buildings}
        options=[]; reachable=set()
        for unit in units:
            for destination in ranked:
                result=route(graph,unit.position,buildings[destination["building_id"]].position,unit.type)
                if result["reachable"]:
                    options.append({"unit_id":unit.id,"destination_id":destination["building_id"],"route":result,
                                    "unit_capacity":unit.capacity})
                    reachable.add(destination["building_id"])
        unreachable=[{"building_id":item["building_id"],"reason":"No unreserved compatible ground unit has a route under current flood, closure and accessibility constraints."} for item in ranked if item["building_id"] not in reachable]
        previous=self._latest_output("routing",state.id,state.epoch)
        old_routes={f"{item['unit_id']}|{item['destination_id']}":item["route"].get("edge_ids",[]) for item in previous.get("reachable_assignments",[])}
        new_routes={f"{item['unit_id']}|{item['destination_id']}":item["route"].get("edge_ids",[]) for item in options}
        changed=[key for key in sorted(set(old_routes)&set(new_routes)) if old_routes[key]!=new_routes[key]]
        invalidated=sorted(set(old_routes)-set(new_routes))
        output={"reachable_assignments":options,"unreachable_destinations":unreachable,
                "changed_route_keys":changed,"invalidated_route_keys":invalidated,
                "manual_closure_revision":c["revision"],"manual_closures":c["closures"]}
        output["_evidence"]={"route_pair_count":len(options),"unreachable_destination_count":len(unreachable),
                              "changed_routes":changed,"invalidated_routes":invalidated,
                              "unit_inventory_ids":[unit.id for unit in units]}
        output["_explanation"]=f"Computed {len(options)} compatible unit-destination routes on the existing NetworkX graph using current water depths, vehicle limits and manual closures."
        return output

    def _allocation(self,c):
        started=time.perf_counter()
        route_rows=c["outputs"]["routing"]["reachable_assignments"]
        route_map={(item["unit_id"],item["destination_id"]):item["route"] for item in route_rows}
        plan=generate_plan(c["city"],c["state"],c["prediction_set"],c["closures"],
            infrastructure_revision=c["revision"],reserved_unit_ids=c["reserved"],
            priorities_override=c["outputs"]["rescue_priority"]["ranked_destinations"],
            route_map_override=route_map,trigger_event_id=c["event"].event_id)
        solver_ms=round((time.perf_counter()-started)*1000,3)
        output={"plan_candidate":plan.model_dump(mode="json"),"assigned_unit_ids":[m["unit_id"] for m in plan.missions],
                "assignments":[{"unit_id":m["unit_id"],"destination_id":m["destination_id"],"edge_ids":m["route"]["edge_ids"]} for m in plan.missions],
                "unreachable_destinations":plan.unreachable,"baseline":plan.comparison["baseline"],
                "optimized":plan.comparison["optimized"],"reserved_unit_ids":sorted(c["reserved"]),
                "solver_duration_ms":solver_ms}
        output["_evidence"]={"assigned_mission_count":len(plan.missions),"baseline":plan.comparison["baseline"],
                              "optimized":plan.comparison["optimized"],"reserved_unit_ids":sorted(c["reserved"]),
                              "unreachable_count":len(plan.unreachable)}
        output["_explanation"]=f"SciPy linear assignment generated {len(plan.missions)} feasible, one-unit-per-destination missions; {len(plan.unreachable)} destinations have no compatible reachable ground unit."
        return output

    def _commander(self,c):
        event=c["event"]; state=c["state"]; outputs=c["outputs"]
        hazard=outputs["hazard_intelligence"]; impact=outputs["impact_assessment"]
        priority=outputs["rescue_priority"]; routing=outputs["routing"]; allocation=outputs["resource_allocation"]
        if event.event_type in ("rescue_plan_rejected",):
            return {"plan_id":None,"decision":"no_new_proposal","_explanation":"The commander rejected the prior recommendation; rejection does not release or alter approved resources."}
        material=(event.event_type in ("manual_assessment","scenario_reset") and bool(priority["ranked_destinations"])) or bool(
            hazard["newly_threatened_building_ids"] or hazard["escalating_depth_building_ids"] or
            impact["changed_road_or_bridge_ids"] or routing["changed_route_keys"] or routing["invalidated_route_keys"] or
            priority["score_changes"] or priority["newly_critical_destination_ids"] or event.event_type=="infrastructure_changed" or
            event.event_type in ("rescue_plan_approved","mission_blocked","mission_cancelled","unit_returned_to_service"))
        if not priority["ranked_destinations"]:
            material=False
        if not material:
            return {"plan_id":None,"decision":"no_new_proposal","trigger_rationale":"No material exposure, access, priority or reservation change met the trigger policy.",
                    "_explanation":"No proposal was created because deterministic trigger thresholds found no material change; the assessment remains in the trace."}
        existing=self.plans.by_trigger(event.event_id)
        if existing:
            return {"plan_id":existing.plan_id,"decision":"proposal_created","trigger_rationale":"Idempotent recovery found the proposal already persisted for this trigger.",
                    "plan_status":existing.status,"scenario_version":existing.scenario_version,"scenario_epoch":existing.scenario_epoch,
                    "infrastructure_revision":existing.infrastructure_revision,"_explanation":"Recovered the proposal persisted for this trigger without creating a duplicate."}
        plan=RescuePlan.model_validate(allocation["plan_candidate"])
        if self._equivalent_plan(plan):
            return {"plan_id":None,"decision":"duplicate_suppressed","trigger_rationale":"A matching proposal already exists for this epoch, closure revision and assignment signature.",
                    "_explanation":"A duplicate recommendation was suppressed; the existing proposal remains the review record."}
        if not self._is_current(event):
            raise ValueError("State changed before Commander persistence; the proposal candidate was discarded.")
        try:
            persistence_started=time.perf_counter()
            saved=self.plans.save(plan)
            persistence_ms=round((time.perf_counter()-persistence_started)*1000,3)
        except ValueError as exc:
            raise ValueError(f"Proposal became stale before persistence: {exc}") from exc
        return {"plan_id":saved.plan_id,"decision":"proposal_created","trigger_rationale":self._rationale(event,outputs),
                "plan_status":saved.status,"scenario_version":saved.scenario_version,"scenario_epoch":saved.scenario_epoch,
                "infrastructure_revision":saved.infrastructure_revision,
                "persistence_duration_ms":persistence_ms,
                "_proposed_action":"Create a rescue-plan proposal for human commander review; no approval or mission execution.",
                "_evidence":{"plan_id":saved.plan_id,"assignment_count":len(saved.missions),"baseline":saved.comparison["baseline"],
                             "optimized":saved.comparison["optimized"],"infrastructure_revision":saved.infrastructure_revision},
                "_explanation":"A versioned recommendation was persisted. Commander approval remains required; no mission was committed."}

    @staticmethod
    def _rationale(event,outputs):
        h=outputs["hazard_intelligence"]; i=outputs["impact_assessment"]; r=outputs["routing"]; p=outputs["rescue_priority"]
        pieces=[]
        if h["newly_threatened_building_ids"]:pieces.append(f"{len(h['newly_threatened_building_ids'])} newly threatened building(s)")
        if h["escalating_depth_building_ids"]:pieces.append(f"{len(h['escalating_depth_building_ids'])} building(s) increased at least {POLICY['minimum_depth_increase_m']:.2f} m")
        if i["changed_road_or_bridge_ids"]:pieces.append(f"{len(i['changed_road_or_bridge_ids'])} modeled access status change(s)")
        if r["changed_route_keys"] or r["invalidated_route_keys"]:pieces.append("a route changed or became unavailable")
        if p["score_changes"]:pieces.append(f"{len(p['score_changes'])} priority score(s) changed by at least {POLICY['minimum_priority_score_change']:.1f}")
        if event.event_type=="infrastructure_changed":pieces.append("manual infrastructure revision changed")
        if event.event_type=="rescue_plan_approved":pieces.append("commander approval changed resource reservations")
        if event.event_type=="mission_blocked":pieces.append("a dispatched mission lost access on its remaining route")
        if event.event_type=="mission_cancelled":pieces.append("a ready mission was cancelled and released its reservation")
        if event.event_type=="unit_returned_to_service":pieces.append("a commander restored a simulated unit to availability")
        return "; ".join(pieces) or f"{event.event_type} triggered an explicit assessment"

    def _equivalent_plan(self,plan):
        with sqlite3.connect(self.path) as db:
            rows=db.execute("SELECT payload FROM rescue_plans WHERE scenario_id=? AND scenario_epoch=? AND status='proposed' ORDER BY created_at DESC LIMIT 10",(plan.scenario_id,plan.scenario_epoch)).fetchall()
        return any(_plan_signature(RescuePlan.model_validate_json(row[0]))==_plan_signature(plan) for row in rows)

    def _write_trace(self,event,status,context,total_seconds):
        outputs=context["outputs"]
        commander=outputs.get("commander_strategy",{})
        plan_id=commander.get("plan_id")
        summary=commander.get("_explanation",commander.get("trigger_rationale","Agent run ended without a commander proposal."))
        evidence={"event_type":event.event_type,"affected_entity_ids":event.affected_entity_ids,
                  "pipeline_duration_ms":round(total_seconds*1000,3),
                  "event_ingestion_ms":event.outbox_insert_ms,
                  "ml_inference_ms":context.get("ml_inference_ms"),
                  "agent_durations_ms":{name:self._run_duration(event.event_id,name) for name in AGENT_NAMES},
                  "routing_duration_ms":self._run_duration(event.event_id,"routing"),
                  "resource_allocation_duration_ms":outputs.get("resource_allocation",{}).get("solver_duration_ms"),
                  "plan_persistence_duration_ms":commander.get("persistence_duration_ms"),
                  "model_status":context["model_status"],"model_error":context["model_error"],
                  "model_reliability_status":outputs.get("hazard_intelligence",{}).get("reliability_status","unavailable"),
                  "model_calibration_status":outputs.get("hazard_intelligence",{}).get("calibration_status","unavailable"),
                  "distribution_support_counts":outputs.get("hazard_intelligence",{}).get("distribution_support_counts",{}),
                  "model_reliability_warnings":outputs.get("hazard_intelligence",{}).get("reliability_warnings",[]),
                  "proposal_decision":commander.get("decision"),"plan_id":plan_id,
                  "exposures":outputs.get("hazard_intelligence",{}).get("newly_threatened_building_ids",[]),
                  "road_changes":sorted(set(outputs.get("impact_assessment",{}).get("changed_road_or_bridge_ids",[]))|
                                         ({event.payload["road_id"]} if event.event_type=="infrastructure_changed" and event.payload.get("road_id") else set())),
                  "route_changes":outputs.get("routing",{}).get("changed_route_keys",[]),
                  "invalidated_routes":outputs.get("routing",{}).get("invalidated_route_keys",[]),
                  "manual_closures":outputs.get("routing",{}).get("manual_closures",[]),
                  "priority_changes":outputs.get("rescue_priority",{}).get("score_changes",[]),
                  "allocation":outputs.get("resource_allocation",{}).get("optimized",{})}
        with sqlite3.connect(self.path) as db:
            db.execute("INSERT OR REPLACE INTO decision_traces(trace_id,event_id,correlation_id,scenario_id,scenario_epoch,state_version,infrastructure_revision,status,plan_id,summary,evidence_json,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (event.event_id,event.event_id,event.correlation_id,event.scenario_id,event.scenario_epoch,event.simulation_state_version,event.infrastructure_revision,status,plan_id,summary,_canonical(evidence),_utc()))

    def _run_duration(self,event_id,name):
        with sqlite3.connect(self.path) as db:
            row=db.execute("SELECT duration_ms FROM agent_runs WHERE event_id=? AND agent_name=?",(event_id,name)).fetchone()
            return row[0] if row else None

    def _finish_stale(self,event,reason):
        for name in AGENT_NAMES:
            if self._run_status(event.event_id,name)=="waiting":
                self._record_run(event,name,"superseded",{"outputs":{}},{},reason)
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE agent_event_outbox SET status='superseded',error=?,processed_at_utc=? WHERE event_id=?",(reason,_utc(),event.event_id))
            db.execute("INSERT OR REPLACE INTO decision_traces(trace_id,event_id,correlation_id,scenario_id,scenario_epoch,state_version,infrastructure_revision,status,plan_id,summary,evidence_json,created_at) VALUES(?,?,?,?,?, ?,?,'superseded',NULL,?,?,?)",
                (event.event_id,event.event_id,event.correlation_id,event.scenario_id,event.scenario_epoch,event.simulation_state_version,event.infrastructure_revision,reason,"{}",_utc()))

    def _supersede_remaining(self,event,current_name,context,attempt):
        seen=False
        for agent in AGENT_NAMES:
            if agent==current_name:seen=True;continue
            if seen and self._run_status(event.event_id,agent)=="waiting":
                self._record_run(event,agent,"superseded",context,{},"Scenario assumptions changed before this agent could execute.",attempt=attempt)

    def get_trace(self,event_id):
        with sqlite3.connect(self.path) as db:
            db.row_factory=sqlite3.Row
            eventrow=db.execute("SELECT * FROM agent_event_outbox WHERE event_id=?",(event_id,)).fetchone()
            if not eventrow:return None
            trace_row=db.execute("SELECT * FROM decision_traces WHERE event_id=?",(event_id,)).fetchone()
            runrows=db.execute("SELECT * FROM agent_runs WHERE event_id=? ORDER BY rowid",(event_id,)).fetchall()
            event=AgentEventEnvelope.model_validate_json(eventrow["envelope_json"])
            trace=AgentTrace(trace_id=trace_row["trace_id"],event_id=trace_row["event_id"],correlation_id=trace_row["correlation_id"],
                scenario_id=trace_row["scenario_id"],scenario_epoch=trace_row["scenario_epoch"],simulation_state_version=trace_row["state_version"],
                infrastructure_revision=trace_row["infrastructure_revision"],status=trace_row["status"],plan_id=trace_row["plan_id"],
                summary=trace_row["summary"],evidence=json.loads(trace_row["evidence_json"]),created_at_utc=trace_row["created_at"]) if trace_row else None
            agents=[_run_record(row) for row in runrows]
            planrow=db.execute("SELECT payload,status FROM rescue_plans WHERE trigger_event_id=? ORDER BY created_at DESC LIMIT 1",(event_id,)).fetchone()
            related=json.loads(planrow[0]) if planrow else None
            if related and planrow[1]!=related["status"]:related["status"]=planrow[1]
            return AgentTraceDetail(event=event,event_status=eventrow["status"],attempts=eventrow["attempts"],agents=agents,trace=trace,related_plan=related)

    def runs(self,scenario_id,limit=50):
        with sqlite3.connect(self.path) as db:
            db.row_factory=sqlite3.Row
            rows=db.execute("SELECT * FROM agent_runs WHERE scenario_id=? ORDER BY started_at DESC,rowid DESC LIMIT ?",(scenario_id,limit)).fetchall()
        return [_run_record(row) for row in rows]

    def traces(self,scenario_id,limit=50):
        with sqlite3.connect(self.path) as db:
            db.row_factory=sqlite3.Row
            rows=db.execute("SELECT * FROM decision_traces WHERE scenario_id=? ORDER BY created_at DESC LIMIT ?",(scenario_id,limit)).fetchall()
        return [_trace_record(row) for row in rows]

    def dashboard(self,scenario_id,state):
        revision,active_closures=self.plans.infrastructure(scenario_id,state.epoch)
        runs=self.runs(scenario_id,100)
        latest={}
        for run in runs:
            if run.scenario_epoch==state.epoch and run.agent_name not in latest:latest[run.agent_name]=run
        traces=self.traces(scenario_id,1)
        with sqlite3.connect(self.path) as db:
            pending=db.execute("SELECT COUNT(*) FROM agent_event_outbox WHERE scenario_id=? AND status IN ('pending','processing')",(scenario_id,)).fetchone()[0]
        city=generate_city(state.seed)
        reserved=self.plans.reserved_units(scenario_id,state.epoch)
        available=sum(unit.status=="standby" and unit.type!="boat" and unit.id not in reserved for unit in city.rescue_units)
        latest_trace=next((trace for trace in self.traces(scenario_id,50) if trace.scenario_epoch==state.epoch),None)
        action=False
        if latest_trace and latest_trace.plan_id:
            with sqlite3.connect(self.path) as db:
                planrow=db.execute("SELECT status FROM rescue_plans WHERE plan_id=?",(latest_trace.plan_id,)).fetchone()
            action=bool(planrow and planrow[0]=="proposed" and latest_trace.simulation_state_version==state.state_version and latest_trace.infrastructure_revision==revision)
        impact_status={item.entity_id:item.status for group in (state.impacts.roads,state.impacts.bridges) for item in group}
        closures=active_closures
        closed=set(closures)|{entity_id for entity_id,status in impact_status.items() if status in ("closed","flooded","manually_blocked")}
        with sqlite3.connect(self.path) as db:
            approved_rows=db.execute("SELECT plan_id,payload FROM rescue_plans WHERE scenario_id=? AND scenario_epoch=? AND status='approved'",(scenario_id,state.epoch)).fetchall()
        approved_route_alerts=[]
        for plan_id,payload in approved_rows:
            approved=RescuePlan.model_validate_json(payload)
            if any(closed.intersection(mission["route"].get("road_ids",[])) for mission in approved.missions):
                approved_route_alerts.append(plan_id)
        action=action or bool(approved_route_alerts)
        return AgentDashboard(scenario_id=scenario_id,scenario_epoch=state.epoch,simulation_state_version=state.state_version,
            infrastructure_revision=revision,definitions=AGENTS,latest_runs=list(latest.values()),latest_trace=latest_trace,
            pending_events=pending,available_ground_units=available,reserved_ground_units=sorted(reserved),commander_action_required=action,
            approved_route_review_required=bool(approved_route_alerts),approved_route_review_plan_ids=approved_route_alerts,
            manual_closure_road_ids=active_closures)

    def events(self,scenario_id,limit=50):
        with sqlite3.connect(self.path) as db:
            rows=db.execute("SELECT envelope_json FROM agent_event_outbox WHERE scenario_id=? ORDER BY created_at_utc DESC LIMIT ?",(scenario_id,limit)).fetchall()
        return [AgentEventEnvelope.model_validate_json(row[0]) for row in rows]


def _run_record(row):
    return AgentRunRecord(run_id=row["run_id"],event_id=row["event_id"],correlation_id=row["correlation_id"],
        scenario_id=row["scenario_id"],scenario_epoch=row["scenario_epoch"],simulation_state_version=row["state_version"],
        infrastructure_revision=row["infrastructure_revision"],agent_name=row["agent_name"],status=row["status"],
        started_at_utc=row["started_at"],completed_at_utc=row["completed_at"],duration_ms=row["duration_ms"],
        input_hash=row["input_hash"],input_snapshot_ref=row["input_snapshot_ref"],output_summary=json.loads(row["output_json"]),
        numerical_evidence=json.loads(row["evidence_json"]),proposed_action=row["proposed_action"],explanation=row["explanation"],
        error=row["error"],attempt=row["attempt"])


def _trace_record(row):
    return AgentTrace(trace_id=row["trace_id"],event_id=row["event_id"],correlation_id=row["correlation_id"],
        scenario_id=row["scenario_id"],scenario_epoch=row["scenario_epoch"],simulation_state_version=row["state_version"],
        infrastructure_revision=row["infrastructure_revision"],status=row["status"],plan_id=row["plan_id"],
        summary=row["summary"],evidence=json.loads(row["evidence_json"]),created_at_utc=row["created_at"])


def _plan_signature(plan: RescuePlan):
    return _canonical({
        "scenario_epoch":plan.scenario_epoch,"infrastructure_revision":plan.infrastructure_revision,
        "priorities":[(row["building_id"],row["priority_score"]) for row in plan.priorities],
        "missions":[(row["unit_id"],row["destination_id"],row["route"].get("edge_ids",[])) for row in plan.missions],
        "unreachable":[row["building_id"] for row in plan.unreachable],
    })
