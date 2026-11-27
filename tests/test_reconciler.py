from __future__ import annotations

from datetime import timedelta

from shim.ledger import service
from shim.ledger.reconciler import find_conflicts
from shim.models import Application, Gpu, utcnow
from shim.schemas import RegisterRequest, ReportRequest


def test_unclaimed_gpu_flagged(session):
    # A GPU in inventory that nobody holds.
    session.add(Gpu(gpu_id="GPU-x", host="h1", health="ok"))
    session.commit()
    conflicts = find_conflicts(session)
    assert any(c.kind == "unclaimed" and c.gpu_id == "GPU-x" for c in conflicts)


def test_double_claim_records_conflict_event_without_moving(session):
    service.register(session, RegisterRequest(app="flamejob", holds=["GPU-a"]))
    # A different app claims the same GPU. Phase 0 records the re-claim but the
    # reconciler/ledger never kills or arbitrates — latest reporter is recorded.
    service.report(
        session,
        ReportRequest(app="llama", gpus=[{"gpu_id": "GPU-a", "state": "held"}]),
    )
    from sqlalchemy import select

    from shim.models import Event, Holding

    holding = session.scalar(select(Holding).where(Holding.gpu_id == "GPU-a"))
    assert holding.app_id == "llama"  # latest reporter recorded
    conflict_events = session.scalars(select(Event).where(Event.kind == "conflict")).all()
    assert any(e.gpu_id == "GPU-a" for e in conflict_events)


def test_stale_holder_flagged(session):
    service.register(session, RegisterRequest(app="flamejob", holds=["GPU-a"]))
    app = session.get(Application, "flamejob")
    app.last_seen = utcnow() - timedelta(hours=1)
    session.commit()
    conflicts = find_conflicts(session)
    assert any(c.kind == "stale_holder" and c.gpu_id == "GPU-a" for c in conflicts)
