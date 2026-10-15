"""Typed durable event contracts shared by simulation producers and agents."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from time import perf_counter


class AgentEventEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str
    event_type: str
    scenario_id: str
    scenario_epoch: int
    simulation_tick: int
    simulation_state_version: int
    infrastructure_revision: int | None = None
    created_at_utc: datetime
    source_module: str
    affected_entity_ids: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str
    causation_event_id: str | None = None
    outbox_insert_ms: float | None = None


AgentStatus = Literal["waiting", "running", "completed", "skipped", "failed", "superseded", "degraded"]


class AgentDefinition(BaseModel):
    name: str
    title: str
    responsibility: str
    position: int


class AgentRunRecord(BaseModel):
    run_id: str
    event_id: str
    correlation_id: str
    scenario_id: str
    scenario_epoch: int
    simulation_state_version: int
    infrastructure_revision: int | None
    agent_name: str
    status: AgentStatus
    started_at_utc: datetime | None = None
    completed_at_utc: datetime | None = None
    duration_ms: float | None = None
    input_hash: str
    input_snapshot_ref: str
    output_summary: dict[str, Any] = Field(default_factory=dict)
    numerical_evidence: dict[str, Any] = Field(default_factory=dict)
    proposed_action: str | None = None
    explanation: str = ""
    error: str | None = None
    attempt: int = 0


class AgentTrace(BaseModel):
    trace_id: str
    event_id: str
    correlation_id: str
    scenario_id: str
    scenario_epoch: int
    simulation_state_version: int
    infrastructure_revision: int | None
    status: Literal["completed", "failed", "superseded", "degraded"]
    plan_id: str | None = None
    summary: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    created_at_utc: datetime


class AgentTraceDetail(BaseModel):
    event: AgentEventEnvelope
    event_status: Literal["pending", "processing", "completed", "failed", "superseded", "degraded"]
    attempts: int
    agents: list[AgentRunRecord]
    trace: AgentTrace | None = None
    related_plan: dict[str, Any] | None = None


class AgentDashboard(BaseModel):
    scenario_id: str
    scenario_epoch: int
    simulation_state_version: int
    infrastructure_revision: int
    definitions: list[AgentDefinition]
    latest_runs: list[AgentRunRecord]
    latest_trace: AgentTrace | None = None
    pending_events: int = 0
    available_ground_units: int = 0
    reserved_ground_units: list[str] = Field(default_factory=list)
    commander_action_required: bool = False
    approved_route_review_required: bool = False
    approved_route_review_plan_ids: list[str] = Field(default_factory=list)
    manual_closure_road_ids: list[str] = Field(default_factory=list)


class AgentEventAccepted(BaseModel):
    event_id: str
    status: str
    scenario_id: str
    scenario_epoch: int
    simulation_tick: int
    simulation_state_version: int


def ensure_agent_event_table(db) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS agent_event_outbox (
        event_id TEXT PRIMARY KEY, scenario_id TEXT NOT NULL, scenario_epoch INTEGER NOT NULL,
        simulation_state_version INTEGER NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
        attempts INTEGER NOT NULL DEFAULT 0, envelope_json TEXT NOT NULL, error TEXT,
        created_at_utc TEXT NOT NULL, processed_at_utc TEXT
    )""")
    db.execute("CREATE INDEX IF NOT EXISTS agent_outbox_pending ON agent_event_outbox(status,created_at_utc)")


def persist_agent_event(
    db,
    *,
    event_type: str,
    scenario_id: str,
    scenario_epoch: int,
    simulation_tick: int,
    state_version: int,
    source_module: str,
    payload: dict[str, Any] | None = None,
    affected_entity_ids: list[str] | None = None,
    infrastructure_revision: int | None = None,
    correlation_id: str | None = None,
    causation_event_id: str | None = None,
    event_id: str | None = None,
) -> AgentEventEnvelope:
    from uuid import uuid4

    ensure_agent_event_table(db)
    event_id = event_id or uuid4().hex
    correlation_id = correlation_id or event_id
    started=perf_counter()
    envelope = AgentEventEnvelope(
        event_id=event_id,
        event_type=event_type,
        scenario_id=scenario_id,
        scenario_epoch=scenario_epoch,
        simulation_tick=simulation_tick,
        simulation_state_version=state_version,
        infrastructure_revision=infrastructure_revision,
        created_at_utc=datetime.now(timezone.utc),
        source_module=source_module,
        affected_entity_ids=affected_entity_ids or [],
        payload=payload or {},
        correlation_id=correlation_id,
        causation_event_id=causation_event_id,
    )
    db.execute(
        "INSERT OR IGNORE INTO agent_event_outbox(event_id,scenario_id,scenario_epoch,simulation_state_version,status,attempts,envelope_json,created_at_utc) VALUES(?,?,?,?, 'pending',0,?,?)",
        (event_id, scenario_id, scenario_epoch, state_version, envelope.model_dump_json(), envelope.created_at_utc.isoformat()),
    )
    envelope.outbox_insert_ms=round((perf_counter()-started)*1000,3)
    db.execute("UPDATE agent_event_outbox SET envelope_json=? WHERE event_id=?",(envelope.model_dump_json(),event_id))
    return envelope


def canonical_payload(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
