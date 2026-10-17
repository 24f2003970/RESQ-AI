"""Deterministic Part 14 positive and unreachable demos on disposable SQLite.

Run from repository root:
  backend/.venv/Scripts/python.exe backend/demo_acceptance_rc1.py
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path


class AcceptanceFailure(RuntimeError):
    pass


class Runner:
    def __init__(self):
        self.report = {
            "schema_version": 1,
            "status": "FAIL",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "environment": {"os": platform.platform(), "python": platform.python_version(), "storage": "disposable SQLite"},
            "scenarios": {}, "missions": {}, "checks": [], "timings_ms": {},
        }

    def check(self, name: str, detail: str, started: float | None = None):
        elapsed = round((time.perf_counter() - started) * 1000, 3) if started is not None else None
        row = {"name": name, "status": "PASS", "detail": detail}
        if elapsed is not None:
            row["duration_ms"] = elapsed
            self.report["timings_ms"].setdefault(name, []).append(elapsed)
        self.report["checks"].append(row)

    @staticmethod
    def require(condition: bool, message: str):
        if not condition:
            raise AcceptanceFailure(message)

    @staticmethod
    def response(response, expected: int, label: str):
        if response.status_code != expected:
            try:
                detail = response.json()
            except ValueError:
                detail = response.text[:500]
            raise AcceptanceFailure(f"{label}: expected HTTP {expected}, received {response.status_code}: {detail}")
        return response.json() if response.content else None

    def run(self):
        from fastapi.testclient import TestClient
        from app import main
        from app.city_service import generate_city

        with TestClient(main.app) as client:
            started = time.perf_counter()
            health = self.response(client.get("/api/v1/health"), 200, "backend health")
            city = self.response(client.get("/api/v1/city/state?seed=2026"), 200, "city state")
            self.require(health["status"] == "ok" and len(city["roads"]) >= 1, "Local API or synthetic road network unavailable.")
            self.check("startup_and_health", "Fresh app lifespan is ready; synthetic city loaded.", started)

            # Demo A: measured deterministic configuration found with the production simulator/router.
            created = self.response(client.post("/api/v1/scenarios", headers={"Idempotency-Key":"rc1-demo-a-create"},
                json={"name":"RC1 Demo A · Supported rescue", "seed":2026, "preset":"mild"}), 201, "Demo A create")
            state = created["state"]
            sid = state["id"]
            self.report["scenarios"]["demo_a"] = {"id":sid,"seed":2026,"preset":"mild","rainfall_mm_h":30,"river_level_m":0.6,"drainage_effectiveness":0.2,"ticks":6}
            started = time.perf_counter()
            state = self.response(client.patch(f"/api/v1/scenarios/{sid}/parameters", json={"rainfall_mm_h":30,"river_level_m":0.6,"drainage_effectiveness":0.2,"expected_version":state["state_version"]}), 200, "Demo A forcing") ["state"]
            state = self.response(client.post(f"/api/v1/scenarios/{sid}/advance", json={"steps":6,"single_step":True,"expected_version":state["state_version"]}), 200, "Demo A progression")["state"]
            self.require(state["tick"] == 6 and state["affected_buildings"] >= 5, "Demo A forcing did not create multi-building flood exposure.")
            self.report["scenarios"]["demo_a"].update({"epoch":state["epoch"],"tick":state["tick"],"state_version":state["state_version"],"affected_buildings":state["affected_buildings"],"max_flood_depth_m":state["maximum_depth_m"]})
            self.check("demo_a_flood_and_exposure", f"Tick {state['tick']}; {state['affected_buildings']} physically exposed buildings; max depth {state['maximum_depth_m']} m.", started)

            model = self.response(client.get("/api/v1/ml/model"), 200, "model status")
            predictions = self.response(client.get(f"/api/v1/scenarios/{sid}/predictions"), 200, "local inference")
            self.require(model["status"] == "ready" and len(predictions["predictions"]) == 72, "Local prediction artifact or inference is unavailable.")
            self.check("local_ml_and_reliability", f"Local model {model['model_version']} returned {len(predictions['predictions'])} predictions; model status is {model['status']}.")

            events = self.response(client.get(f"/api/v1/scenarios/{sid}/agent-events"), 200, "agent outbox")
            event = next((item for item in reversed(events) if item["event_type"] == "simulation_advanced" and item["simulation_state_version"] == state["state_version"]), None)
            self.require(event is not None, "Flood advance did not enqueue the event-driven agent run.")
            trace = self.response(client.get(f"/api/v1/agent-traces/{event['event_id']}"), 200, "six-agent trace")
            self.require(trace["event_status"] in ("completed", "degraded") and len(trace["agents"]) == 6, "Six-agent trace is incomplete.")
            self.report["scenarios"]["demo_a"]["agent_trace_id"] = event["event_id"]
            self.check("six_agent_decision_evidence", f"Trace {event['event_id']} persisted {len(trace['agents'])} agent records ({trace['event_status']}).")

            started = time.perf_counter()
            plan = self.response(client.post(f"/api/v1/scenarios/{sid}/rescue-plans"), 201, "Demo A proposal")
            self.require(plan["status"] == "proposed" and plan["solver_status"] and plan["missions"], "Demo A has no feasible route-supported proposal.")
            multi_road = [item for item in plan["missions"] if len(item["route"].get("road_ids", [])) >= 3 and item["route"].get("distance_m", 0) >= 300]
            self.require(multi_road, "The proposal has no route long enough to cross multiple connected corridors.")
            self.report["scenarios"]["demo_a"].update({"plan_id":plan["plan_id"],"solver_status":plan["solver_status"],"infrastructure_revision":plan["infrastructure_revision"],"proposal_assignments":len(plan["missions"]),"candidate_routes":[{"unit_id":m["unit_id"],"destination_id":m["destination_id"],"road_ids":m["route"]["road_ids"],"distance_m":m["route"]["distance_m"]} for m in multi_road]})
            self.check("proposal_freshness_and_solver", f"Fresh version {plan['scenario_version']}, infrastructure revision {plan['infrastructure_revision']}; {len(plan['missions'])} assignments; supported multi-corridor route found.", started)

            started = time.perf_counter()
            approved = self.response(client.post(f"/api/v1/rescue-plans/{plan['plan_id']}/decision", json={"action":"approved","reason":"Explicit RC1 test commander approval","expected_version":state["state_version"]}), 200, "explicit plan approval")
            self.require(approved["status"] == "approved", "Commander approval was not persisted.")
            mission_rows = self.response(client.get(f"/api/v1/scenarios/{sid}/missions?epoch={state['epoch']}"), 200, "approved missions")
            self.require(mission_rows and all(row["status"] == "ready" for row in mission_rows), "Approval did not create ready missions.")
            mission = next((row for row in mission_rows if row["unit_id"] in {item["unit_id"] for item in multi_road} and len(row["route"].get("road_ids", [])) >= 3), None)
            self.require(mission is not None, "No approved mission retained the multi-corridor route.")
            self.check("human_approval_and_mission_creation", f"Plan explicitly approved; {len(mission_rows)} ready missions persisted without auto-dispatch.", started)

            started = time.perf_counter()
            dispatched = self.response(client.post(f"/api/v1/missions/{mission['mission_id']}/dispatch", headers={"Idempotency-Key":"rc1-demo-a-dispatch"}, json={"expected_version":mission["mission_version"]}), 200, "explicit dispatch")
            self.require(dispatched["status"] == "en_route", "Explicit dispatch did not place the mission en route.")
            self.report["missions"]["demo_a"] = {"id":mission["mission_id"],"unit_id":mission["unit_id"],"destination_id":mission["destination_id"],"original_road_ids":mission["route"]["road_ids"],"original_distance_m":mission["total_distance_m"]}
            self.check("explicit_dispatch", f"Mission {mission['mission_id']} dispatched; routes remain simulation-only.", started)

            # Move a measured distance on backend authority, then close the second corridor.
            clock = self.response(client.get(f"/api/v1/scenarios/{sid}/missions/clock"), 200, "mission clock")
            movement = self.response(client.post(f"/api/v1/scenarios/{sid}/missions/clock/advance", headers={"Idempotency-Key":"rc1-demo-a-move-before-closure"}, json={"expected_version":clock["version"],"expected_state_version":state["state_version"],"seconds":18}), 200, "movement before closure")
            live = next(row for row in movement["missions"] if row["mission_id"] == mission["mission_id"])
            for index in range(40):
                if live["traversed_distance_m"] >= 90:
                    break
                clock = movement["clock"]
                step_seconds = 1 if live["traversed_distance_m"] >= 70 else 5
                movement = self.response(client.post(f"/api/v1/scenarios/{sid}/missions/clock/advance", headers={"Idempotency-Key":f"rc1-demo-a-move-before-closure-{index}"}, json={"expected_version":clock["version"],"expected_state_version":state["state_version"],"seconds":step_seconds}), 200, "movement before closure")
                live = next(row for row in movement["missions"] if row["mission_id"] == mission["mission_id"])
            self.require(live["traversed_distance_m"] >= 90 and live["traversed_distance_m"] <= 130, f"Expected the unit part-way along the first corridor before closure; got {live['traversed_distance_m']:.1f} m.")
            self.report["missions"]["demo_a"].update({"distance_before_closure_m":live["traversed_distance_m"],"position_before_closure":live["position"],"route_segment_before_closure":live["route_segment_index"]})
            self.check("authoritative_road_movement", f"Clock advanced 17 s to {live['traversed_distance_m']:.1f} m on saved route geometry.")

            close_road_id = mission["route"]["road_ids"][1]
            closure = self.response(client.post(f"/api/v1/scenarios/{sid}/road-closures", json={"road_id":close_road_id,"reason":"RC1 Demo A planned downstream disruption"}), 200, "relevant closure")
            blocked = self.response(client.get(f"/api/v1/missions/{mission['mission_id']}"), 200, "blocked mission")
            self.require(blocked["status"] == "blocked" and blocked["traversed_distance_m"] == live["traversed_distance_m"], "The closure did not block in place without fictional progress.")
            self.report["missions"]["demo_a"].update({"closed_road_id":close_road_id,"blocked_distance_m":blocked["traversed_distance_m"],"infrastructure_revision":closure["infrastructure_revision"]})
            self.check("road_disruption_stops_mission", f"Closed {close_road_id}; mission stopped at {blocked['traversed_distance_m']:.1f} m.")

            proposal = self.response(client.post(f"/api/v1/missions/{mission['mission_id']}/route-proposal", headers={"Idempotency-Key":"rc1-demo-a-route-proposal"}, json={"expected_version":blocked["mission_version"]}), 200, "safe route proposal")
            candidate = proposal["route_proposal"]
            self.require(candidate and candidate["route"]["reachable"], f"No safe alternative route exists in this configuration: {candidate and candidate['route'].get('reason')}")
            old_roads = set(mission["route"]["road_ids"])
            new_roads = candidate["route"].get("road_ids", [])
            self.require(close_road_id not in new_roads and new_roads != mission["route"]["road_ids"], "Replacement route did not avoid the closed segment or change route.")
            self.report["missions"]["demo_a"].update({"replacement_road_ids":new_roads,"replacement_distance_m":candidate["route"].get("distance_m"),"route_revision_id":candidate["route_revision_id"]})
            self.check("genuine_route_revision", f"Reachable replacement {new_roads} avoids closed {close_road_id}; route generated from persisted position and road graph.")

            revision = self.response(client.post(f"/api/v1/missions/{mission['mission_id']}/route-approval", headers={"Idempotency-Key":"rc1-demo-a-route-approval"}, json={"expected_version":proposal["mission_version"],"route_revision_id":candidate["route_revision_id"]}), 200, "route approval")
            self.require(revision["status"] == "en_route" and revision["route_revision"] == 2, "Version-checked route approval did not resume the mission on revision 2.")
            self.check("version_checked_route_approval", f"Commander approved route revision {revision['route_revision']} after closure revision {revision['infrastructure_revision']}.")

            # Advance in legal 30 s slices until backend state reports arrival.
            arrivals = 0
            for index in range(20):
                current_clock = self.response(client.get(f"/api/v1/scenarios/{sid}/missions/clock"), 200, "mission clock before advance")
                movement = self.response(client.post(f"/api/v1/scenarios/{sid}/missions/clock/advance", headers={"Idempotency-Key":f"rc1-demo-a-arrival-{index}"}, json={"expected_version":current_clock["version"],"expected_state_version":state["state_version"],"seconds":30}), 200, "mission movement")
                live = next(row for row in movement["missions"] if row["mission_id"] == mission["mission_id"])
                expected_position = main.missions.get(mission["mission_id"]).position
                self.require(all(abs(float(live["position"][key])-float(expected_position[key])) < 1e-6 for key in ("x_m","y_m","elevation_m")), "API movement position disagrees with persisted mission state.")
                if live["status"] == "arrived":
                    arrivals += 1
                    break
            self.require(arrivals == 1, "Mission did not arrive within the bounded synthetic clock window.")
            self.report["missions"]["demo_a"].update({"arrival_position":live["position"],"arrival_distance_m":live["traversed_distance_m"],"approved_route_revision":live["route_revision"]})
            self.check("arrival_and_route_geometry_consistency", f"Mission arrived at {live['traversed_distance_m']:.1f} m on approved route revision {live['route_revision']}.")

            complete = self.response(client.post(f"/api/v1/missions/{mission['mission_id']}/complete", headers={"Idempotency-Key":"rc1-demo-a-complete"}, json={"expected_version":live["mission_version"]}), 200, "explicit completion")
            self.require(complete["status"] == "completed", "Mission completion was not an explicit successful action.")
            still_reserved = self.response(client.get(f"/api/v1/scenarios/{sid}/missions/units"), 200, "resources before return")
            unit = next(row for row in still_reserved if row["unit_id"] == mission["unit_id"])
            self.require(unit["status"] != "available", "Arrival/completion incorrectly released the unit automatically.")
            restored = self.response(client.post(f"/api/v1/missions/{mission['mission_id']}/restore", headers={"Idempotency-Key":"rc1-demo-a-return"}, json={"expected_version":complete["mission_version"]}), 200, "explicit return to service")
            self.require(restored["status"] == "completed", "Explicit restore changed historical mission completion.")
            units_after = self.response(client.get(f"/api/v1/scenarios/{sid}/missions/units"), 200, "resources after return")
            self.require(next(row for row in units_after if row["unit_id"] == mission["unit_id"])["status"] == "available", "Explicit return-to-service did not restore the unit.")
            replay = self.response(client.get(f"/api/v1/missions/{mission['mission_id']}/replay"), 200, "mission replay")
            self.require(replay["read_only"] is True and len(replay["events"]) >= 5, "Mission event replay was not durable/read-only.")
            self.report["missions"]["demo_a"].update({"completion_status":restored["status"],"resource_after_return":"available","event_count":len(replay["events"])})
            self.check("explicit_completion_resource_return_and_replay", f"Explicit completion and return-to-service restored {mission['unit_id']}; {len(replay['events'])} durable read-only mission events.")

            # Demo B is distinct: physically affected targets, but no traversable ground corridors.
            created = self.response(client.post("/api/v1/scenarios", headers={"Idempotency-Key":"rc1-demo-b-create"}, json={"name":"RC1 Demo B · No supported ground route","seed":2026,"preset":"mild"}), 201, "Demo B create")
            state_b = created["state"]
            sid_b = state_b["id"]
            state_b = self.response(client.patch(f"/api/v1/scenarios/{sid_b}/parameters", json={"rainfall_mm_h":30,"river_level_m":0.6,"drainage_effectiveness":0.2,"expected_version":state_b["state_version"]}), 200, "Demo B forcing")["state"]
            state_b = self.response(client.post(f"/api/v1/scenarios/{sid_b}/advance", json={"steps":6,"single_step":True,"expected_version":state_b["state_version"]}), 200, "Demo B progression")["state"]
            for index, road in enumerate(generate_city(2026).roads):
                self.response(client.post(f"/api/v1/scenarios/{sid_b}/road-closures", json={"road_id":road.id,"reason":"RC1 Demo B all-corridor closure"}), 200, f"Demo B close corridor {index+1}")
            plan_b = self.response(client.post(f"/api/v1/scenarios/{sid_b}/rescue-plans"), 201, "Demo B plan")
            self.require(state_b["affected_buildings"] > 0 and not plan_b["missions"], "Demo B did not preserve impacted targets and zero supported assignments.")
            self.require(plan_b["unreachable"] and all(item["reason"] for item in plan_b["unreachable"]), "Demo B did not explain why routes are unavailable.")
            missions_b = self.response(client.get(f"/api/v1/scenarios/{sid_b}/missions?epoch={state_b['epoch']}"), 200, "Demo B mission records")
            self.require(not missions_b, "Demo B created an unsupported mission despite all modeled corridors being closed.")
            self.report["scenarios"]["demo_b"] = {"id":sid_b,"seed":2026,"rainfall_mm_h":30,"river_level_m":0.6,"drainage_effectiveness":0.2,"ticks":6,"affected_buildings":state_b["affected_buildings"],"closed_corridors":len(generate_city(2026).roads),"assignments":len(plan_b["missions"]),"mission_records":len(missions_b),"unreachable_count":len(plan_b["unreachable"]),"sample_reason":plan_b["unreachable"][0]["reason"]}
            self.check("demo_b_honest_unreachable", f"All {len(generate_city(2026).roads)} modeled roads closed; {state_b['affected_buildings']} buildings exposed; 0 assignments, 0 mission rows; reason: {plan_b['unreachable'][0]['reason']}")

            before = self.response(client.get(f"/api/v1/scenarios/{sid_b}/events"), 200, "Demo B event evidence")
            self.report["evidence"] = {"demo_a_plan_id":plan["plan_id"],"demo_a_mission_id":mission["mission_id"],"demo_a_event_count":len(replay["events"]),"demo_b_event_count":len(before),"all_mutations_disposable":True}


def worker(db_path: Path):
    os.environ["RESQ_DB_PATH"] = str(db_path.resolve())
    import logging
    logging.disable(logging.INFO)
    started = time.perf_counter()
    runner = Runner()
    try:
        runner.run()
        runner.report["status"] = "PASS"
    except Exception as error:
        runner.report["status"] = "FAIL"
        runner.report["error"] = {"stage":runner.report["checks"][-1]["name"] if runner.report["checks"] else "startup", "category":type(error).__name__,"message":str(error)}
    runner.report["elapsed_ms"] = round((time.perf_counter()-started)*1000,3)
    for name, values in runner.report["timings_ms"].items():
        if values:
            ordered=sorted(values)
            runner.report["timings_ms"][name]={"samples":len(values),"median_ms":round(statistics.median(values),3),"p95_ms":round(ordered[min(len(ordered)-1,int(len(ordered)*.95))],3)}
    print(json.dumps(runner.report))
    return 0 if runner.report["status"] == "PASS" else 1


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/part14-rc1-acceptance"))
    parser.add_argument("--worker-db", type=Path, help=argparse.SUPPRESS)
    args=parser.parse_args()
    if args.worker_db:
        return worker(args.worker_db)
    output=args.output_dir.resolve()
    output.mkdir(parents=True,exist_ok=True)
    started=time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="resq-rc1-acceptance-") as folder:
        child=subprocess.run([sys.executable,str(Path(__file__).resolve()),"--worker-db",str(Path(folder)/"operational.sqlite3")],capture_output=True,text=True,check=False)
        try:
            report=json.loads(child.stdout)
        except json.JSONDecodeError:
            report={"status":"FAIL","checks":[],"error":{"stage":"worker startup","category":"invalid_worker_output","message":(child.stderr or child.stdout)[-2500:]}}
    report["total_elapsed_ms"]=round((time.perf_counter()-started)*1000,3)
    report["environment"]["database_lifecycle"]="temporary directory deleted after acceptance"
    (output/"acceptance-report.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    lines=["# RESQ-AI RC1 Demo Acceptance","",f"**Status:** {report['status']}",f"**Elapsed:** {report['total_elapsed_ms']:.1f} ms","", "## Scenarios and missions", "", f"- Demo A: `{report.get('scenarios',{}).get('demo_a',{}).get('id','not created')}`", f"- Demo A mission: `{report.get('missions',{}).get('demo_a',{}).get('id','not created')}`", f"- Demo B: `{report.get('scenarios',{}).get('demo_b',{}).get('id','not created')}`", "", "## Assertions", ""]
    lines += [f"- **{row['status']}** `{row['name']}` — {row['detail']}" for row in report.get("checks",[])]
    if report.get("error"):
        lines += ["",f"## Failure at {report['error']['stage']}","",f"{report['error']['category']}: {report['error']['message']}"]
    lines += ["","Machine-readable output: `acceptance-report.json`.",""]
    (output/"acceptance-report.md").write_text("\n".join(lines),encoding="utf-8")
    print(json.dumps({"status":report["status"],"elapsed_ms":report["total_elapsed_ms"],"checks":len(report.get("checks",[])),"error":report.get("error"),"reports":[str(output/"acceptance-report.json"),str(output/"acceptance-report.md")]},indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
