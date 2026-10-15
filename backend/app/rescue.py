"""Deterministic, local rescue planning over the fictional city road network."""
from __future__ import annotations

import json
import math
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Literal

import networkx as nx
import numpy as np
from scipy.optimize import linear_sum_assignment
from pydantic import BaseModel, ConfigDict, Field

from .city_service import generate_city
from .schemas import ScenarioState


class RescuePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan_id: str
    scenario_id: str
    scenario_version: int
    scenario_epoch: int = 0
    infrastructure_revision: int = 0
    simulation_tick: int
    generated_at: str
    status: Literal["proposed", "approved", "rejected", "superseded"] = "proposed"
    priorities: list[dict]
    missions: list[dict]
    available_assignments: list[dict]
    unreachable: list[dict]
    comparison: dict
    solver_status: str
    objective: str
    explanation: str


def _xy(p):
    return (float(p.x_m), float(p.y_m))


def build_road_graph(city, state: ScenarioState | None = None, manual_closures=()):
    """Split corridors at all geometric crossings; bridges occupy explicit 46m spans."""
    g = nx.Graph()
    bridge_by_road = {b.road_id: b for b in city.bridges}
    road_status = {i.entity_id: i for i in state.impacts.roads} if state else {}
    bridge_status = {i.entity_id: i for i in state.impacts.bridges} if state else {}
    closures = set(manual_closures)
    corridors = []
    for road in city.roads:
        a, b = _xy(road.start), _xy(road.end)
        points = [(0.0, a), (1.0, b)]
        for other in city.roads:
            if other.id == road.id:
                continue
            c, d = _xy(other.start), _xy(other.end)
            den = (b[0]-a[0])*(d[1]-c[1])-(b[1]-a[1])*(d[0]-c[0])
            if abs(den) < 1e-9:
                continue
            t = ((c[0]-a[0])*(d[1]-c[1])-(c[1]-a[1])*(d[0]-c[0]))/den
            u = ((c[0]-a[0])*(b[1]-a[1])-(c[1]-a[1])*(b[0]-a[0]))/den
            if -1e-9 <= t <= 1+1e-9 and -1e-9 <= u <= 1+1e-9:
                points.append((max(0.0, min(1.0, t)), (a[0]+t*(b[0]-a[0]), a[1]+t*(b[1]-a[1]))))
        bridge = bridge_by_road.get(road.id)
        if bridge:
            half = bridge.length_m / 2
            t0 = (bridge.position.y_m-half-a[1])/(b[1]-a[1]) if abs(b[1]-a[1]) > 1e-9 else (bridge.position.x_m-half-a[0])/(b[0]-a[0])
            t1 = (bridge.position.y_m+half-a[1])/(b[1]-a[1]) if abs(b[1]-a[1]) > 1e-9 else (bridge.position.x_m+half-a[0])/(b[0]-a[0])
            points.extend([(t0, (a[0]+t0*(b[0]-a[0]), a[1]+t0*(b[1]-a[1]))), (t1, (a[0]+t1*(b[0]-a[0]), a[1]+t1*(b[1]-a[1])))])
        corridors.append((road, sorted(points, key=lambda x: x[0])))
    for road, pts in corridors:
        dedup = []
        for t, p in pts:
            if not dedup or abs(t-dedup[-1][0]) > 1e-8:
                dedup.append((t,p))
        for t,p in dedup:
            node = f"j:{p[0]:.3f}:{p[1]:.3f}"
            g.add_node(node, xy=p, kind="intersection")
        for (t0,p0),(t1,p1) in zip(dedup,dedup[1:]):
            bridge = bridge_by_road.get(road.id)
            is_bridge = bool(bridge and abs((p0[0]+p1[0])/2-bridge.position.x_m) < .01 and abs((p0[1]+p1[1])/2-bridge.position.y_m) < bridge.length_m/2+0.01)
            status = "open"
            depth = 0.0
            if road.id in road_status:
                status = road_status[road.id].status or "open"
                depth = road_status[road.id].max_depth_m
            if is_bridge and bridge.id in bridge_status:
                status = bridge_status[bridge.id].status or status
                if status == "open":
                    depth = 0.0
            edge_id = f"{road.id}:{'bridge' if is_bridge else 'segment'}:{t0:.4f}-{t1:.4f}"
            length = math.dist(p0,p1)
            g.add_edge(f"j:{p0[0]:.3f}:{p0[1]:.3f}", f"j:{p1[0]:.3f}:{p1[1]:.3f}",
                       edge_id=edge_id, road_id=road.id, bridge_id=bridge.id if is_bridge else None,
                       length_m=length, xy=[p0,p1], status="manually_blocked" if road.id in closures else status,
                       depth_m=depth, speed_kmh=24.0 if is_bridge else 30.0)
    return g


