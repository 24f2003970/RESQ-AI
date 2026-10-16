"""SQLite-backed scenario state, event history and deterministic replay."""

import hashlib
import json
import os
import sqlite3
import threading
import uuid
import zlib
from contextlib import contextmanager
from pathlib import Path

import numpy as np

from .city_service import generate_city
from .agent_contracts import ensure_agent_event_table, persist_agent_event
from .flood import STEP_SECONDS, channel_mask, impact_assessment, initial_depth, step
from .schemas import (
    AdvanceRequest, ImpactAssessment, MassBalance, ParameterUpdate, ScenarioCreate,
    ScenarioEnvelope, ScenarioState, SimulationEvent, SimulationParameters,
)
from .terrain import CELL_SIZE_M, GRID_HEIGHT, GRID_WIDTH, grid_coordinates, terrain_grid

PRESETS = {
    "mild": {"name": "Mild rainfall", "rainfall_mm_h": 8.0, "river_level_m": -0.5, "drainage_effectiveness": 0.8, "speed": 1.0},
    "heavy": {"name": "Heavy rainfall", "rainfall_mm_h": 90.0, "river_level_m": 0.25, "drainage_effectiveness": 0.45, "speed": 1.0},
    "extreme": {"name": "Extreme rainfall + river overflow", "rainfall_mm_h": 180.0, "river_level_m": 1.4, "drainage_effectiveness": 0.2, "speed": 1.0},
}


