"""The elasticity contract, read side only (Phase 0).

Implemented here: POST /register, POST /report, POST /ping.

Deliberately NOT implemented: POST /grant and POST /reclaim. Those are Phase 1,
when the broker is allowed to signal apps to move GPUs. Keeping them absent is
the Phase 0 safety guarantee.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from shim import __version__
from shim.db import get_session
from shim.ledger import service
from shim.schemas import Ack, PingResponse, RegisterRequest, ReportRequest

router = APIRouter(tags=["contract"])


@router.post("/register", response_model=Ack)
def register(req: RegisterRequest, session: Session = Depends(get_session)) -> Ack:
    count = service.register(session, req)
    return Ack(accepted=True, app=req.app, count=count)


@router.post("/report", response_model=Ack)
def report(req: ReportRequest, session: Session = Depends(get_session)) -> Ack:
    count = service.report(session, req)
    return Ack(accepted=True, app=req.app, count=count)


@router.post("/ping", response_model=PingResponse)
def ping() -> PingResponse:
    return PingResponse(version=__version__, can_move_gpus=False)
