"""Ledger writes.

Everything here is driven by what applications *report*. Nothing in this module
decides to move a GPU — it only records holder and state, and appends events.
This is the whole of the Phase 0 "write" surface, and it is deliberately
limited to register/report.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from shim.models import Application, Event, Gpu, Holding, utcnow
from shim.schemas import RegisterRequest, ReportRequest


def _upsert_gpu(
    session: Session,
    gpu_id: str,
    *,
    host: str | None = None,
    model: str | None = None,
    mem_mb: int | None = None,
    health: str | None = None,
) -> Gpu:
    gpu = session.get(Gpu, gpu_id)
    if gpu is None:
        gpu = Gpu(gpu_id=gpu_id, host=host or "unknown", health=health or "unknown")
        session.add(gpu)
    if host:
        gpu.host = host
    if model is not None:
        gpu.model = model
    if mem_mb is not None:
        gpu.mem_mb = mem_mb
    if health is not None:
        gpu.health = health
    gpu.last_seen = utcnow()
    return gpu


def _log(session: Session, kind: str, *, gpu_id: str | None = None,
         app_id: str | None = None, detail: str | None = None) -> None:
    session.add(Event(kind=kind, gpu_id=gpu_id, app_id=app_id, detail=detail))


def register(session: Session, req: RegisterRequest) -> int:
    """Record (or refresh) an application and the GPUs it declares it holds."""
    app = session.get(Application, req.app)
    if app is None:
        app = Application(app_id=req.app, name=req.name or req.app)
        session.add(app)
    app.name = req.name or app.name or req.app
    app.endpoint = req.endpoint
    app.version = req.version
    app.last_seen = utcnow()

    for gpu_id in req.holds:
        _upsert_gpu(session, gpu_id)
        _ensure_holding(session, gpu_id=gpu_id, app_id=req.app, state="held",
                        util=None, work_id=None)

    _log(session, "register", app_id=req.app, detail=f"holds={len(req.holds)}")
    session.commit()
    return len(req.holds)


def report(session: Session, req: ReportRequest) -> int:
    """Apply a heartbeat/state report from one application."""
    app = session.get(Application, req.app)
    if app is None:
        # A report from an unregistered app still gets recorded; the reconciler
        # will not punish it. We auto-create a minimal application row.
        app = Application(app_id=req.app, name=req.app)
        session.add(app)
    app.last_seen = utcnow()

    for g in req.gpus:
        _upsert_gpu(
            session, g.gpu_id, host=g.host, model=g.model, mem_mb=g.mem_mb, health=g.health
        )
        if g.state == "free":
            _release_holding(session, gpu_id=g.gpu_id, app_id=req.app)
        else:  # "held" — validated upstream to be the only other Phase 0 state
            _ensure_holding(
                session, gpu_id=g.gpu_id, app_id=req.app,
                state=g.state, util=g.util, work_id=g.work_id,
            )

    _log(session, "report", app_id=req.app, detail=f"gpus={len(req.gpus)}")
    session.commit()
    return len(req.gpus)


def _ensure_holding(session: Session, *, gpu_id: str, app_id: str, state: str,
                    util: int | None, work_id: str | None) -> None:
    holding = session.scalar(select(Holding).where(Holding.gpu_id == gpu_id))
    if holding is None:
        session.add(
            Holding(gpu_id=gpu_id, app_id=app_id, state=state, util=util, work_id=work_id)
        )
        _log(session, "hold", gpu_id=gpu_id, app_id=app_id, detail=state)
        return

    if holding.app_id != app_id:
        # Two apps claim the same GPU. Phase 0 does NOT arbitrate — it records
        # the latest reporter and leaves the conflict for the reconciler to
        # surface. It never kills or moves anything.
        _log(session, "conflict", gpu_id=gpu_id, app_id=app_id,
             detail=f"claimed_over={holding.app_id}")
        holding.app_id = app_id
        holding.since = utcnow()
    holding.state = state
    holding.util = util
    holding.work_id = work_id


def _release_holding(session: Session, *, gpu_id: str, app_id: str) -> None:
    holding = session.scalar(select(Holding).where(Holding.gpu_id == gpu_id))
    if holding is None:
        return
    # Only the current holder's own "free" report releases the GPU.
    if holding.app_id == app_id:
        session.delete(holding)
        _log(session, "free", gpu_id=gpu_id, app_id=app_id)