class ScenarioError(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code


def _json(value) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def _params(row) -> SimulationParameters:
    return SimulationParameters.model_validate(json.loads(row["parameters_json"]))


def _balance(row) -> MassBalance:
    return MassBalance.model_validate(json.loads(row["mass_json"]))


def _infra_revision(db,scenario_id,epoch):
    try:
        row=db.execute("SELECT revision FROM scenario_infrastructure WHERE scenario_id=? AND epoch=?",(scenario_id,epoch)).fetchone()
        return row[0] if row else 0
    except sqlite3.OperationalError:
        return 0


class ScenarioStore:
    def __init__(self, db_path: str | Path | None = None):
        self.path = Path(db_path or os.getenv("RESQ_DB_PATH", Path(__file__).resolve().parents[1] / "data" / "resq.sqlite3"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        with self._connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                PRAGMA foreign_keys=ON;
                CREATE TABLE IF NOT EXISTS scenarios (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, seed INTEGER NOT NULL,
                    preset TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('paused','running')),
                    tick INTEGER NOT NULL, epoch INTEGER NOT NULL, state_version INTEGER NOT NULL,
                    simulated_seconds INTEGER NOT NULL, parameters_json TEXT NOT NULL,
                    initial_parameters_json TEXT NOT NULL, depth_blob BLOB NOT NULL, mass_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE TABLE IF NOT EXISTS events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT UNIQUE NOT NULL,
                    scenario_id TEXT NOT NULL REFERENCES scenarios(id), epoch INTEGER NOT NULL,
                    tick INTEGER NOT NULL, simulated_seconds INTEGER NOT NULL, state_version INTEGER NOT NULL,
                    event_type TEXT NOT NULL, entity_ids_json TEXT NOT NULL, payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS events_timeline ON events(scenario_id, epoch, tick, sequence);
                CREATE TABLE IF NOT EXISTS checkpoints (
                    scenario_id TEXT NOT NULL REFERENCES scenarios(id), epoch INTEGER NOT NULL,
                    tick INTEGER NOT NULL, depth_blob BLOB NOT NULL, mass_json TEXT NOT NULL,
                    state_version INTEGER NOT NULL, PRIMARY KEY(scenario_id, epoch, tick)
                );
                CREATE TABLE IF NOT EXISTS creation_keys (
                    idempotency_key TEXT PRIMARY KEY, request_hash TEXT NOT NULL,
                    scenario_id TEXT NOT NULL REFERENCES scenarios(id)
                );
            """)
            ensure_agent_event_table(db)
            if db.execute("SELECT 1 FROM scenarios LIMIT 1").fetchone() is None:
                self._create_row(db, ScenarioCreate(name="Riverside / Mild rainfall", seed=2026, preset="mild"), "scenario-riverside-2026")

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=10000")
        try:
            yield db
        finally:
            db.close()

    @staticmethod
    def _event(db, row, event_type: str, payload: dict, entity_ids=None, *, tick=None, version=None, epoch=None):
        tick = row["tick"] if tick is None else tick
        db.execute(
            "INSERT INTO events(event_id,scenario_id,epoch,tick,simulated_seconds,state_version,event_type,entity_ids_json,payload_json) VALUES(?,?,?,?,?,?,?,?,?)",
            (uuid.uuid4().hex, row["id"], row["epoch"] if epoch is None else epoch, tick,
             tick * STEP_SECONDS, row["state_version"] if version is None else version,
             event_type, _json(entity_ids or []), _json(payload)),
        )

    def _create_row(self, db, request: ScenarioCreate, scenario_id: str | None = None):
        preset = PRESETS[request.preset]
        params = SimulationParameters.model_validate({key: value for key, value in preset.items() if key != "name"})
        depth = initial_depth(request.seed, params.river_level_m)
        initial_volume = float(depth.sum() * CELL_SIZE_M**2)
        balance = MassBalance(initial_m3=initial_volume, rainfall_m3=0, river_in_m3=0, river_out_m3=0,
                              drainage_m3=0, stored_m3=initial_volume, balance_error_m3=0)
        sid = scenario_id or f"scenario-{uuid.uuid4().hex[:12]}"
        data = (sid, request.name, request.seed, request.preset, "paused", 0, 0, 1, 0,
                _json(params.model_dump()), _json(params.model_dump()), zlib.compress(depth.tobytes()),
                _json(balance.model_dump()))
        db.execute("INSERT INTO scenarios(id,name,seed,preset,status,tick,epoch,state_version,simulated_seconds,parameters_json,initial_parameters_json,depth_blob,mass_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", data)
        row = db.execute("SELECT * FROM scenarios WHERE id=?", (sid,)).fetchone()
        self._event(db, row, "scenario_created", {"name": request.name, "preset": request.preset, "seed": request.seed}, version=1)
        self._event(db, row, "simulation_paused", {"reason": "new scenario starts paused"}, version=1)
        persist_agent_event(db,event_type="scenario_created",scenario_id=sid,scenario_epoch=row["epoch"],
            simulation_tick=row["tick"],state_version=row["state_version"],source_module="scenario_store",
            payload={"name":request.name,"preset":request.preset,"seed":request.seed},infrastructure_revision=0)
        return sid

    def create(self, request: ScenarioCreate, idempotency_key: str) -> ScenarioEnvelope:
        with self.lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            fingerprint = hashlib.sha256(_json(request.model_dump()).encode()).hexdigest()
            existing = db.execute("SELECT * FROM creation_keys WHERE idempotency_key=?", (idempotency_key,)).fetchone()
            if existing:
                if existing["request_hash"] != fingerprint:
                    db.rollback()
                    raise ScenarioError(409, "This idempotency key was already used for a different scenario request.")
                result = self._envelope(db, db.execute("SELECT * FROM scenarios WHERE id=?", (existing["scenario_id"],)).fetchone())
                db.commit()
                return result
            sid = self._create_row(db, request)
            db.execute("INSERT INTO creation_keys(idempotency_key,request_hash,scenario_id) VALUES(?,?,?)", (idempotency_key, fingerprint, sid))
            result = self._envelope(db, db.execute("SELECT * FROM scenarios WHERE id=?", (sid,)).fetchone())
            db.commit()
            return result

    def import_snapshot(self, state: ScenarioState, scenario_id: str) -> ScenarioEnvelope:
        """Create an isolated scenario from an exact physical snapshot.

        Used by analytical experiments so variants start from the same depth,
        mass balance, parameters, tick, seed, epoch, and state version.
        This writes only to the ScenarioStore database it was called on.
        """
        depth = np.asarray(state.depth_m, dtype=np.float64)
        if depth.shape != (GRID_HEIGHT, GRID_WIDTH) or not np.isfinite(depth).all() or (depth < 0).any():
            raise ScenarioError(422, "The experiment starting flood snapshot is invalid.")
        with self.lock, self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT 1 FROM scenarios WHERE id=?", (scenario_id,)).fetchone()
            if existing:
                db.rollback()
                raise ScenarioError(409, "The isolated experiment scenario already exists.")
            params = state.parameters
            db.execute(
                "INSERT INTO scenarios(id,name,seed,preset,status,tick,epoch,state_version,simulated_seconds,parameters_json,initial_parameters_json,depth_blob,mass_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (scenario_id, state.name, state.seed, state.preset, "paused", state.tick,
                 state.epoch, state.state_version, state.simulated_seconds,
                 _json(params.model_dump()), _json(params.model_dump()),
                 zlib.compress(depth.tobytes()), _json(state.mass_balance.model_dump())),
            )
            row = db.execute("SELECT * FROM scenarios WHERE id=?", (scenario_id,)).fetchone()
            self._event(db, row, "experiment_snapshot_imported", {
                "source_scenario_id": state.id,
                "source_state_version": state.state_version,
                "source_epoch": state.epoch,
            }, version=state.state_version, tick=state.tick, epoch=state.epoch)
            if state.tick % 12 == 0:
                db.execute("INSERT OR REPLACE INTO checkpoints VALUES(?,?,?,?,?,?)",
                    (scenario_id, state.epoch, state.tick, zlib.compress(depth.tobytes()),
                     _json(state.mass_balance.model_dump()), state.state_version))
            result = self._envelope(db, row)
            db.commit()
            return result

    def active_id(self) -> str:
        with self._connect() as db:
            row = db.execute("SELECT id FROM scenarios ORDER BY created_at DESC, rowid DESC LIMIT 1").fetchone()
            return row["id"]

    def get(self, scenario_id: str) -> ScenarioEnvelope:
        with self._connect() as db:
            row = db.execute("SELECT * FROM scenarios WHERE id=?", (scenario_id,)).fetchone()
            if row is None:
                raise ScenarioError(404, "Scenario does not exist.")
            return self._envelope(db, row)

    def _depth(self, row):
        return np.frombuffer(zlib.decompress(row["depth_blob"]), dtype=np.float64).reshape(GRID_HEIGHT, GRID_WIDTH).copy()

    def _events(self, db, scenario_id: str, epoch=None, *, limit=250):
        sql = "SELECT * FROM events WHERE scenario_id=?"
        values: list[object] = [scenario_id]
        if epoch is not None:
            sql += " AND epoch=?"
            values.append(epoch)
        sql += " ORDER BY sequence DESC LIMIT ?"
        values.append(limit)
        rows = db.execute(sql, values).fetchall()[::-1]
        return [SimulationEvent(event_id=e["event_id"], scenario_id=e["scenario_id"], tick=e["tick"],
            simulated_seconds=e["simulated_seconds"], state_version=e["state_version"], event_type=e["event_type"],
            entity_ids=json.loads(e["entity_ids_json"]), payload=json.loads(e["payload_json"])) for e in rows]

    def events(self, scenario_id: str) -> list[SimulationEvent]:
        with self._connect() as db:
            if db.execute("SELECT 1 FROM scenarios WHERE id=?", (scenario_id,)).fetchone() is None:
                raise ScenarioError(404, "Scenario does not exist.")
            return self._events(db, scenario_id, limit=1000)

    def _state(self, row, depth=None, params=None, balance=None, *, replay=False, tick=None, version=None):
        depth = self._depth(row) if depth is None else depth
        params = _params(row) if params is None else params
        balance = _balance(row) if balance is None else balance
        tick = row["tick"] if tick is None else tick
        city = generate_city(row["seed"])
        impacts_dict = impact_assessment(city, depth, row["seed"], params.river_level_m)
        impacts = ImpactAssessment.model_validate(impacts_dict)
        land_depth = depth[~channel_mask()]
        maximum_depth = float(land_depth.max()) if land_depth.size else 0.0
        return ScenarioState(id=row["id"], name=row["name"], seed=row["seed"], city_id=city.city.id,
            preset=row["preset"], status="paused" if replay else row["status"], tick=tick,
            epoch=row["epoch"], state_version=row["state_version"] if version is None else version,
            simulated_seconds=tick * STEP_SECONDS, grid_width=GRID_WIDTH, grid_height=GRID_HEIGHT,
            cell_size_m=CELL_SIZE_M, x_centers_m=grid_coordinates()[0], y_centers_m=grid_coordinates()[1],
            terrain_m=terrain_grid(row["seed"]).round(4).tolist(), depth_m=depth.round(4).tolist(),
            parameters=params, impacts=impacts, mass_balance=balance,
            maximum_depth_m=round(maximum_depth, 4),
            affected_buildings=sum(i.water_reaches_building for i in impacts.buildings),
            exposed_roads=sum(i.status in ("caution", "flooded") for i in impacts.roads),
            closed_bridges=sum(i.status == "closed" for i in impacts.bridges))

    def _envelope(self, db, row, state=None, *, replay=False):
        return ScenarioEnvelope(state=state or self._state(row, replay=replay), events=self._events(db, row["id"], row["epoch"]))

    def _begin(self, db, scenario_id: str, expected_version: int):
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT * FROM scenarios WHERE id=?", (scenario_id,)).fetchone()
        if row is None:
            db.rollback()
            raise ScenarioError(404, "Scenario does not exist.")
        if row["state_version"] != expected_version:
            db.rollback()
            raise ScenarioError(409, f"Scenario changed since version {expected_version}; current version is {row['state_version']}.")
        return row

    def update_parameters(self, scenario_id: str, request: ParameterUpdate):
        with self.lock, self._connect() as db:
            row = self._begin(db, scenario_id, request.expected_version)
            params = _params(row)
            changes = request.model_dump(exclude={"expected_version"}, exclude_none=True)
            if not changes:
                db.rollback()
                raise ScenarioError(422, "Provide at least one parameter to update.")
            updated = SimulationParameters.model_validate({**params.model_dump(), **changes})
            version = row["state_version"] + 1
            db.execute("UPDATE scenarios SET parameters_json=?,state_version=? WHERE id=?", (_json(updated.model_dump()), version, scenario_id))
            newrow = db.execute("SELECT * FROM scenarios WHERE id=?", (scenario_id,)).fetchone()
            for key, value in changes.items():
                event_type = {"rainfall_mm_h": "rainfall_changed", "river_level_m": "river_level_changed",
                              "drainage_effectiveness": "drainage_changed", "speed": "simulation_speed_changed"}[key]
                self._event(db, newrow, event_type, {"parameter": key, "value": value}, version=version)
            persist_agent_event(db,event_type="parameters_changed",scenario_id=scenario_id,scenario_epoch=row["epoch"],
                simulation_tick=newrow["tick"],state_version=version,source_module="scenario_store",infrastructure_revision=_infra_revision(db,scenario_id,row["epoch"]),
                payload={"changes":changes,"parameters":updated.model_dump()})
            db.commit()
            return self._envelope(db, newrow)

    def transition(self, scenario_id: str, expected_version: int, action: str):
        with self.lock, self._connect() as db:
            row = self._begin(db, scenario_id, expected_version)
            expected = {"start": "paused", "resume": "paused", "pause": "running"}[action]
            target = "running" if action in ("start", "resume") else "paused"
            if row["status"] != expected:
                db.rollback()
                raise ScenarioError(409, f"Cannot {action} a scenario that is {row['status']}.")
            version = row["state_version"] + 1
            db.execute("UPDATE scenarios SET status=?,state_version=? WHERE id=?", (target, version, scenario_id))
            newrow = db.execute("SELECT * FROM scenarios WHERE id=?", (scenario_id,)).fetchone()
            self._event(db, newrow, {"start": "simulation_started", "resume": "simulation_resumed", "pause": "simulation_paused"}[action], {}, version=version)
            result = self._envelope(db, newrow)
            db.commit()
            return result

    @staticmethod
    def _transition_events(old_impacts, new_impacts, row, db, tick, version):
        for group, label in (("buildings", "building_exposure_changed"), ("roads", None), ("bridges", None)):
            before = {i["entity_id"]: i for i in old_impacts[group]}
            for item in new_impacts[group]:
                prior = before[item["entity_id"]]
                key = "category" if group == "buildings" else "status"
                if item[key] != prior[key]:
                    event_type = label or (("road_reopened" if item["status"] == "open" else "road_flooded") if group == "roads"
                                           else ("bridge_closed" if item["status"] == "closed" else "bridge_reopened"))
                    ScenarioStore._event(db, row, event_type,
                        {"previous": prior[key], "current": item[key], "maximum_depth_m": item["max_depth_m"]},
                        [item["entity_id"]], tick=tick, version=version)

    def advance(self, scenario_id: str, request: AdvanceRequest):
        with self.lock, self._connect() as db:
            row = self._begin(db, scenario_id, request.expected_version)
            if row["status"] != "running" and not request.single_step:
                db.rollback()
                raise ScenarioError(409, "A paused scenario can only advance with single_step=true.")
            depth = self._depth(row)
            params = _params(row)
            balance = _balance(row).model_dump()
            version = row["state_version"]
            start_tick = row["tick"]
            city = generate_city(row["seed"])
            initial_impacts = impact_assessment(city, depth, row["seed"], params.river_level_m)
            for offset in range(1, request.steps + 1):
                previous_impacts = impact_assessment(city, depth, row["seed"], params.river_level_m)
                depth, delta = step(depth, row["seed"], params)
                for key in ("rainfall_m3", "river_in_m3", "river_out_m3", "drainage_m3"):
                    balance[key] += delta[key]
                balance["stored_m3"] = float(depth.sum() * CELL_SIZE_M**2)
                balance["balance_error_m3"] = balance["stored_m3"] - (balance["initial_m3"] + balance["rainfall_m3"] + balance["river_in_m3"] - balance["river_out_m3"] - balance["drainage_m3"])
                tick = start_tick + offset
                version += 1
                current_impacts = impact_assessment(city, depth, row["seed"], params.river_level_m)
                db.execute("UPDATE scenarios SET depth_blob=?,mass_json=?,tick=?,simulated_seconds=?,state_version=? WHERE id=?",
                    (zlib.compress(depth.tobytes()), _json(balance), tick, tick * STEP_SECONDS, version, scenario_id))
                current = db.execute("SELECT * FROM scenarios WHERE id=?", (scenario_id,)).fetchone()
                land_depth = depth[~channel_mask()]
                max_depth = float(land_depth.max()) if land_depth.size else 0.0
                changed = int(np.count_nonzero((depth > 1e-4) & ~channel_mask()))
                self._event(db, current, "simulation_tick", {"parameters": params.model_dump(), "maximum_depth_m": round(max_depth, 4)}, tick=tick, version=version)
                self._event(db, current, "flood_cell_updated", {"wet_cell_count": changed, "maximum_depth_m": round(max_depth, 4)}, tick=tick, version=version)
                self._transition_events(previous_impacts, current_impacts, current, db, tick, version)
                if tick % 12 == 0:
                    db.execute("INSERT OR REPLACE INTO checkpoints VALUES(?,?,?,?,?,?)",
                        (scenario_id, row["epoch"], tick, zlib.compress(depth.tobytes()), _json(balance), version))
            newrow = db.execute("SELECT * FROM scenarios WHERE id=?", (scenario_id,)).fetchone()
            changed_ids=[]
            for key in ("buildings","roads","bridges"):
                field="category" if key=="buildings" else "status"
                before={item["entity_id"]:item for item in initial_impacts[key]}
                changed_ids.extend(item["entity_id"] for item in current_impacts[key] if item[field]!=before[item["entity_id"]][field])
            persist_agent_event(db,event_type="simulation_advanced",scenario_id=scenario_id,scenario_epoch=row["epoch"],
                simulation_tick=newrow["tick"],state_version=newrow["state_version"],source_module="scenario_store",infrastructure_revision=_infra_revision(db,scenario_id,row["epoch"]),
                affected_entity_ids=sorted(changed_ids),payload={"from_tick":start_tick,"to_tick":newrow["tick"],
                "from_state_version":row["state_version"],"to_state_version":newrow["state_version"],
                "changed_exposure_or_access_ids":sorted(changed_ids),"parameters":params.model_dump()})
            result = self._envelope(db, newrow)
            db.commit()
            return result

    def reset(self, scenario_id: str, expected_version: int):
        with self.lock, self._connect() as db:
            row = self._begin(db, scenario_id, expected_version)
            params = SimulationParameters.model_validate(json.loads(row["initial_parameters_json"]))
            depth = initial_depth(row["seed"], params.river_level_m)
            initial_volume = float(depth.sum() * CELL_SIZE_M**2)
            balance = MassBalance(initial_m3=initial_volume, rainfall_m3=0, river_in_m3=0, river_out_m3=0,
                                  drainage_m3=0, stored_m3=initial_volume, balance_error_m3=0)
            epoch, version = row["epoch"] + 1, row["state_version"] + 1
            db.execute("UPDATE scenarios SET status='paused',tick=0,epoch=?,state_version=?,simulated_seconds=0,parameters_json=?,depth_blob=?,mass_json=? WHERE id=?",
                       (epoch, version, _json(params.model_dump()), zlib.compress(depth.tobytes()), _json(balance.model_dump()), scenario_id))
            newrow = db.execute("SELECT * FROM scenarios WHERE id=?", (scenario_id,)).fetchone()
            self._event(db, newrow, "simulation_reset", {"seed": row["seed"], "parameters": params.model_dump()}, version=version)
            persist_agent_event(db,event_type="scenario_reset",scenario_id=scenario_id,scenario_epoch=epoch,
                simulation_tick=0,state_version=version,source_module="scenario_store",infrastructure_revision=_infra_revision(db,scenario_id,epoch),
                payload={"previous_epoch":row["epoch"],"new_epoch":epoch})
            result = self._envelope(db, newrow)
            db.commit()
            return result

    def replay(self, scenario_id: str, tick: int):
        with self._connect() as db:
            row = db.execute("SELECT * FROM scenarios WHERE id=?", (scenario_id,)).fetchone()
            if row is None:
                raise ScenarioError(404, "Scenario does not exist.")
            if tick < 0 or tick > row["tick"]:
                raise ScenarioError(422, "Replay tick must be between zero and the current scenario tick.")
            checkpoint = db.execute("SELECT * FROM checkpoints WHERE scenario_id=? AND epoch=? AND tick<=? ORDER BY tick DESC LIMIT 1",
                                    (scenario_id, row["epoch"], tick)).fetchone()
            if checkpoint:
                depth = np.frombuffer(zlib.decompress(checkpoint["depth_blob"]), dtype=np.float64).reshape(GRID_HEIGHT, GRID_WIDTH).copy()
                balance = MassBalance.model_validate(json.loads(checkpoint["mass_json"]))
                start_tick, version = checkpoint["tick"], checkpoint["state_version"]
                checkpoint_step = db.execute(
                    "SELECT payload_json FROM events WHERE scenario_id=? AND epoch=? AND event_type='simulation_tick' AND tick=? ORDER BY sequence DESC LIMIT 1",
                    (scenario_id, row["epoch"], start_tick),
                ).fetchone()
                params = SimulationParameters.model_validate(json.loads(checkpoint_step["payload_json"])["parameters"]) if checkpoint_step else SimulationParameters.model_validate(json.loads(row["initial_parameters_json"]))
            else:
                initial_params = SimulationParameters.model_validate(json.loads(row["initial_parameters_json"]))
                depth = initial_depth(row["seed"], initial_params.river_level_m)
                initial_volume = float(depth.sum() * CELL_SIZE_M**2)
                balance = MassBalance(initial_m3=initial_volume, rainfall_m3=0, river_in_m3=0, river_out_m3=0, drainage_m3=0, stored_m3=initial_volume, balance_error_m3=0)
                start_tick, version = 0, 1
                params = initial_params
                if tick == 0:
                    updates = db.execute(
                        "SELECT event_type,payload_json FROM events WHERE scenario_id=? AND epoch=? AND tick=0 AND event_type IN ('rainfall_changed','river_level_changed','drainage_changed','simulation_speed_changed') ORDER BY sequence",
                        (scenario_id, row["epoch"]),
                    ).fetchall()
                    for update in updates:
                        payload = json.loads(update["payload_json"])
                        params = SimulationParameters.model_validate({**params.model_dump(), payload["parameter"]: payload["value"]})
            ticks = db.execute("SELECT * FROM events WHERE scenario_id=? AND epoch=? AND event_type='simulation_tick' AND tick>? AND tick<=? ORDER BY tick",
                               (scenario_id, row["epoch"], start_tick, tick)).fetchall()
            for event in ticks:
                payload = json.loads(event["payload_json"])
                params = SimulationParameters.model_validate(payload["parameters"])
                depth, delta = step(depth, row["seed"], params)
                b = balance.model_dump()
                for key in ("rainfall_m3", "river_in_m3", "river_out_m3", "drainage_m3"):
                    b[key] += delta[key]
                b["stored_m3"] = float(depth.sum() * CELL_SIZE_M**2)
                b["balance_error_m3"] = b["stored_m3"] - (b["initial_m3"] + b["rainfall_m3"] + b["river_in_m3"] - b["river_out_m3"] - b["drainage_m3"])
                balance = MassBalance.model_validate(b)
                version = event["state_version"]
            state = self._state(row, depth, params, balance, replay=True, tick=tick, version=version)
            return self._envelope(db, row, state, replay=True)

    def snapshots(self, scenario_id: str):
        with self._connect() as db:
            if db.execute("SELECT 1 FROM scenarios WHERE id=?", (scenario_id,)).fetchone() is None:
                raise ScenarioError(404, "Scenario does not exist.")
            rows = db.execute("SELECT tick,state_version FROM checkpoints WHERE scenario_id=? ORDER BY epoch DESC,tick DESC LIMIT 100", (scenario_id,)).fetchall()
            return [{"tick": r["tick"], "state_version": r["state_version"]} for r in rows]


store = ScenarioStore()
