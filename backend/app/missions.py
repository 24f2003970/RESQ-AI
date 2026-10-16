"""Persistent, deterministic fictional rescue mission operations.

The mission rows and unit_resources table share the scenario SQLite database.
unit_resources is authoritative for availability; approved plans remain the
source for historical approval details and are used to backfill legacy rows.
"""
from __future__ import annotations

import json
import math
import sqlite3
import time
import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .agent_contracts import persist_agent_event

MissionStatus = Literal["ready", "en_route", "blocked", "arrived", "completed", "cancelled"]
ResourceStatus = Literal["available", "reserved", "en_route", "blocked", "at_destination", "unavailable"]
ACTIVE_STATUSES = ("ready", "en_route", "blocked", "arrived")
MAX_ADVANCE_SECONDS = 30
SYNTHETIC_SPEED_MPS = 6.0


class MissionCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)


class MissionClockAdvance(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    expected_state_version: int = Field(ge=1)
    seconds: int = Field(ge=1, le=MAX_ADVANCE_SECONDS)


class RouteApproval(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    route_revision_id: str = Field(min_length=1)


class Mission(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mission_id: str
    plan_id: str
    scenario_id: str
    scenario_epoch: int
    simulation_version: int
    infrastructure_revision: int
    mission_version: int
    unit_id: str
    unit_type: str
    destination_id: str
    unit_capacity: int
    occupants_targeted: int
    status: MissionStatus
    route: dict[str, Any]
    route_revision: int
    traversed_distance_m: float
    total_distance_m: float
    remaining_distance_m: float
    route_segment_index: int
    position: dict[str, float]
    operational_seconds: int
    estimated_remaining_seconds: int
    dispatch_clock_seconds: int | None = None
    arrival_clock_seconds: int | None = None
    completion_clock_seconds: int | None = None
    block_reason: str | None = None
    route_proposal: dict[str, Any] | None = None
    created_at: str
    updated_at: str


class MissionClock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenario_id: str
    scenario_epoch: int
    seconds: int
    version: int
    paused: bool


class MissionEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sequence: int
    event_id: str
    mission_id: str
    event_type: str
    mission_version: int
    clock_seconds: int
    payload: dict[str, Any]
    created_at: str


class MissionAdvanceResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    clock: MissionClock
    missions: list[Mission]
    infrastructure_revision: int


class MissionUnitResource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenario_id: str
    scenario_epoch: int
    unit_id: str
    status: ResourceStatus
    mission_id: str | None
    position: dict[str, float]
    version: int
    updated_at: str


class _ClosingConnection(sqlite3.Connection):
    """SQLite's context manager commits but does not close; close scoped reads too."""
    def __exit__(self, exc_type, exc, traceback):
        try:
            return super().__exit__(exc_type, exc, traceback)
        finally:
            self.close()


def ensure_mission_schema(db: sqlite3.Connection) -> None:
    db.executescript("""
    CREATE TABLE IF NOT EXISTS missions (
      mission_id TEXT PRIMARY KEY, plan_id TEXT NOT NULL, assignment_key TEXT NOT NULL,
      scenario_id TEXT NOT NULL, scenario_epoch INTEGER NOT NULL,
      simulation_version INTEGER NOT NULL, infrastructure_revision INTEGER NOT NULL,
      mission_version INTEGER NOT NULL, unit_id TEXT NOT NULL, unit_type TEXT NOT NULL,
      destination_id TEXT NOT NULL, unit_capacity INTEGER NOT NULL, occupants_targeted INTEGER NOT NULL,
      status TEXT NOT NULL CHECK(status IN ('ready','en_route','blocked','arrived','completed','cancelled')),
      route_json TEXT NOT NULL, route_revision INTEGER NOT NULL DEFAULT 1,
      traversed_distance_m REAL NOT NULL DEFAULT 0, total_distance_m REAL NOT NULL,
      remaining_distance_m REAL NOT NULL, route_segment_index INTEGER NOT NULL DEFAULT 0,
      position_json TEXT NOT NULL, operational_seconds INTEGER NOT NULL DEFAULT 0,
      estimated_remaining_seconds INTEGER NOT NULL DEFAULT 0, dispatch_clock_seconds INTEGER,
      arrival_clock_seconds INTEGER, completion_clock_seconds INTEGER, block_reason TEXT,
      route_proposal_json TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
      UNIQUE(plan_id, assignment_key)
    );
    CREATE INDEX IF NOT EXISTS missions_scenario_epoch ON missions(scenario_id,scenario_epoch,status);
    CREATE TABLE IF NOT EXISTS unit_resources (
      scenario_id TEXT NOT NULL, scenario_epoch INTEGER NOT NULL, unit_id TEXT NOT NULL,
      status TEXT NOT NULL CHECK(status IN ('available','reserved','en_route','blocked','at_destination','unavailable')),
      mission_id TEXT, position_json TEXT NOT NULL DEFAULT '{"x_m":0,"y_m":0,"elevation_m":0}',
      version INTEGER NOT NULL DEFAULT 1, updated_at TEXT NOT NULL,
      PRIMARY KEY(scenario_id,scenario_epoch,unit_id), UNIQUE(mission_id)
    );
    CREATE TABLE IF NOT EXISTS mission_clocks (
      scenario_id TEXT NOT NULL, scenario_epoch INTEGER NOT NULL, seconds INTEGER NOT NULL DEFAULT 0,
      version INTEGER NOT NULL DEFAULT 1, paused INTEGER NOT NULL DEFAULT 0,
      PRIMARY KEY(scenario_id,scenario_epoch)
    );
    CREATE TABLE IF NOT EXISTS mission_events (
      sequence INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL UNIQUE,
      mission_id TEXT NOT NULL, event_type TEXT NOT NULL, mission_version INTEGER NOT NULL,
      clock_seconds INTEGER NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS mission_events_timeline ON mission_events(mission_id,sequence);
    CREATE TABLE IF NOT EXISTS mission_commands (
      idempotency_key TEXT PRIMARY KEY, mission_id TEXT NOT NULL, command TEXT NOT NULL,
      response_json TEXT NOT NULL, created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS mission_clock_commands (
      idempotency_key TEXT PRIMARY KEY, scenario_id TEXT NOT NULL, scenario_epoch INTEGER NOT NULL,
      request_json TEXT NOT NULL, response_json TEXT NOT NULL, created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS mission_clock_events (
      sequence INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL UNIQUE,
      scenario_id TEXT NOT NULL, scenario_epoch INTEGER NOT NULL, event_type TEXT NOT NULL,
      clock_seconds INTEGER NOT NULL, clock_version INTEGER NOT NULL, payload_json TEXT NOT NULL,
      created_at TEXT NOT NULL
    );
    """)
    unit_columns={row[1] for row in db.execute("PRAGMA table_info(unit_resources)")}
    if "position_json" not in unit_columns:
        db.execute("ALTER TABLE unit_resources ADD COLUMN position_json TEXT NOT NULL DEFAULT '{\"x_m\":0,\"y_m\":0,\"elevation_m\":0}'")


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _route_distance(route: dict[str, Any]) -> float:
    segments = route.get("segment_lengths_m")
    if segments:
        return sum(float(x) for x in segments)
    points = route.get("polyline", [])
    return sum(math.dist(points[i], points[i + 1]) for i in range(len(points) - 1))


def _position_at(route: dict[str, Any], distance: float) -> tuple[dict[str, float], int]:
    points = route.get("polyline") or [[0.0, 0.0]]
    points_3d = route.get("polyline_xyz")
    lengths = [float(x) for x in route.get("segment_lengths_m", [])]
    if len(lengths) != len(points) - 1:
        lengths = [math.dist(points[i], points[i + 1]) for i in range(len(points) - 1)]
    left = max(0.0, distance)
    for index, length in enumerate(lengths):
        if left <= length or index == len(lengths) - 1:
            ratio = min(1.0, left / max(length, 1e-9))
            a=points_3d[index] if points_3d and len(points_3d)==len(points) else [points[index][0],points[index][1],0]
            b=points_3d[index+1] if points_3d and len(points_3d)==len(points) else [points[index+1][0],points[index+1][1],0]
            x = a[0] + (b[0] - a[0]) * ratio
            y = a[1] + (b[1] - a[1]) * ratio
            z = a[2] + (b[2] - a[2]) * ratio
            return {"x_m": round(x, 4), "y_m": round(y, 4), "elevation_m":round(z,4)}, index
        left -= length
    end = points[-1]
    xyz=points_3d[-1] if points_3d and len(points_3d)==len(points) else [end[0],end[1],0]
    return {"x_m": float(xyz[0]), "y_m": float(xyz[1]), "elevation_m":float(xyz[2])}, max(0, len(points) - 2)


def _estimate_remaining_seconds(route: dict[str, Any], distance: float) -> int:
    lengths=[float(x) for x in route.get("segment_lengths_m",[])]
    speeds=[float(x) for x in route.get("segment_speeds_mps",[])]
    if len(speeds)!=len(lengths): speeds=[SYNTHETIC_SPEED_MPS]*len(lengths)
    remaining=max(0.0,distance)
    total=0.0
    for length,speed in zip(lengths,speeds):
        used=min(length,remaining)
        remaining-=used
        total+=(length-used)/max(speed,1e-9)
    return int(math.ceil(total))


def _mission_from_row(row: sqlite3.Row) -> Mission:
    return Mission(mission_id=row["mission_id"], plan_id=row["plan_id"], scenario_id=row["scenario_id"],
        scenario_epoch=row["scenario_epoch"], simulation_version=row["simulation_version"],
        infrastructure_revision=row["infrastructure_revision"], mission_version=row["mission_version"],
        unit_id=row["unit_id"], unit_type=row["unit_type"], destination_id=row["destination_id"],
        unit_capacity=row["unit_capacity"], occupants_targeted=row["occupants_targeted"], status=row["status"],
        route=json.loads(row["route_json"]), route_revision=row["route_revision"],
        traversed_distance_m=row["traversed_distance_m"], total_distance_m=row["total_distance_m"],
        remaining_distance_m=row["remaining_distance_m"], route_segment_index=row["route_segment_index"],
        position=json.loads(row["position_json"]), operational_seconds=row["operational_seconds"],
        estimated_remaining_seconds=row["estimated_remaining_seconds"], dispatch_clock_seconds=row["dispatch_clock_seconds"],
        arrival_clock_seconds=row["arrival_clock_seconds"], completion_clock_seconds=row["completion_clock_seconds"],
        block_reason=row["block_reason"], route_proposal=json.loads(row["route_proposal_json"]) if row["route_proposal_json"] else None,
        created_at=row["created_at"], updated_at=row["updated_at"])


def create_approved_missions(db: sqlite3.Connection, plan: dict[str, Any]) -> list[str]:
    """Called inside PlanStore's approval transaction; safe for legacy backfill/retry."""
    ensure_mission_schema(db)
    now = _now()
    ids: list[str] = []
    for assignment in plan.get("missions", []):
        unit_id = assignment["unit_id"]
        destination_id = assignment["destination_id"]
        key = f"{unit_id}:{destination_id}"
        mission_id = "mission-" + uuid.uuid5(uuid.NAMESPACE_URL, f"resq:{plan['plan_id']}:{key}").hex[:20]
        route = assignment.get("route", {})
        total = _route_distance(route)
        if not total or len(route.get("polyline", [])) < 2:
            # Historical approvals are preserved, but an unusable legacy route is not dispatchable.
            status = "blocked"
            reason = "Approved plan has no persisted route geometry; generate a fresh plan in this epoch."
            point = {"x_m": 0.0, "y_m": 0.0, "elevation_m": 0.0}
        else:
            status = "ready"
            reason = None
            point, _ = _position_at(route, 0)
        inserted = db.execute("""INSERT OR IGNORE INTO missions(mission_id,plan_id,assignment_key,scenario_id,scenario_epoch,
          simulation_version,infrastructure_revision,mission_version,unit_id,unit_type,destination_id,unit_capacity,
          occupants_targeted,status,route_json,route_revision,traversed_distance_m,total_distance_m,remaining_distance_m,
          route_segment_index,position_json,operational_seconds,estimated_remaining_seconds,block_reason,created_at,updated_at)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
          (mission_id,plan["plan_id"],key,plan["scenario_id"],plan.get("scenario_epoch",0),plan["scenario_version"],
           plan.get("infrastructure_revision",0),1,unit_id,assignment.get("unit_type","ground"),destination_id,
            assignment.get("unit_capacity",1),assignment.get("occupants_targeted",0),status,_json(route),1,0,total,total,0,
            _json(point),0,_estimate_remaining_seconds(route,0),reason,now,now))
        row = db.execute("SELECT mission_id,status FROM missions WHERE plan_id=? AND assignment_key=?",(plan["plan_id"],key)).fetchone()
        ids.append(row[0])
        # Backfill runs on every startup. Existing mission/resource rows are
        # authoritative and must not be reconstructed from an old approval:
        # doing so would re-reserve a unit after cancellation or restoration.
        if inserted.rowcount:
            rstatus = "reserved" if row[1] == "ready" else "unavailable"
            db.execute("""INSERT INTO unit_resources(scenario_id,scenario_epoch,unit_id,status,mission_id,position_json,version,updated_at)
              VALUES(?,?,?,?,?,?,1,?) ON CONFLICT(scenario_id,scenario_epoch,unit_id) DO UPDATE SET
              status=excluded.status,mission_id=excluded.mission_id,position_json=excluded.position_json,
              version=unit_resources.version+1,updated_at=excluded.updated_at
              WHERE unit_resources.status='available'""",
                       (plan["scenario_id"],plan.get("scenario_epoch",0),unit_id,rstatus,row[0],_json(point),now))
        db.execute("INSERT OR IGNORE INTO mission_events(event_id,mission_id,event_type,mission_version,clock_seconds,payload_json,created_at) VALUES(?,?, 'mission_created',1,0,?,?)",
                   (uuid.uuid5(uuid.NAMESPACE_URL, f"{mission_id}:created").hex, row[0], _json({"plan_id":plan["plan_id"],"legacy_backfill":True,"route":route,"simulation_version":plan["scenario_version"],"infrastructure_revision":plan.get("infrastructure_revision",0)}),now))
    return ids


def backfill_approved_missions(db: sqlite3.Connection) -> None:
    """Migrate old approvals forward without modifying their original plan rows."""
    ensure_mission_schema(db)
    for (payload,) in db.execute("SELECT payload FROM rescue_plans WHERE status='approved' ORDER BY created_at,plan_id").fetchall():
        create_approved_missions(db, json.loads(payload))


class MissionStore:
    def __init__(self, path: str):
        self.path = str(path)
        with self._connect() as db:
            ensure_mission_schema(db)
            backfill_approved_missions(db)

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None, factory=_ClosingConnection)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _clock(db, scenario_id: str, epoch: int) -> MissionClock:
        db.execute("INSERT OR IGNORE INTO mission_clocks(scenario_id,scenario_epoch) VALUES(?,?)",(scenario_id,epoch))
        row=db.execute("SELECT * FROM mission_clocks WHERE scenario_id=? AND scenario_epoch=?",(scenario_id,epoch)).fetchone()
        return MissionClock(scenario_id=scenario_id,scenario_epoch=epoch,seconds=row["seconds"],version=row["version"],paused=bool(row["paused"]))

    @staticmethod
    def _event(db, mission_id, event_type, version, clock, payload):
        db.execute("INSERT INTO mission_events(event_id,mission_id,event_type,mission_version,clock_seconds,payload_json,created_at) VALUES(?,?,?,?,?,?,?)",
          (uuid.uuid4().hex,mission_id,event_type,version,clock,_json(payload),_now()))

    def _fetch(self, db, mission_id):
        row=db.execute("SELECT * FROM missions WHERE mission_id=?",(mission_id,)).fetchone()
        if row is None: raise KeyError("Mission does not exist.")
        return _mission_from_row(row)

    def list(self, scenario_id: str, epoch: int | None = None) -> list[Mission]:
        with self._connect() as db:
            if epoch is None:
                row=db.execute("SELECT epoch FROM scenarios WHERE id=?",(scenario_id,)).fetchone()
                if row is None: raise KeyError("Scenario does not exist.")
                epoch=row[0]
            rows=db.execute("SELECT * FROM missions WHERE scenario_id=? AND scenario_epoch=? ORDER BY created_at,mission_id",(scenario_id,epoch)).fetchall()
            return [_mission_from_row(row) for row in rows]

    def get(self, mission_id: str) -> Mission:
        with self._connect() as db: return self._fetch(db,mission_id)

    def units(self, scenario_id: str, epoch: int):
        with self._connect() as db:
            rows=db.execute("SELECT * FROM unit_resources WHERE scenario_id=? AND scenario_epoch=? ORDER BY unit_id",(scenario_id,epoch)).fetchall()
            return [{key:row[key] for key in ("scenario_id","scenario_epoch","unit_id","status","mission_id","version","updated_at")} | {"position":json.loads(row["position_json"])} for row in rows]

    def unit_positions(self, scenario_id: str, epoch: int):
        with self._connect() as db:
            try:
                rows=db.execute("SELECT unit_id,position_json FROM unit_resources WHERE scenario_id=? AND scenario_epoch=? AND status='available'",(scenario_id,epoch)).fetchall()
            except sqlite3.OperationalError:
                return {}
            return {row[0]:json.loads(row[1]) for row in rows}

    def events(self, mission_id: str):
        with self._connect() as db:
            self._fetch(db,mission_id)
            return [MissionEvent(sequence=r[0],event_id=r[1],mission_id=r[2],event_type=r[3],mission_version=r[4],clock_seconds=r[5],payload=json.loads(r[6]),created_at=r[7])
                    for r in db.execute("SELECT sequence,event_id,mission_id,event_type,mission_version,clock_seconds,payload_json,created_at FROM mission_events WHERE mission_id=? ORDER BY sequence",(mission_id,))]

    def clock(self, scenario_id: str, epoch: int) -> MissionClock:
        with self._connect() as db: return self._clock(db,scenario_id,epoch)

    def command(self, mission_id: str, action: str, expected_version: int, *, idempotency_key: str | None = None, reason: str = "") -> Mission:
        db=self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            if idempotency_key:
                old=db.execute("SELECT mission_id,command,response_json FROM mission_commands WHERE idempotency_key=?",(idempotency_key,)).fetchone()
                if old:
                    if old[0]!=mission_id or old[1]!=action: raise ValueError("Idempotency key was already used for another command.")
                    db.commit(); return Mission.model_validate_json(old[2])
            mission=self._fetch(db,mission_id)
            scenario=db.execute("SELECT epoch,state_version FROM scenarios WHERE id=?",(mission.scenario_id,)).fetchone()
            if scenario is None or scenario[0]!=mission.scenario_epoch: raise ValueError("Mission belongs to a historical scenario epoch.")
            if mission.mission_version!=expected_version: raise ValueError("Mission version is stale; refresh before retrying.")
            if action=="dispatch" and scenario[1]!=mission.simulation_version:
                raise ValueError("Flood scenario state changed after plan approval; a fresh approved plan is required before dispatch.")
            clock=self._clock(db,mission.scenario_id,mission.scenario_epoch)
            if action=="dispatch":
                if mission.status!="ready": raise ValueError("Only a ready mission can be dispatched.")
                infra=db.execute("SELECT revision FROM scenario_infrastructure WHERE scenario_id=? AND epoch=?",(mission.scenario_id,mission.scenario_epoch)).fetchone()
                if infra and infra[0]!=mission.infrastructure_revision: raise ValueError("Infrastructure changed after approval; mission requires route review before dispatch.")
                cursor=db.execute("UPDATE unit_resources SET status='en_route',version=version+1,updated_at=? WHERE mission_id=? AND status='reserved'",(_now(),mission_id))
                if cursor.rowcount!=1: raise ValueError("The mission no longer owns a reserved unit; refresh and generate a new plan.")
                mission.status="en_route"; mission.mission_version+=1; mission.dispatch_clock_seconds=clock.seconds
                mission.updated_at=_now()
                event="mission_dispatched"
            elif action=="pause":
                if mission.status!="en_route": raise ValueError("Only an en-route mission can be paused.")
                db.execute("UPDATE mission_clocks SET paused=1,version=version+1 WHERE scenario_id=? AND scenario_epoch=?",(mission.scenario_id,mission.scenario_epoch))
                mission.mission_version+=1; mission.updated_at=_now(); event="mission_paused"
            elif action=="resume":
                if mission.status!="en_route": raise ValueError("Only an en-route mission can be resumed.")
                db.execute("UPDATE mission_clocks SET paused=0,version=version+1 WHERE scenario_id=? AND scenario_epoch=?",(mission.scenario_id,mission.scenario_epoch))
                mission.mission_version+=1; mission.updated_at=_now(); event="mission_resumed"
            elif action=="complete":
                if mission.status!="arrived": raise ValueError("Only an arrived mission can be explicitly completed.")
                mission.status="completed"; mission.completion_clock_seconds=clock.seconds; mission.mission_version+=1; mission.updated_at=_now()
                cursor=db.execute("UPDATE unit_resources SET status='unavailable',version=version+1,updated_at=? WHERE mission_id=? AND status='at_destination'",(_now(),mission_id))
                if cursor.rowcount!=1: raise ValueError("The arrived mission's unit reservation is inconsistent; no completion was recorded.")
                event="mission_completed"
            elif action=="cancel":
                if mission.status not in ("ready","en_route","blocked","arrived"): raise ValueError("This mission cannot be cancelled from its current state.")
                if mission.status!="ready":
                    mission.status="cancelled"; mission.mission_version+=1; mission.updated_at=_now()
                    cursor=db.execute("UPDATE unit_resources SET status='unavailable',version=version+1,updated_at=? WHERE mission_id=? AND status IN ('en_route','blocked','at_destination')",(_now(),mission_id))
                    if cursor.rowcount!=1: raise ValueError("The dispatched mission's unit reservation is inconsistent; no cancellation was recorded.")
                    event="mission_cancelled_unit_unavailable"
                else:
                    mission.status="cancelled"; mission.mission_version+=1; mission.updated_at=_now()
                    cursor=db.execute("UPDATE unit_resources SET status='available',mission_id=NULL,version=version+1,updated_at=? WHERE mission_id=? AND status='reserved'",(_now(),mission_id))
                    if cursor.rowcount!=1: raise ValueError("The ready mission no longer owns a reserved unit; no cancellation was recorded.")
                    event="mission_cancelled"
            elif action=="restore":
                if mission.status not in ("completed","cancelled"): raise ValueError("Return-to-service is allowed only after completion or a ready-mission cancellation.")
                cursor=db.execute("UPDATE unit_resources SET status='available',mission_id=NULL,position_json=?,version=version+1,updated_at=? WHERE mission_id=? AND status='unavailable'",(_json(mission.position),_now(),mission_id))
                if cursor.rowcount==0: raise ValueError("Unit is not awaiting return-to-service.")
                if db.total_changes==0: raise ValueError("Unit is not awaiting return-to-service.")
                mission.mission_version+=1; mission.updated_at=_now(); event="unit_returned_to_service"
            else: raise ValueError("Unknown mission action.")
            if action in {"dispatch","complete","cancel","restore"}:
                db.execute("UPDATE missions SET status=?,mission_version=?,dispatch_clock_seconds=?,completion_clock_seconds=?,updated_at=? WHERE mission_id=?",
                    (mission.status,mission.mission_version,mission.dispatch_clock_seconds,mission.completion_clock_seconds,mission.updated_at,mission_id))
            else:
                db.execute("UPDATE missions SET mission_version=?,updated_at=? WHERE mission_id=?",(mission.mission_version,mission.updated_at,mission_id))
            self._event(db,mission_id,event,mission.mission_version,clock.seconds,{"reason":reason,"status":mission.status})
            refreshed=self._fetch(db,mission_id)
            if idempotency_key:
                db.execute("INSERT INTO mission_commands VALUES(?,?,?,?,?)",(idempotency_key,mission_id,action,refreshed.model_dump_json(),_now()))
            self._agent_event(db,mission,event)
            db.commit(); return refreshed
        except Exception:
            db.rollback(); raise
        finally: db.close()

    @staticmethod
    def _agent_event(db, mission: Mission, event_type: str, payload: dict | None = None):
        row=db.execute("SELECT tick,state_version FROM scenarios WHERE id=?",(mission.scenario_id,)).fetchone()
        if not row: return
        infra=db.execute("SELECT revision FROM scenario_infrastructure WHERE scenario_id=? AND epoch=?",(mission.scenario_id,mission.scenario_epoch)).fetchone()
        persist_agent_event(db,event_type=event_type,scenario_id=mission.scenario_id,scenario_epoch=mission.scenario_epoch,
            simulation_tick=row[0],state_version=row[1],infrastructure_revision=infra[0] if infra else mission.infrastructure_revision,
            source_module="mission_store",payload={"mission_id":mission.mission_id,**(payload or {})})

    def advance(self, scenario_id: str, epoch: int, expected_version: int, expected_state_version: int, seconds: int,
                disrupted_road_ids: set[str] | None = None, idempotency_key: str | None = None) -> tuple[MissionClock,list[Mission]]:
        if not 1<=seconds<=MAX_ADVANCE_SECONDS: raise ValueError(f"Mission clock advances must be between 1 and {MAX_ADVANCE_SECONDS} seconds.")
        db=self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            request_json=_json({"scenario_id":scenario_id,"scenario_epoch":epoch,"expected_version":expected_version,
                                "expected_state_version":expected_state_version,"seconds":seconds})
            if idempotency_key:
                old=db.execute("SELECT scenario_id,scenario_epoch,request_json,response_json FROM mission_clock_commands WHERE idempotency_key=?",(idempotency_key,)).fetchone()
                if old:
                    if old[0]!=scenario_id or old[1]!=epoch or old[2]!=request_json: raise ValueError("Idempotency key was already used for a different clock advance.")
                    response=json.loads(old[3]);db.commit()
                    return MissionClock.model_validate(response["clock"]),[Mission.model_validate(x) for x in response["missions"]]
            clock=self._clock(db,scenario_id,epoch)
            if clock.version!=expected_version: raise ValueError("Mission clock version is stale; refresh before advancing.")
            if clock.paused: raise ValueError("Mission clock is paused.")
            scenario=db.execute("SELECT epoch,tick,state_version FROM scenarios WHERE id=?",(scenario_id,)).fetchone()
            if not scenario or scenario[0]!=epoch: raise ValueError("Mission clock epoch is no longer active.")
            if scenario[2]!=expected_state_version: raise ValueError("Flood scenario version changed; refresh before advancing mission time.")
            now_seconds=clock.seconds+seconds
            db.execute("UPDATE mission_clocks SET seconds=?,version=version+1 WHERE scenario_id=? AND scenario_epoch=?",(now_seconds,scenario_id,epoch))
            db.execute("INSERT INTO mission_clock_events(event_id,scenario_id,scenario_epoch,event_type,clock_seconds,clock_version,payload_json,created_at) VALUES(?,?,?,'clock_advanced',?,?,?,?)",
                (uuid.uuid4().hex,scenario_id,epoch,now_seconds,clock.version+1,_json({"seconds_advanced":seconds,"expected_state_version":expected_state_version}),_now()))
            rows=db.execute("SELECT * FROM missions WHERE scenario_id=? AND scenario_epoch=? AND status='en_route' ORDER BY mission_id",(scenario_id,epoch)).fetchall()
            updated=[]
            for row in rows:
                mission=_mission_from_row(row)
                if db.execute("SELECT paused FROM mission_clocks WHERE scenario_id=? AND scenario_epoch=?",(scenario_id,epoch)).fetchone()[0]: continue
                route=mission.route
                lengths=[float(x) for x in route.get("segment_lengths_m",[])]
                speeds=[float(x) for x in route.get("segment_speeds_mps",[])]
                if len(lengths)!=len(route.get("polyline",[]))-1: lengths=[math.dist(route["polyline"][i],route["polyline"][i+1]) for i in range(len(route.get("polyline",[]))-1)]
                if len(speeds)!=len(lengths): speeds=[SYNTHETIC_SPEED_MPS]*len(lengths)
                distance=mission.traversed_distance_m; seconds_left=seconds; index=mission.route_segment_index
                closures={r[0] for r in db.execute("SELECT road_id FROM road_closures WHERE scenario_id=? AND epoch=? AND active=1",(scenario_id,epoch))}
                closures |= disrupted_road_ids or set()
                edge_ids=route.get("edge_ids",[])
                # A road closure blocks only a matching untraversed graph segment.
                for i in range(index,len(lengths)):
                    edge=edge_ids[i] if i<len(edge_ids) else ""
                    road=edge.split(":",1)[0] if not edge.startswith("access:") else None
                    road_blocked=road in closures or (road is not None and f"bridge:{road}" in closures and ":bridge:" in edge)
                    if road_blocked and distance < sum(lengths[:i+1])-1e-6:
                        mission.status="blocked"; mission.block_reason=f"Road {road} closed ahead of the simulated unit."; mission.mission_version+=1
                        db.execute("UPDATE unit_resources SET status='blocked',version=version+1,updated_at=? WHERE mission_id=?",(_now(),mission.mission_id))
                        self._event(db,mission.mission_id,"mission_blocked",mission.mission_version,now_seconds,{"road_id":road,"route_segment_index":i,"traversed_distance_m":distance})
                        self._agent_event(db,mission,"mission_blocked",{"road_id":road})
                        break
                    seg_start=sum(lengths[:i]); already=max(0.0,distance-seg_start); seg_remaining=max(0.0,lengths[i]-already)
                    if seconds_left<=0: break
                    can=seconds_left*speeds[i]
                    taken=min(seg_remaining,can)
                    distance+=taken; seconds_left-=taken/max(speeds[i],1e-9)
                    if taken+1e-7<seg_remaining: break
                    index=i+1
                if mission.status=="blocked":
                    db.execute("UPDATE missions SET status='blocked',mission_version=?,block_reason=?,traversed_distance_m=?,remaining_distance_m=?,route_segment_index=?,position_json=?,operational_seconds=operational_seconds+?,updated_at=? WHERE mission_id=?",
                        (mission.mission_version,mission.block_reason,distance,max(0,mission.total_distance_m-distance),max(0,index),_json(_position_at(route,distance)[0]),seconds-seconds_left,_now(),mission.mission_id))
                else:
                    arrived=distance>=mission.total_distance_m-1e-6
                    status="arrived" if arrived else "en_route"
                    mission.mission_version+=1
                    pos,seg=_position_at(route,min(distance,mission.total_distance_m))
                    left=max(0,mission.total_distance_m-distance)
                    eta=0 if arrived else _estimate_remaining_seconds(route,distance)
                    elapsed=int(round(seconds-seconds_left))
                    arrival_seconds=(clock.seconds+elapsed) if arrived else None
                    db.execute("UPDATE missions SET status=?,mission_version=?,traversed_distance_m=?,remaining_distance_m=?,route_segment_index=?,position_json=?,operational_seconds=operational_seconds+?,estimated_remaining_seconds=?,arrival_clock_seconds=?,updated_at=? WHERE mission_id=?",
                        (status,mission.mission_version,distance,left,seg,_json(pos),elapsed,eta,arrival_seconds,_now(),mission.mission_id))
                    if arrived:
                        db.execute("UPDATE unit_resources SET status='at_destination',version=version+1,updated_at=? WHERE mission_id=?",(_now(),mission.mission_id))
                        self._event(db,mission.mission_id,"mission_arrived",mission.mission_version,arrival_seconds,{"position":pos,"occupants_targeted_is_synthetic":True})
                        self._agent_event(db,mission,"mission_arrived")
                    else:
                        self._event(db,mission.mission_id,"mission_progressed",mission.mission_version,now_seconds,{"traversed_distance_m":round(distance,3),"remaining_distance_m":round(left,3),"position":pos,"route_revision":mission.route_revision})
                final_position=_position_at(route,min(distance,mission.total_distance_m))[0]
                db.execute("UPDATE unit_resources SET position_json=?,updated_at=? WHERE mission_id=?",(_json(final_position),_now(),mission.mission_id))
                updated.append(self._fetch(db,mission.mission_id))
            clock=self._clock(db,scenario_id,epoch)
            if idempotency_key:
                response_json=_json({"clock":clock.model_dump(mode="json"),"missions":[item.model_dump(mode="json") for item in updated]})
                db.execute("INSERT INTO mission_clock_commands VALUES(?,?,?,?,?,?)",(idempotency_key,scenario_id,epoch,request_json,response_json,_now()))
            db.commit(); return clock,updated
        except Exception:
            db.rollback(); raise
        finally: db.close()

    def set_paused(self, scenario_id: str, epoch: int, expected_version: int, paused: bool, idempotency_key: str | None = None) -> MissionClock:
        db=self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            scenario=db.execute("SELECT epoch FROM scenarios WHERE id=?",(scenario_id,)).fetchone()
            if not scenario or scenario[0]!=epoch: raise ValueError("Mission clock belongs to a historical scenario epoch.")
            command_json=_json({"scenario_id":scenario_id,"scenario_epoch":epoch,"expected_version":expected_version,"paused":paused})
            if idempotency_key:
                old=db.execute("SELECT scenario_id,scenario_epoch,request_json,response_json FROM mission_clock_commands WHERE idempotency_key=?",(idempotency_key,)).fetchone()
                if old:
                    if old[0]!=scenario_id or old[1]!=epoch or old[2]!=command_json: raise ValueError("Idempotency key was already used for a different clock command.")
                    db.commit();return MissionClock.model_validate(json.loads(old[3])["clock"])
            clock=self._clock(db,scenario_id,epoch)
            if clock.version!=expected_version: raise ValueError("Mission clock version is stale.")
            db.execute("UPDATE mission_clocks SET paused=?,version=version+1 WHERE scenario_id=? AND scenario_epoch=?",(int(paused),scenario_id,epoch))
            updated=self._clock(db,scenario_id,epoch)
            db.execute("INSERT INTO mission_clock_events(event_id,scenario_id,scenario_epoch,event_type,clock_seconds,clock_version,payload_json,created_at) VALUES(?,?,?,?,?,?,?,?)",
              (uuid.uuid4().hex,scenario_id,epoch,"clock_paused" if paused else "clock_resumed",clock.seconds,clock.version+1,_json({}),_now()))
            if idempotency_key:
                db.execute("INSERT INTO mission_clock_commands VALUES(?,?,?,?,?,?)",(idempotency_key,scenario_id,epoch,command_json,_json({"clock":updated.model_dump(mode="json"),"missions":[]}),_now()))
            db.commit(); return updated
        except Exception: db.rollback(); raise
        finally: db.close()

    def infrastructure_changed(self, scenario_id: str, epoch: int, revision: int, closed_road_ids: set[str], simulation_version: int | None = None) -> list[str]:
        """Block only dispatched missions with a now-closed untraversed edge."""
        db=self._connect(); blocked=[]
        try:
            db.execute("BEGIN IMMEDIATE")
            clock=self._clock(db,scenario_id,epoch)
            rows=db.execute("SELECT * FROM missions WHERE scenario_id=? AND scenario_epoch=? AND status='en_route'",(scenario_id,epoch)).fetchall()
            for row in rows:
                mission=_mission_from_row(row);route=mission.route
                lengths=[float(x) for x in route.get("segment_lengths_m",[])]
                distance=mission.traversed_distance_m; edge_ids=route.get("edge_ids",[])
                hit=None
                for i,edge in enumerate(edge_ids):
                    road=edge.split(":",1)[0] if not edge.startswith("access:") else None
                    segment_start=sum(lengths[:i]) if i<len(lengths) else float("inf")
                    segment_end=segment_start+(lengths[i] if i<len(lengths) else 0)
                    road_blocked=road in closed_road_ids or (road is not None and f"bridge:{road}" in closed_road_ids and ":bridge:" in edge)
                    if road_blocked and segment_end>distance+1e-6:
                        hit=(road,i);break
                if hit:
                    mission.status="blocked";mission.block_reason=f"Road {hit[0]} closed before the simulated unit traversed that route segment.";mission.mission_version+=1;mission.infrastructure_revision=revision
                    if simulation_version is not None: mission.simulation_version=simulation_version
                    db.execute("UPDATE missions SET status='blocked',mission_version=?,simulation_version=?,infrastructure_revision=?,block_reason=?,updated_at=? WHERE mission_id=?",(mission.mission_version,mission.simulation_version,revision,mission.block_reason,_now(),mission.mission_id))
                    db.execute("UPDATE unit_resources SET status='blocked',version=version+1,updated_at=? WHERE mission_id=?",(_now(),mission.mission_id))
                    self._event(db,mission.mission_id,"mission_blocked",mission.mission_version,clock.seconds,{"road_id":hit[0],"segment_index":hit[1],"infrastructure_revision":revision,"simulation_version":mission.simulation_version,"traversed_distance_m":distance})
                    self._agent_event(db,mission,"mission_blocked",{"road_id":hit[0],"infrastructure_revision":revision})
                    blocked.append(mission.mission_id)
            db.commit(); return blocked
        except Exception: db.rollback(); raise
        finally: db.close()

    def propose_route(self, mission_id: str, expected_version: int, city, state, closures: list[str], infrastructure_revision: int,
                      idempotency_key: str | None = None):
        from .rescue import build_road_graph, route_from_mission_segment
        db=self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            command_name=f"route_proposal:v{expected_version}"
            if idempotency_key:
                old=db.execute("SELECT mission_id,command,response_json FROM mission_commands WHERE idempotency_key=?",(idempotency_key,)).fetchone()
                if old:
                    if old[0]!=mission_id or old[1]!=command_name: raise ValueError("Idempotency key was already used for another mission command.")
                    db.commit();return Mission.model_validate_json(old[2])
            mission=self._fetch(db,mission_id)
            if mission.mission_version!=expected_version: raise ValueError("Mission version is stale.")
            if mission.status!="blocked": raise ValueError("A route replacement can be requested only for a blocked mission.")
            if state.id!=mission.scenario_id or state.epoch!=mission.scenario_epoch: raise ValueError("Mission is outside the active scenario epoch.")
            current=db.execute("SELECT epoch,state_version FROM scenarios WHERE id=?",(mission.scenario_id,)).fetchone()
            infra=db.execute("SELECT revision FROM scenario_infrastructure WHERE scenario_id=? AND epoch=?",(mission.scenario_id,mission.scenario_epoch)).fetchone()
            if not current or current[0]!=state.epoch or current[1]!=state.state_version or not infra or infra[0]!=infrastructure_revision:
                raise ValueError("Scenario or infrastructure changed before the route proposal could be saved.")
            graph=build_road_graph(city,state,closures)
            destination=next((b for b in city.buildings if b.id==mission.destination_id),None)
            if destination is None: raise ValueError("Mission destination no longer exists in this city snapshot.")
            current={"x_m":mission.position["x_m"],"y_m":mission.position["y_m"],"elevation_m":mission.position.get("elevation_m",0)}
            recommendation=route_from_mission_segment(graph,mission.route,mission.traversed_distance_m,
                mission.route_segment_index,current,destination.position,mission.unit_type)
            if not recommendation.get("reachable"):
                raise ValueError("No safe replacement route is reachable from the blocked unit: "+recommendation.get("reason","route unavailable."))
            proposal={"route_revision_id":uuid.uuid4().hex,"blocked_mission_version":mission.mission_version,"simulation_version":state.state_version,
              "scenario_epoch":state.epoch,"infrastructure_revision":infrastructure_revision,"route":recommendation}
            mission.mission_version+=1;mission.updated_at=_now()
            db.execute("UPDATE missions SET mission_version=?,route_proposal_json=?,updated_at=? WHERE mission_id=?",(mission.mission_version,_json(proposal),mission.updated_at,mission_id))
            self._event(db,mission_id,"route_replacement_proposed",mission.mission_version,self._clock(db,mission.scenario_id,mission.scenario_epoch).seconds,
                {"route_revision_id":proposal["route_revision_id"],"edge_ids":recommendation.get("edge_ids",[]),"route":recommendation,"simulation_version":state.state_version,"infrastructure_revision":infrastructure_revision})
            refreshed=self._fetch(db,mission_id)
            if idempotency_key:
                db.execute("INSERT INTO mission_commands VALUES(?,?,?,?,?)",(idempotency_key,mission_id,command_name,refreshed.model_dump_json(),_now()))
            db.commit(); return refreshed
        except Exception: db.rollback(); raise
        finally: db.close()

    def approve_route(self, mission_id: str, expected_version: int, revision_id: str, state, infrastructure_revision: int,
                      idempotency_key: str | None = None):
        db=self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            command_name=f"route_approval:{revision_id}:v{expected_version}"
            if idempotency_key:
                old=db.execute("SELECT mission_id,command,response_json FROM mission_commands WHERE idempotency_key=?",(idempotency_key,)).fetchone()
                if old:
                    if old[0]!=mission_id or old[1]!=command_name: raise ValueError("Idempotency key was already used for another mission command.")
                    db.commit();return Mission.model_validate_json(old[2])
            mission=self._fetch(db,mission_id)
            if mission.mission_version!=expected_version: raise ValueError("Mission version is stale.")
            p=mission.route_proposal
            if mission.status!="blocked" or not p or p["route_revision_id"]!=revision_id: raise ValueError("No matching route proposal is awaiting approval.")
            current=db.execute("SELECT epoch,state_version FROM scenarios WHERE id=?",(mission.scenario_id,)).fetchone()
            infra=db.execute("SELECT revision FROM scenario_infrastructure WHERE scenario_id=? AND epoch=?",(mission.scenario_id,mission.scenario_epoch)).fetchone()
            if state.epoch!=mission.scenario_epoch or state.id!=mission.scenario_id or not current or current[0]!=state.epoch or current[1]!=state.state_version or p["simulation_version"]!=state.state_version or not infra or infra[0]!=infrastructure_revision or p["infrastructure_revision"]!=infrastructure_revision: raise ValueError("Route proposal is stale against the scenario or infrastructure state.")
            # Revalidate that every proposed road is still open against this revision.
            current_closures={r[0] for r in db.execute("SELECT road_id FROM road_closures WHERE scenario_id=? AND epoch=? AND active=1",(mission.scenario_id,mission.scenario_epoch))}
            used={e.split(":",1)[0] for e in p["route"].get("edge_ids",[]) if not e.startswith("access:")}
            if used & current_closures: raise ValueError("The proposed route contains a road that is currently closed.")
            clock=self._clock(db,mission.scenario_id,mission.scenario_epoch)
            route_data=p["route"]; total=_route_distance(route_data); pos,seg=_position_at(route_data,0)
            mission.route=route_data;mission.route_revision+=1;mission.simulation_version=state.state_version;mission.traversed_distance_m=0;mission.total_distance_m=total;mission.remaining_distance_m=total;mission.route_segment_index=seg;mission.position=pos
            mission.status="en_route";mission.block_reason=None;mission.route_proposal=None;mission.mission_version+=1;mission.infrastructure_revision=infrastructure_revision
            mission.estimated_remaining_seconds=_estimate_remaining_seconds(route_data,0);mission.updated_at=_now()
            db.execute("UPDATE missions SET status='en_route',mission_version=?,simulation_version=?,infrastructure_revision=?,route_json=?,route_revision=?,traversed_distance_m=0,total_distance_m=?,remaining_distance_m=?,route_segment_index=?,position_json=?,estimated_remaining_seconds=?,block_reason=NULL,route_proposal_json=NULL,updated_at=? WHERE mission_id=?",
              (mission.mission_version,state.state_version,infrastructure_revision,_json(route_data),mission.route_revision,total,total,seg,_json(pos),mission.estimated_remaining_seconds,mission.updated_at,mission_id))
            cursor=db.execute("UPDATE unit_resources SET status='en_route',version=version+1,updated_at=? WHERE mission_id=? AND status='blocked'",(_now(),mission_id))
            if cursor.rowcount!=1: raise ValueError("The blocked mission no longer owns its unit; route approval was not applied.")
            self._event(db,mission_id,"route_revision_approved",mission.mission_version,clock.seconds,{"route_revision":mission.route_revision,"route_revision_id":revision_id,"edge_ids":route_data.get("edge_ids",[]),"route":route_data,"simulation_version":state.state_version,"infrastructure_revision":infrastructure_revision})
            self._agent_event(db,mission,"mission_route_revision_approved",{"route_revision":mission.route_revision})
            refreshed=self._fetch(db,mission_id)
            if idempotency_key:
                db.execute("INSERT INTO mission_commands VALUES(?,?,?,?,?)",(idempotency_key,mission_id,command_name,refreshed.model_dump_json(),_now()))
            db.commit();return refreshed
        except Exception: db.rollback();raise
        finally: db.close()

    def replay(self, mission_id: str):
        # Event timeline is immutable observation data; this read path never changes reservations.
        return self.events(mission_id)

    def clock_events(self, scenario_id: str, epoch: int):
        with self._connect() as db:
            return [{"sequence":r[0],"event_id":r[1],"event_type":r[2],"clock_seconds":r[3],"clock_version":r[4],"payload":json.loads(r[5]),"created_at":r[6]}
                for r in db.execute("SELECT sequence,event_id,event_type,clock_seconds,clock_version,payload_json,created_at FROM mission_clock_events WHERE scenario_id=? AND scenario_epoch=? ORDER BY sequence",(scenario_id,epoch))]