def _nearest_node(g, position):
    x,y = _xy(position)
    return min(g.nodes, key=lambda n: (math.dist(g.nodes[n]["xy"], (x,y)), n))


def route(g, start_position, destination_position, unit_type="ambulance"):
    if unit_type == "boat":
        return {"reachable": False, "reason": "Boat routing is unsupported: no waterway navigation or docking graph exists."}
    start_road, end_road = _nearest_node(g, start_position), _nearest_node(g, destination_position)
    start, end = "access:unit", "access:destination"
    sx, sy = _xy(start_position); ex, ey = _xy(destination_position)
    if math.dist((sx,sy),g.nodes[start_road]["xy"]) > 90 or math.dist((ex,ey),g.nodes[end_road]["xy"]) > 90:
        return {"reachable": False, "reason": "Unit or destination is beyond the documented 90 m road-access spur limit."}
    allowed = nx.Graph()
    allowed.add_nodes_from(g.nodes(data=True))
    for a,b,data in g.edges(data=True):
        if data["status"] in ("closed", "flooded", "manually_blocked"):
            continue
        if unit_type == "ambulance" and data["depth_m"] > .15:
            continue
        if unit_type == "rescue_team" and data["depth_m"] > .30:
            continue
        penalty = 1.0 + data["depth_m"] * 4 + (0.4 if data["status"] == "caution" else 0)
        speed = data["speed_kmh"] * (0.55 if data["status"] == "caution" else 1.0)
        allowed.add_edge(a,b,**data, cost=data["length_m"]*penalty, speed=speed)
    allowed.add_node(start, xy=(sx,sy), kind="unit_access")
    allowed.add_node(end, xy=(ex,ey), kind="building_access")
    for node, anchor, point, identity in ((start,start_road,(sx,sy),"unit"),(end,end_road,(ex,ey),"building")):
        length=math.dist(point,g.nodes[anchor]["xy"])
        allowed.add_edge(node,anchor,edge_id=f"access:{identity}",road_id=None,bridge_id=None,length_m=length,
                         xy=[point,g.nodes[anchor]["xy"]],status="open",depth_m=0.0,speed_kmh=5.0,
                         speed=5.0,cost=length*1.5)
    try:
        nodes = nx.shortest_path(allowed, start, end, weight="cost", method="dijkstra")
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return {"reachable": False, "reason": "No route is available under this unit's accessibility policy."}
    edges = [allowed.edges[a,b] for a,b in zip(nodes,nodes[1:])]
    polyline = [allowed.nodes[n]["xy"] for n in nodes]
    length = sum(e["length_m"] for e in edges)
    seconds = sum(e["length_m"]/(e["speed"]*1000/3600) for e in edges)
    return {"reachable": True, "distance_m": round(length,1), "simulated_minutes": round(seconds/60,1),
            "road_ids": list(dict.fromkeys(e["road_id"] for e in edges if e["road_id"])), "edge_ids": [e["edge_id"] for e in edges],
            "polyline": polyline, "accessibility": "caution" if any(e["status"] == "caution" for e in edges) else "open",
            "explanation": "Dijkstra route on open segments; synthetic speed assumptions are not traffic ETAs."}


