"""Read-only observability endpoints — the Phase 0 pool view."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from shim.db import get_session
from shim.ledger.reconciler import find_conflicts
from shim.metrics import render_metrics
from shim.models import Application, Event, Gpu, Holding
from shim.schemas import (
    EventView,
    GpuView,
    HoldingView,
    PoolSummary,
)

router = APIRouter(tags=["views"])


def _gpu_views(session: Session) -> list[GpuView]:
    holdings = {h.gpu_id: h for h in session.scalars(select(Holding)).all()}
    out: list[GpuView] = []
    for gpu in session.scalars(select(Gpu).order_by(Gpu.host, Gpu.gpu_id)).all():
        h = holdings.get(gpu.gpu_id)
        out.append(
            GpuView(
                gpu_id=gpu.gpu_id,
                host=gpu.host,
                model=gpu.model,
                mem_mb=gpu.mem_mb,
                health=gpu.health,
                holder=h.app_id if h else None,
                state=h.state if h else "free",
                util=h.util if h else None,
                last_seen=gpu.last_seen,
            )
        )
    return out


@router.get("/gpus", response_model=list[GpuView])
def list_gpus(session: Session = Depends(get_session)) -> list[GpuView]:
    return _gpu_views(session)


@router.get("/holdings", response_model=list[HoldingView])
def list_holdings(session: Session = Depends(get_session)) -> list[HoldingView]:
    return [
        HoldingView(
            gpu_id=h.gpu_id, app_id=h.app_id, state=h.state,
            util=h.util, work_id=h.work_id, since=h.since,
        )
        for h in session.scalars(select(Holding).order_by(Holding.app_id)).all()
    ]


@router.get("/events", response_model=list[EventView])
def list_events(limit: int = 100, session: Session = Depends(get_session)) -> list[EventView]:
    rows = session.scalars(select(Event).order_by(Event.ts.desc()).limit(limit)).all()
    return [
        EventView(ts=e.ts, kind=e.kind, gpu_id=e.gpu_id, app_id=e.app_id, detail=e.detail)
        for e in rows
    ]


@router.get("/pool", response_model=PoolSummary)
def pool_summary(session: Session = Depends(get_session)) -> PoolSummary:
    total = session.scalar(select(func.count()).select_from(Gpu)) or 0
    held = session.scalar(select(func.count()).select_from(Holding)) or 0
    apps = session.scalar(select(func.count()).select_from(Application)) or 0
    conflicts = find_conflicts(session)
    return PoolSummary(
        total_gpus=total,
        held=held,
        free=max(total - held, 0),
        applications=apps,
        conflicts=conflicts,
    )


@router.get("/metrics")
def metrics(session: Session = Depends(get_session)) -> PlainTextResponse:
    return PlainTextResponse(render_metrics(session), media_type="text/plain; version=0.0.4")
