from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from shim.models import PHASE0_STATES

# --- Contract: application -> shim (read side only in Phase 0) ---------------


class RegisterRequest(BaseModel):
    """POST /register — { app, endpoint, version, holds: [gpu_id] }."""

    app: str
    name: str | None = None
    endpoint: str | None = None
    version: str | None = None
    holds: list[str] = Field(default_factory=list)


class ReportedGpu(BaseModel):
    gpu_id: str
    state: str
    util: int | None = None
    work_id: str | None = None
    # Optional inventory hints an app may include for GPUs it owns the host of.
    host: str | None = None
    model: str | None = None
    mem_mb: int | None = None
    health: str | None = None

    @field_validator("state")
    @classmethod
    def _phase0_state_only(cls, v: str) -> str:
        if v not in PHASE0_STATES:
            raise ValueError(
                f"state {v!r} not allowed in Phase 0; expected one of {sorted(PHASE0_STATES)}"
            )
        return v


class ReportRequest(BaseModel):
    """POST /report — { app, gpus: [{ gpu_id, state, util, work_id? }] }."""

    app: str
    gpus: list[ReportedGpu] = Field(default_factory=list)


class PingResponse(BaseModel):
    status: str = "ok"
    version: str
    # Phase 0 never signals. Advertised so clients can assert the safe mode.
    can_move_gpus: bool = False


class Ack(BaseModel):
    accepted: bool = True
    app: str
    count: int = 0


# --- Read-only views ---------------------------------------------------------


class GpuView(BaseModel):
    gpu_id: str
    host: str
    model: str | None
    mem_mb: int | None
    health: str
    holder: str | None
    state: str
    util: int | None
    last_seen: datetime


class HoldingView(BaseModel):
    gpu_id: str
    app_id: str
    state: str
    util: int | None
    work_id: str | None
    since: datetime


class EventView(BaseModel):
    ts: datetime
    kind: str
    gpu_id: str | None
    app_id: str | None
    detail: str | None


class ConflictView(BaseModel):
    kind: str  # "double_claim" | "unclaimed" | "stale_holder"
    gpu_id: str
    detail: str


class PoolSummary(BaseModel):
    total_gpus: int
    held: int
    free: int
    applications: int
    conflicts: list[ConflictView]