def priorities(city, state, predictions, closures=(), reserved_unit_ids=()):
    pred = {p.building_id:p for p in getattr(predictions,"predictions",[])}
    exposed = {i.entity_id:i for i in state.impacts.buildings}
    road_impacts={i.entity_id:i for i in state.impacts.roads}
    bridge_by_road={b.road_id:b for b in city.bridges}
    bridge_impacts={i.entity_id:i for i in state.impacts.bridges}
    closed=set(closures)
    reserved=set(reserved_unit_ids)
    available_units=sum(u.status=="standby" and u.type!="boat" and u.id not in reserved for u in city.rescue_units)
    eligible=[b for b in city.buildings if exposed[b.id].water_reaches_building or (pred.get(b.id) and pred[b.id].predicted_future_exposed)]
    scarcity=max(0.0,1.0-available_units/max(len(eligible),1))
    rows=[]
    for b in city.buildings:
        impact=exposed[b.id]; future=pred.get(b.id)
        if not impact.water_reaches_building and not (future and future.predicted_future_exposed):
            continue
        occ=min(b.occupants/100,1)
        depth=min(impact.max_depth_m/1.5,1)
        current=1.0 if impact.water_reaches_building else 0.0
        forecast=1.0 if future and future.predicted_future_exposed else 0.0
        x,y=_xy(b.position)
        def dist_to_road(road):
            ax,ay=_xy(road.start); bx,by=_xy(road.end); dx,dy=bx-ax,by-ay
            t=max(0,min(1,((x-ax)*dx+(y-ay)*dy)/(dx*dx+dy*dy)))
            return math.dist((x,y),(ax+t*dx,ay+t*dy))
        nearest=min(city.roads,key=dist_to_road)
        road_status="manually_blocked" if nearest.id in closed else (road_impacts[nearest.id].status or "open")
        bridge=bridge_by_road.get(nearest.id)
        if bridge and bridge_impacts[bridge.id].status=="closed":road_status="closed"
        access=1.0 if road_status in ("closed","flooded","manually_blocked") else .5 if road_status=="caution" else 0.0
        critical=1.0 if b.use=="hospital" else .5 if b.use=="shelter" else 0.0
        score=100*(.25*occ+.25*current+.15*depth+.10*forecast+.10*access+.10*scarcity+.05*critical)
        rows.append({"building_id":b.id,"name":b.name,"use":b.use,"occupants":b.occupants,"current_exposed":bool(impact.water_reaches_building),"current_depth_m":impact.max_depth_m,"predicted_future_exposed":bool(future and future.predicted_future_exposed),"uncalibrated_ml_score":future.uncalibrated_model_score if future else None,"nearest_road_accessibility":road_status,"priority_score":round(score,2),"explanation":f"Score {score:.2f}/100 = occupants {occ:.2f}×0.25 + current exposure {current:.0f}×0.25 + depth {depth:.2f}×0.15 + forecast {forecast:.0f}×0.10 + access deterioration {access:.1f}×0.10 + resource scarcity {scarcity:.2f}×0.10 + criticality {critical:.1f}×0.05."})
    return sorted(rows,key=lambda r:(-r["priority_score"],r["building_id"]))


