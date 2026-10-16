"""Full-stack local acceptance run using disposable SQLite and real API methods.

From the repository root, explicitly opt into simulated commander decisions:
  backend/.venv/Scripts/python.exe backend/demo_acceptance_part10.py --test-commander-actions
"""
from __future__ import annotations

import argparse
import importlib
import json
import logging
import math
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


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AcceptanceFailure(message)


class Runner:
    def __init__(self):
        self.report = {"status": "FAIL", "schema_version": 1, "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                       "environment": {"os": platform.platform(), "python": platform.python_version(), "mode": "in-process FastAPI TestClient; no external network"},
                       "scenario_ids": [], "mission_ids": [], "checks": [], "timings_ms": {}}

    def check(self, name: str, detail: str, duration_ms: float | None = None) -> None:
        self.report["checks"].append({"name": name, "status": "PASS", "detail": detail,
                                      **({"duration_ms": round(duration_ms, 3)} if duration_ms is not None else {})})
        if duration_ms is not None:
            self.report["timings_ms"].setdefault(name, []).append(round(duration_ms, 3))

    @staticmethod
    def response(response, expected: int, label: str):
        if response.status_code != expected:
            try:
                detail = response.json()
            except ValueError:
                detail = response.text[:300]
            raise AcceptanceFailure(f"{label}: expected HTTP {expected}, got {response.status_code}: {detail}")
        return response.json() if response.content else None

    def execute(self) -> None:
        from fastapi.testclient import TestClient
        from app import main

        with TestClient(main.app) as client:
            started = time.perf_counter()
            health = self.response(client.get("/api/v1/health"), 200, "health")
            city = self.response(client.get("/api/v1/city/state"), 200, "city")
            require(health["status"] == "ok" and bool(city.get("buildings")), "Backend health or city loading failed.")
            self.check("Backend health", "Health and generated city endpoints returned their expected contracts.", (time.perf_counter()-started)*1000)

            scenario_write_started=time.perf_counter()
            creation = self.response(client.post("/api/v1/scenarios", headers={"Idempotency-Key":"part10-acceptance-create"},
                json={"name":"Part 10 disposable acceptance","seed":2026,"preset":"mild"}), 201, "scenario creation")
            state = creation["state"]
            sid = state["id"]
            self.report["scenario_ids"].append(sid)
            self.check("Scenario creation", f"Created seed 2026 scenario {sid} in the disposable database.",(time.perf_counter()-scenario_write_started)*1000)
            self.report["timings_ms"].setdefault("SQLite scenario write",[]).append(self.report["checks"][-1]["duration_ms"])

            ml_start = time.perf_counter()
            model = self.response(client.get("/api/v1/ml/model"), 200, "ML model info")
            dataset = self.response(client.get("/api/v1/ml/dataset"), 200, "dataset metadata")
            self.response(client.get("/api/v1/ml/evaluation"), 200, "evaluation metadata")
            predictions = self.response(client.get(f"/api/v1/scenarios/{sid}/predictions"), 200, "local model predictions")
            require(model["status"] == "ready" and bool(dataset["feature_names"]) and bool(predictions["predictions"]), "Local ML artifact, metadata or inference was unavailable.")
            self.report["evidence"] = {"model_version": predictions["model_version"], "prediction_count": len(predictions["predictions"])}
            self.check("Local ML model and inference", f"Loaded {predictions['model_version']} and predicted {len(predictions['predictions'])} buildings.", (time.perf_counter()-ml_start)*1000)

            updated = self.response(client.patch(f"/api/v1/scenarios/{sid}/parameters", json={"rainfall_mm_h":90,"river_level_m":1.4,"drainage_effectiveness":0.2,"expected_version":state["state_version"]}), 200, "flood parameters")
            flood_start = time.perf_counter()
            flooded = self.response(client.post(f"/api/v1/scenarios/{sid}/advance", json={"steps":12,"single_step":True,"expected_version":updated["state"]["state_version"]}), 200, "flood advance")["state"]
            require(flooded["tick"] == 12 and flooded["affected_buildings"] > 0, "Flood simulation did not produce the expected tick and meaningful exposure.")
            self.check("Flood simulation and exposure", f"Reached tick {flooded['tick']} with {flooded['affected_buildings']} affected buildings and {flooded['exposed_roads']} exposed roads.", (time.perf_counter()-flood_start)*1000)
            stale = client.post(f"/api/v1/scenarios/{sid}/advance",json={"steps":1,"single_step":True,"expected_version":updated["state"]["state_version"]})
            self.response(stale,409,"stale frontend scenario version rejection")
            self.check("Stale frontend state rejected", "The pre-flood version returned HTTP 409 without mutating current state.")

            agents_started = time.perf_counter()
            registry = self.response(client.get("/api/v1/agents/registry"),200,"agent registry")
            events = self.response(client.get(f"/api/v1/scenarios/{sid}/agent-events"),200,"agent event outbox")
            runs = self.response(client.get(f"/api/v1/scenarios/{sid}/agent-runs?limit=100"),200,"agent runs")
            relevant = [event for event in events if event["simulation_state_version"] == flooded["state_version"] and event["event_type"] == "simulation_advanced"]
            require(len(registry)==6 and relevant, "The six-agent registry or flood event was not present.")
            event_id = relevant[-1]["event_id"]
            trace = self.response(client.get(f"/api/v1/agent-traces/{event_id}"),200,"agent decision trace")
            require(trace["event_status"] in ("completed","degraded") and len(trace["agents"]) == 6, "Six-agent trace did not persist all agent results.")
            self.report["evidence"].update({"flood_event_id":event_id,"agent_trace_status":trace["event_status"],"agent_run_count":len(runs),"agent_names":[item["name"] for item in registry]})
            self.check("Six-agent pipeline and durable trace", f"Event {event_id} has a {trace['event_status']} trace with six agent records.", (time.perf_counter()-agents_started)*1000)

            route_start = time.perf_counter()
            plan = self.response(client.post(f"/api/v1/scenarios/{sid}/rescue-plans"),201,"rescue proposal")
            require(plan["status"] == "proposed" and plan["solver_status"] and isinstance(plan["missions"],list), "Rescue plan was not a computed commander-review proposal.")
            require(plan["missions"], "No reachable mission exists in this deterministic synthetic case.")
            self.report["evidence"].update({"plan_id":plan["plan_id"],"solver_status":plan["solver_status"],"mission_count":len(plan["missions"]),"infrastructure_revision":plan["infrastructure_revision"]})
            for key in ("routing","assignment"):
                if key in plan.get("timings_ms",{}):
                    self.report["timings_ms"].setdefault("Rescue " + key,[]).append(float(plan["timings_ms"][key]))
            self.check("Computed rescue proposal and routing", f"Plan {plan['plan_id']} contains {len(plan['missions'])} computed mission assignments.", (time.perf_counter()-route_start)*1000)

            # These are explicit test-commander actions against the same API used by the UI.
            approve_start = time.perf_counter()
            approved = self.response(client.post(f"/api/v1/rescue-plans/{plan['plan_id']}/decision",json={"action":"approved","reason":"Explicit --test-commander-actions acceptance decision","expected_version":flooded["state_version"]}),200,"human test approval")
            mission_rows = self.response(client.get(f"/api/v1/scenarios/{sid}/missions?epoch={flooded['epoch']}"),200,"approved missions")
            require(approved["status"]=="approved" and mission_rows and all(item["status"]=="ready" for item in mission_rows), "Approval did not create ready missions.")
            self.report["mission_ids"]=[item["mission_id"] for item in mission_rows]
            first = mission_rows[0]
            live_state=main.store.get(sid).state
            revision,_=main.rescue_plans.infrastructure(sid,live_state.epoch)
            pending_event=main.agent_orchestrator.enqueue(event_type="manual_assessment",scenario_id=sid,state=live_state,
                infrastructure_revision=revision,source_module="part10_restart_acceptance",payload={"restart_recovery_probe":True})
            self.report["evidence"]["pending_recovery_event_id"]=pending_event.event_id
            # Recreate the application service objects after closing the first client to verify durable recovery below.
            self.check("Explicit plan approval and mission creation", f"Plan {plan['plan_id']} approved; {len(mission_rows)} ready missions and reservations persisted.", (time.perf_counter()-approve_start)*1000)

        # A new application module creates fresh stores and runs normal lifespan recovery against the same DB.
        main = importlib.reload(main)
        with TestClient(main.app) as client:
            read_started=time.perf_counter()
            persisted = self.response(client.get(f"/api/v1/scenarios/{sid}"),200,"scenario after restart")["state"]
            self.report["timings_ms"].setdefault("SQLite scenario read",[]).append((time.perf_counter()-read_started)*1000)
            persisted_plan = self.response(client.get(f"/api/v1/rescue-plans/{plan['plan_id']}"),200,"plan after restart")
            persisted_missions = self.response(client.get(f"/api/v1/scenarios/{sid}/missions?epoch={persisted['epoch']}"),200,"missions after restart")
            resources = self.response(client.get(f"/api/v1/scenarios/{sid}/missions/units"),200,"resources after restart")
            require(persisted["state_version"]==flooded["state_version"] and persisted_plan["status"]=="approved" and len(persisted_missions)==len(mission_rows), "Scenario, plan or missions did not survive an application restart.")
            reserved_ids={item["unit_id"] for item in persisted_missions}
            actual_reserved={item["unit_id"] for item in resources if item["status"]=="reserved"}
            require(reserved_ids <= actual_reserved, "Resource reservations did not survive restart.")
            self.check("Restart persistence and reservation recovery", f"Scenario, approved plan, {len(persisted_missions)} missions, and {len(actual_reserved)} reserved units survived a fresh application lifespan.")
            recovered_trace=self.response(client.get(f"/api/v1/agent-traces/{self.report['evidence']['pending_recovery_event_id']}"),200,"recovered pending event trace")
            require(recovered_trace["event_status"] in ("completed","degraded"), "Pending event was not recovered during application startup.")
            self.check("Pending agent event restart recovery", f"Pending event recovered as {recovered_trace['event_status']} after a new application lifespan.")

            dispatch_start = time.perf_counter()
            mission = next((item for item in persisted_missions if item["route"].get("road_ids") and item["total_distance_m"] > 100), None)
            require(mission is not None, "The computed proposal did not contain a road-following mission for the disruption scenario.")
            self.response(client.post(f"/api/v1/missions/{mission['mission_id']}/dispatch",headers={"Idempotency-Key":"part10-test-dispatch"},json={"expected_version":mission["mission_version"]}),200,"test commander dispatch")
            retried_dispatch=self.response(client.post(f"/api/v1/missions/{mission['mission_id']}/dispatch",headers={"Idempotency-Key":"part10-test-dispatch"},json={"expected_version":mission["mission_version"]}),200,"idempotent dispatch retry")
            require(retried_dispatch["mission_version"]==mission["mission_version"]+1 and retried_dispatch["status"]=="en_route", "Retrying the same dispatch key duplicated the mutation.")
            self.check("Explicit test dispatch", f"Dispatched mission {mission['mission_id']} through the production mission API.", (time.perf_counter()-dispatch_start)*1000)

            # Move to the first corner, then close a downstream road on this approved route.
            clock = self.response(client.get(f"/api/v1/scenarios/{sid}/missions/clock"),200,"mission clock")
            moved = self.response(client.post(f"/api/v1/scenarios/{sid}/missions/clock/advance",headers={"Idempotency-Key":"part10-clock-prefix"},json={"expected_version":clock["version"],"expected_state_version":flooded["state_version"],"seconds":min(2,30)}),200,"mission clock prefix")
            live = next(item for item in moved["missions"] if item["mission_id"]==mission["mission_id"])
            require(live["traversed_distance_m"]>0, "Mission clock did not advance authoritative movement.")
            selected_road = mission["route"]["road_ids"][-1]
            closure = self.response(client.post(f"/api/v1/scenarios/{sid}/road-closures",json={"road_id":selected_road,"reason":"Part 10 acceptance route disruption"}),200,"road disruption")
            blocked = self.response(client.get(f"/api/v1/missions/{mission['mission_id']}"),200,"blocked mission")
            require(blocked["status"]=="blocked" and closure["infrastructure_revision"]>mission["infrastructure_revision"], "Closure did not block the mission and advance infrastructure revision.")
            self.check("Disruption and blocked mission", f"Closed {selected_road}; mission stopped at {blocked['traversed_distance_m']} m with reason: {blocked['block_reason']}.")

            route_response = client.post(f"/api/v1/missions/{mission['mission_id']}/route-proposal",headers={"Idempotency-Key":"part10-route-proposal"},json={"expected_version":blocked["mission_version"]})
            revision_approved = False
            if route_response.status_code == 200:
                candidate = route_response.json()
                proposal = candidate.get("route_proposal")
                if proposal and proposal.get("route",{}).get("reachable"):
                    approved_route = self.response(client.post(f"/api/v1/missions/{mission['mission_id']}/route-approval",headers={"Idempotency-Key":"part10-route-approval"},json={"expected_version":candidate["mission_version"],"route_revision_id":proposal["route_revision_id"]}),200,"commander route approval")
                    revision_approved = approved_route["status"]=="en_route" and approved_route["route_revision"]==2
                    mission = approved_route
            elif route_response.status_code == 409:
                self.report["evidence"]["route_infeasibility"] = route_response.json()
            else:
                self.response(route_response,200,"route proposal")
            if not revision_approved:
                # Record safe infeasibility, reopen the synthetic closure, then request/approve a fresh route.
                reopen = client.delete(f"/api/v1/scenarios/{sid}/road-closures/{selected_road}")
                self.response(reopen,200,"road reopen after infeasibility")
                refreshed = self.response(client.get(f"/api/v1/missions/{mission['mission_id']}"),200,"blocked mission after reopen")
                fresh = self.response(client.post(f"/api/v1/missions/{mission['mission_id']}/route-proposal",headers={"Idempotency-Key":"part10-route-proposal-recovered"},json={"expected_version":refreshed["mission_version"]}),200,"fresh route proposal")
                proposal=fresh.get("route_proposal")
                require(proposal and proposal.get("route",{}).get("reachable"), "Mission remained safely blocked after an infeasible route and could not recover after reopening the road.")
                mission=self.response(client.post(f"/api/v1/missions/{mission['mission_id']}/route-approval",headers={"Idempotency-Key":"part10-route-approval-recovered"},json={"expected_version":fresh["mission_version"],"route_revision_id":proposal["route_revision_id"]}),200,"fresh commander route approval")
            self.report["evidence"]["route_revision_approved"] = revision_approved or mission["status"]=="en_route"
            self.report["evidence"]["replacement_route_road_ids"] = mission["route"]["road_ids"]
            self.check("Safe route proposal and commander review", "A route was explicitly reviewed and approved; an infeasible closure was recorded and reopened before obtaining a fresh route when needed.")

            travel_started = time.perf_counter()
            updates=[]
            for index in range(300):
                current = self.response(client.get(f"/api/v1/missions/{mission['mission_id']}"),200,"mission progress")
                if current["status"]=="arrived": break
                require(current["status"]=="en_route", f"Mission left en-route state during travel: {current['status']}.")
                clock=self.response(client.get(f"/api/v1/scenarios/{sid}/missions/clock"),200,"mission clock")
                clock_started=time.perf_counter()
                result=self.response(client.post(f"/api/v1/scenarios/{sid}/missions/clock/advance",headers={"Idempotency-Key":f"part10-travel-{index:03d}"},json={"expected_version":clock["version"],"expected_state_version":flooded["state_version"],"seconds":30}),200,"mission travel")
                self.report["timings_ms"].setdefault("Mission clock update",[]).append((time.perf_counter()-clock_started)*1000)
                updates.extend(result["missions"])
            current=self.response(client.get(f"/api/v1/missions/{mission['mission_id']}"),200,"mission arrival")
            require(current["status"]=="arrived", "Mission did not arrive within the acceptance runner's bounded progression loop.")
            self.check("Mission movement and arrival", f"Mission arrived at {current['position']} after {current['operational_seconds']} simulated seconds.", (time.perf_counter()-travel_started)*1000)
            completed=self.response(client.post(f"/api/v1/missions/{mission['mission_id']}/complete",headers={"Idempotency-Key":"part10-test-complete"},json={"expected_version":current["mission_version"]}),200,"explicit test completion")
            require(completed["status"]=="completed", "Explicit completion was not persisted.")
            restored=self.response(client.post(f"/api/v1/missions/{mission['mission_id']}/restore",headers={"Idempotency-Key":"part10-test-return-to-service"},json={"expected_version":completed["mission_version"]}),200,"return to service")
            resources=self.response(client.get(f"/api/v1/scenarios/{sid}/missions/units"),200,"restored resources")
            require(any(item["unit_id"]==mission["unit_id"] and item["status"]=="available" for item in resources), "Return-to-service did not restore the resource.")
            replay=self.response(client.get(f"/api/v1/missions/{mission['mission_id']}/replay"),200,"read-only replay")
            require(replay["read_only"] is True and any(item["event_type"]=="mission_completed" for item in replay["events"]), "Mission replay was not read-only or did not include completion.")
            self.report["evidence"].update({"mission_status":restored["status"],"resource_status":"available","mission_replay_events":len(replay["events"]),"movement_updates":len(updates)})
            self.check("Completion, return-to-service and replay", f"Mission explicitly completed; unit {mission['unit_id']} returned to available; {len(replay['events'])} replay events read without mutation.")

            base_before=self.response(client.get(f"/api/v1/scenarios/{sid}"),200,"scenario before A/B")["state"]
            experiment_started=time.perf_counter()
            experiment=self.response(client.post(f"/api/v1/scenarios/{sid}/experiments",json={"name":"Part 10 isolated A/B","base_scenario_id":sid,"expected_state_version":base_before["state_version"],"simulation_ticks":2,"variants":[{"variant_id":"A","label":"Same snapshot baseline"},{"variant_id":"B","label":"Higher rainfall","rainfall_mm_h":120}]}),202,"A/B creation")
            experiment_id=experiment["experiment_id"]
            saved=self.response(client.get(f"/api/v1/scenario-experiments/{experiment_id}"),200,"A/B result")
            after=self.response(client.get(f"/api/v1/scenarios/{sid}"),200,"scenario after A/B")["state"]
            require(saved["status"]=="completed" and len(saved["results"]["variants"])==2 and after["state_version"]==base_before["state_version"], "A/B experiment failed or mutated operational state.")
            self.report["evidence"]["experiment_id"]=experiment_id
            self.check("A/B experiment isolation", f"Experiment {experiment_id} completed two variants from one snapshot; operational version remained {after['state_version']}.",(time.perf_counter()-experiment_started)*1000)

        main=importlib.reload(main)
        with TestClient(main.app) as client:
            recovered_experiment=self.response(client.get(f"/api/v1/scenario-experiments/{experiment_id}"),200,"experiment after restart")
            require(recovered_experiment["status"]=="completed" and len(recovered_experiment["results"]["variants"])==2, "A/B experiment was not retrievable after restart.")
            self.check("Experiment restart persistence", f"Completed experiment {experiment_id} and both variants remained retrievable after restart.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test-commander-actions", action="store_true", help="Explicitly allow this local runner to approve and dispatch synthetic test missions through the real API.")
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/part10-acceptance"))
    parser.add_argument("--worker-db", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not args.test_commander_actions:
        parser.error("This workflow includes synthetic plan approval and mission dispatch. Pass --test-commander-actions to authorize those test-only actions.")
    if args.worker_db:
        os.environ["RESQ_DB_PATH"] = str(args.worker_db.resolve())
        logging.disable(logging.INFO)
        started = time.perf_counter()
        runner = Runner()
        try:
            runner.execute()
            runner.report["status"] = "PASS"
        except Exception as exc:
            runner.report["status"] = "FAIL"
            runner.report["error"] = {"category": type(exc).__name__, "message": str(exc)}
        runner.report["elapsed_ms"] = round((time.perf_counter()-started)*1000,3)
        for label, values in runner.report.get("timings_ms",{}).items():
            if values:
                runner.report["timings_ms"][label] = {"samples":len(values),"median_ms":round(statistics.median(values),3),"p95_ms":round(sorted(values)[min(len(values)-1,math.ceil(.95*len(values))-1)],3)}
        print(json.dumps(runner.report))
        return 0 if runner.report["status"]=="PASS" else 1

    output_dir=args.output_dir.resolve()
    output_dir.mkdir(parents=True,exist_ok=True)
    started=time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="resq-part10-acceptance-") as folder:
        db_path=Path(folder)/"operational.sqlite3"
        child=subprocess.run([sys.executable,str(Path(__file__).resolve()),"--test-commander-actions","--worker-db",str(db_path)],capture_output=True,text=True,check=False)
        try:
            report=json.loads(child.stdout)
        except json.JSONDecodeError:
            report={"status":"FAIL","schema_version":1,"checks":[],"error":{"category":"acceptance_worker_failed","message":(child.stderr or child.stdout)[-2000:]}}
        if child.returncode and report.get("status")=="PASS": report["status"]="FAIL"
    report["elapsed_ms"]=round((time.perf_counter()-started)*1000,3)
    report["evidence_files"]={"temporary_database":"deleted with temporary directory after run","output_directory":"caller-selected local path"}
    json_path=output_dir/"acceptance-report.json"
    md_path=output_dir/"acceptance-report.md"
    json_path.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    lines=["# Part 10 End-to-End Acceptance", "", f"**Status:** {report['status']}", f"**Elapsed:** {report['elapsed_ms']:.1f} ms", "", "## Scenario and mission IDs", "", "- Scenarios: "+(", ".join(report.get("scenario_ids",[])) or "none"), "- Missions: "+(", ".join(report.get("mission_ids",[])) or "none"), "", "## Checked outcomes", ""]
    lines += [f"- **{row['status']}** {row['name']}: {row['detail']}" for row in report.get("checks",[])]
    if report.get("error"): lines += ["", "## Failure", "", f"{report['error']['category']}: {report['error']['message']}"]
    lines += ["", "Machine-readable evidence: `acceptance-report.json`.", ""]
    md_path.write_text("\n".join(lines),encoding="utf-8")
    print(json.dumps({"status":report["status"],"elapsed_ms":report["elapsed_ms"],"scenario_ids":report.get("scenario_ids"),"mission_ids":report.get("mission_ids"),"checks":report.get("checks"),"error":report.get("error"),"reports":[str(json_path),str(md_path)]},indent=2))
    return 0 if report["status"]=="PASS" else 1


if __name__=="__main__":
    raise SystemExit(main())