def _assign(units, destinations, route_map, optimized=True):
    if not optimized:
        remaining=set(u["id"] for u in units); result=[]
        unit_by_id={u["id"]:u for u in units}
        for destination in destinations:
            candidates=[uid for uid in remaining if (uid,destination["building_id"]) in route_map]
            if not candidates:continue
            uid=min(candidates,key=lambda unit_id:(route_map[(unit_id,destination["building_id"])]["simulated_minutes"],unit_id))
            unit=unit_by_id[uid]; route_result=route_map[(uid,destination["building_id"]) ]
            result.append({"unit_id":uid,"destination_id":destination["building_id"],"unit_capacity":unit["capacity"],"occupants_targeted":min(unit["capacity"],destination["occupants"]),"route":route_result})
            remaining.remove(uid)
        return result
    # Rows are units; destination columns plus one zero-utility dummy per unit
    # permit any unit to remain unassigned. Stable ordering plus a tiny
    # lexicographic perturbation makes exact ties reproducible.
    units = sorted(units, key=lambda unit: unit["id"])
    destinations = sorted(destinations, key=lambda dest: dest["building_id"])
    if not units or not destinations:
        return []
    weights = np.zeros((len(units), len(destinations) + len(units)), dtype=float)
    for i, unit in enumerate(units):
        for j, destination in enumerate(destinations):
            pair = (unit["id"], destination["building_id"])
            if pair not in route_map:
                weights[i, j] = -1e9
                continue
            route_result = route_map[pair]
            coverage = min(unit["capacity"] / max(destination["occupants"], 1), 1.0)
            value = destination["priority_score"] * coverage
            if optimized:
                value -= route_result["simulated_minutes"] * 0.15
            weights[i, j] = value + 1e-12 / (1 + i * len(destinations) + j)
    rows, columns = linear_sum_assignment(weights, maximize=True)
    choices = [None] * len(units)
    for i, j in zip(rows, columns):
        if j < len(destinations) and (units[i]["id"], destinations[j]["building_id"]) in route_map:
            choices[i] = destinations[j]["building_id"]
    output=[]
    for u,did in zip(units,choices):
        if did is None:continue
        destination=next(dest for dest in destinations if dest["building_id"]==did)
        output.append({"unit_id":u["id"],"destination_id":did,"unit_capacity":u["capacity"],"occupants_targeted":min(u["capacity"],destination["occupants"]),"route":route_map[(u["id"],did)]})
    return output


def generate_plan(city, state, prediction_set, closures=(), *, infrastructure_revision=0, reserved_unit_ids=()):
    g=build_road_graph(city,state,closures)
    ranked=priorities(city,state,prediction_set,closures,reserved_unit_ids)
    reserved=set(reserved_unit_ids)
    units=[u.model_dump() for u in city.rescue_units if u.status=="standby" and u.type!="boat" and u.id not in reserved]
    route_map={}
    for u in units:
        for d in ranked:
            b=next(x for x in city.buildings if x.id==d["building_id"])
            r=route(g,u["position"],b.position,u["type"])
            if r["reachable"]: route_map[(u["id"],b.id)]=r
    optimized=_assign(units,ranked,route_map,True)
    baseline=_assign(units,ranked,route_map,False)
    reachable_destinations={destination_id for _,destination_id in route_map}
    unreachable=[{"building_id":d["building_id"],"reason":"No compatible ground unit has a route under current infrastructure conditions."} for d in ranked if d["building_id"] not in reachable_destinations]
    def metrics(missions):
        priority_by_id={d["building_id"]:d["priority_score"] for d in ranked}
        total_priority=sum(priority_by_id[m["destination_id"]]*m["occupants_targeted"]/max(next(d["occupants"] for d in ranked if d["building_id"]==m["destination_id"]),1) for m in missions)
        return {"destinations_covered":len(missions),"priority_weighted_coverage":round(total_priority,2),"total_distance_m":round(sum(m["route"]["distance_m"] for m in missions),1),"estimated_simulated_minutes":round(sum(m["route"]["simulated_minutes"] for m in missions),1),"resource_utilization":round(len(missions)/len(units),3) if units else 0,"unreachable_destinations":len(unreachable)}
    plan_id=str(uuid.uuid4())
    available=[]
    unit_by_id={u["id"]:u for u in units}
    destination_by_id={d["building_id"]:d for d in ranked}
    for (uid,did),r in route_map.items():
        u=unit_by_id[uid]; d=destination_by_id[did]
        available.append({"unit_id":uid,"destination_id":did,"unit_capacity":u["capacity"],"occupants_targeted":min(u["capacity"],d["occupants"]),"route":r})
    return RescuePlan(plan_id=plan_id,scenario_id=state.id,scenario_version=state.state_version,scenario_epoch=state.epoch,infrastructure_revision=infrastructure_revision,simulation_tick=state.tick,generated_at=datetime.now(timezone.utc).isoformat(),priorities=ranked,missions=optimized,available_assignments=available,unreachable=unreachable,comparison={"baseline":metrics(baseline),"optimized":metrics(optimized),"baseline_missions":baseline},solver_status="optimal_linear_sum_assignment",objective="Maximize sum(priority_score × capacity-covered occupant fraction - 0.15 × synthetic route minutes), with each unit assigned at most once and each destination at most once.",explanation="Assignments are recommendations; unit capacity limits the occupant count targeted in this single mission. Approval reserves assigned units until the scenario is reset into a new epoch; no mission completion or automatic release is simulated.")


class PlanStore:
    def __init__(self,path):
        self.path=str(path)
        with sqlite3.connect(self.path) as db:
            db.executescript("CREATE TABLE IF NOT EXISTS rescue_plans (plan_id TEXT PRIMARY KEY, scenario_id TEXT NOT NULL, scenario_version INTEGER NOT NULL, payload TEXT NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL); CREATE TABLE IF NOT EXISTS rescue_events (event_id INTEGER PRIMARY KEY AUTOINCREMENT, plan_id TEXT NOT NULL, event_type TEXT NOT NULL, detail TEXT NOT NULL, created_at TEXT NOT NULL); CREATE TABLE IF NOT EXISTS road_closures (scenario_id TEXT NOT NULL, epoch INTEGER NOT NULL DEFAULT 0, road_id TEXT NOT NULL, reason TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1, PRIMARY KEY(scenario_id,epoch,road_id)); CREATE TABLE IF NOT EXISTS scenario_infrastructure (scenario_id TEXT NOT NULL, epoch INTEGER NOT NULL, revision INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(scenario_id,epoch));")
            columns={row[1]:row[5] for row in db.execute("PRAGMA table_info(road_closures)")}
            if not columns.get("epoch"):
                db.execute("ALTER TABLE road_closures RENAME TO road_closures_legacy")
                db.execute("CREATE TABLE road_closures (scenario_id TEXT NOT NULL, epoch INTEGER NOT NULL, road_id TEXT NOT NULL, reason TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1, PRIMARY KEY(scenario_id,epoch,road_id))")
                db.execute("INSERT INTO road_closures(scenario_id,epoch,road_id,reason,active) SELECT c.scenario_id,s.epoch,c.road_id,c.reason,c.active FROM road_closures_legacy c JOIN scenarios s ON s.id=c.scenario_id")
                db.execute("DROP TABLE road_closures_legacy")
    def infrastructure(self,scenario_id,epoch):
        with sqlite3.connect(self.path) as db:
            db.execute("INSERT OR IGNORE INTO scenario_infrastructure VALUES(?,?,0)",(scenario_id,epoch))
            revision=db.execute("SELECT revision FROM scenario_infrastructure WHERE scenario_id=? AND epoch=?",(scenario_id,epoch)).fetchone()[0]
            closures=[r[0] for r in db.execute("SELECT road_id FROM road_closures WHERE scenario_id=? AND epoch=? AND active=1 ORDER BY road_id",(scenario_id,epoch))]
            return revision,closures
    def reserved_units(self,scenario_id,epoch):
        with sqlite3.connect(self.path) as db:
            rows=db.execute("SELECT payload FROM rescue_plans WHERE scenario_id=? AND status='approved'",(scenario_id,)).fetchall()
            plans=[RescuePlan.model_validate_json(payload) for (payload,) in rows]
            return {mission["unit_id"] for plan in plans if plan.scenario_epoch==epoch for mission in plan.missions}
    def save(self,plan):
        with sqlite3.connect(self.path) as db:
            db.execute("BEGIN IMMEDIATE")
            current=db.execute("SELECT state_version,epoch FROM scenarios WHERE id=?",(plan.scenario_id,)).fetchone()
            infra=db.execute("SELECT revision FROM scenario_infrastructure WHERE scenario_id=? AND epoch=?",(plan.scenario_id,plan.scenario_epoch)).fetchone()
            if not current or current[0]!=plan.scenario_version or current[1]!=plan.scenario_epoch or not infra or infra[0]!=plan.infrastructure_revision:
                db.rollback();raise ValueError("Scenario changed while the plan was being generated; request a fresh proposal.")
            previous=db.execute("SELECT plan_id FROM rescue_plans WHERE scenario_id=? AND status='proposed'",(plan.scenario_id,)).fetchall()
            db.execute("INSERT INTO rescue_plans VALUES(?,?,?,?,?,?)",(plan.plan_id,plan.scenario_id,plan.scenario_version,plan.model_dump_json(),plan.status,plan.generated_at))
            for (prior_id,) in previous:
                db.execute("UPDATE rescue_plans SET status='superseded' WHERE plan_id=?",(prior_id,))
                db.execute("INSERT INTO rescue_events(plan_id,event_type,detail,created_at) VALUES(?,?,?,?)",(prior_id,"superseded",json.dumps({"reason":"A newer scenario recommendation replaced this proposal."}),datetime.now(timezone.utc).isoformat()))
        return plan
    def get(self,plan_id):
        with sqlite3.connect(self.path,timeout=10,isolation_level=None) as db:
            db.execute("BEGIN IMMEDIATE")
            row=db.execute("SELECT payload,status,scenario_id,scenario_version FROM rescue_plans WHERE plan_id=?",(plan_id,)).fetchone()
            if row:
                state=db.execute("SELECT state_version,epoch FROM scenarios WHERE id=?",(row[2],)).fetchone()
                payload=RescuePlan.model_validate_json(row[0])
                infra=db.execute("SELECT revision FROM scenario_infrastructure WHERE scenario_id=? AND epoch=?",(row[2],payload.scenario_epoch)).fetchone()
                if state and row[1]=="proposed" and (state[0]!=row[3] or state[1]!=payload.scenario_epoch or not infra or infra[0]!=payload.infrastructure_revision):
                    plan=RescuePlan.model_validate_json(row[0]);plan.status="superseded"
                    db.execute("UPDATE rescue_plans SET payload=?,status='superseded' WHERE plan_id=?",(plan.model_dump_json(),plan_id))
                    db.execute("INSERT INTO rescue_events(plan_id,event_type,detail,created_at) VALUES(?,?,?,?)",(plan_id,"superseded",json.dumps({"reason":"Scenario state version changed."}),datetime.now(timezone.utc).isoformat()))
                    row=(plan.model_dump_json(),"superseded",row[2],row[3])
            db.commit()
        if not row:return None
        plan=RescuePlan.model_validate_json(row[0]); plan.status=row[1]; return plan
    def decision(self,plan_id,action,reason="",expected_version=None):
        with sqlite3.connect(self.path,timeout=10,isolation_level=None) as db:
            db.execute("BEGIN IMMEDIATE")
            row=db.execute("SELECT payload,status,scenario_id,scenario_version FROM rescue_plans WHERE plan_id=?",(plan_id,)).fetchone()
            if not row: db.rollback(); raise ValueError("Plan not found.")
            plan=RescuePlan.model_validate_json(row[0])
            current=db.execute("SELECT state_version,epoch FROM scenarios WHERE id=?",(plan.scenario_id,)).fetchone()
            infra=db.execute("SELECT revision FROM scenario_infrastructure WHERE scenario_id=? AND epoch=?",(plan.scenario_id,plan.scenario_epoch)).fetchone()
            if current is None: db.rollback(); raise ValueError("Scenario not found.")
            if current[0]!=plan.scenario_version or current[1]!=plan.scenario_epoch or expected_version!=plan.scenario_version or not infra or infra[0]!=plan.infrastructure_revision:
                plan.status="superseded"
                db.execute("UPDATE rescue_plans SET payload=?,status='superseded' WHERE plan_id=?",(plan.model_dump_json(),plan_id)); db.commit(); raise ValueError("Plan is stale and cannot be approved or rejected.")
            if row[1]!="proposed": db.rollback(); raise ValueError("Only proposed plans can receive a decision.")
            if action=="approved":
                approvals=db.execute("SELECT payload FROM rescue_plans WHERE scenario_id=? AND status='approved'",(plan.scenario_id,)).fetchall()
                approved_units={m["unit_id"] for (payload,) in approvals for m in RescuePlan.model_validate_json(payload).missions if RescuePlan.model_validate_json(payload).scenario_epoch==plan.scenario_epoch}
                overlap=approved_units & {m["unit_id"] for m in plan.missions}
                if overlap:db.rollback();raise ValueError("Approval conflicts with resources already approved in another plan: "+", ".join(sorted(overlap)))
            plan.status=action
            db.execute("UPDATE rescue_plans SET payload=?,status=? WHERE plan_id=?",(plan.model_dump_json(),action,plan_id))
            db.execute("INSERT INTO rescue_events(plan_id,event_type,detail,created_at) VALUES(?,?,?,?)",(plan_id,action,json.dumps({"reason":reason}),datetime.now(timezone.utc).isoformat()))
            db.commit()
            return plan

    def modify(self,plan_id,assignments,expected_version):
        with sqlite3.connect(self.path,timeout=10,isolation_level=None) as db:
            db.execute("BEGIN IMMEDIATE")
            row=db.execute("SELECT payload,status,scenario_id,scenario_version FROM rescue_plans WHERE plan_id=?",(plan_id,)).fetchone()
            if not row:db.rollback();raise ValueError("Plan not found.")
            plan=RescuePlan.model_validate_json(row[0])
            state=db.execute("SELECT state_version,epoch FROM scenarios WHERE id=?",(plan.scenario_id,)).fetchone()
            infra=db.execute("SELECT revision FROM scenario_infrastructure WHERE scenario_id=? AND epoch=?",(plan.scenario_id,plan.scenario_epoch)).fetchone()
            if not state or state[0]!=plan.scenario_version or state[1]!=plan.scenario_epoch or expected_version!=plan.scenario_version or not infra or infra[0]!=plan.infrastructure_revision:
                plan.status="superseded";db.execute("UPDATE rescue_plans SET payload=?,status='superseded' WHERE plan_id=?",(plan.model_dump_json(),plan_id));db.commit();raise ValueError("Plan is stale and cannot be modified.")
            if row[1]!="proposed":db.rollback();raise ValueError("Only proposed plans can be modified.")
            pairs=[(item.unit_id,item.destination_id) for item in assignments]
            if len({u for u,_ in pairs})!=len(pairs) or len({d for _,d in pairs})!=len(pairs):db.rollback();raise ValueError("A unit and destination can each appear only once.")
            approvals=db.execute("SELECT payload FROM rescue_plans WHERE scenario_id=? AND status='approved'",(plan.scenario_id,)).fetchall()
            approved_units={m["unit_id"] for (payload,) in approvals for m in RescuePlan.model_validate_json(payload).missions if RescuePlan.model_validate_json(payload).scenario_epoch==plan.scenario_epoch}
            if approved_units & {unit_id for unit_id,_ in pairs}:db.rollback();raise ValueError("Assignment uses a resource already approved in another plan.")
            allowed={(item["unit_id"],item["destination_id"]):item for item in plan.available_assignments}
            if any(pair not in allowed for pair in pairs):db.rollback();raise ValueError("Assignment is infeasible under the plan's saved routes and capacities.")
            plan.missions=[allowed[pair] for pair in pairs]
            destinations={item["building_id"]:item for item in plan.priorities}
            weighted=sum(destinations[m["destination_id"]]["priority_score"]*m["occupants_targeted"]/max(destinations[m["destination_id"]]["occupants"],1) for m in plan.missions)
            plan.comparison["optimized"].update({"destinations_covered":len(plan.missions),"priority_weighted_coverage":round(weighted,2),"total_distance_m":round(sum(m["route"]["distance_m"] for m in plan.missions),1),"estimated_simulated_minutes":round(sum(m["route"]["simulated_minutes"] for m in plan.missions),1),"resource_utilization":round(len(plan.missions)/max(len({a["unit_id"] for a in plan.available_assignments}),1),3)})
            plan.solver_status="commander_modified"
            db.execute("UPDATE rescue_plans SET payload=? WHERE plan_id=?",(plan.model_dump_json(),plan_id))
            db.execute("INSERT INTO rescue_events(plan_id,event_type,detail,created_at) VALUES(?,?,?,?)",(plan_id,"assignments_modified",json.dumps({"assignments":pairs}),datetime.now(timezone.utc).isoformat()))
            db.commit();return plan
