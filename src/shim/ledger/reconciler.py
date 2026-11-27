"""Reconciler — observation only.

It compares what apps have reported against the ledger and flags anomalies:
  * double_claim — (should be prevented by the single-holding constraint, but
    a recent re-claim is surfaced from the event log)
  * unclaimed    — a GPU in inventory that no app holds
  * stale_holder — a holding whose owning app hasn't reported within the window

It returns findings. It never changes a holding or signals an app.
"""

from __future__ import annotations

from datetime import UTC, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from shim.config import get_settings
from shim.models import Application, Gpu, Holding, utcnow
from shim.schemas import ConflictView


def find_conflicts(session: Session) -> list[ConflictView]:
    settings = get_settings()
    out: list[ConflictView] = []

    held_gpu_ids = set(session.scalars(select(Holding.gpu_id)).all())

    # Unclaimed: in inventory but with no holding row.
    for gpu_id in session.scalars(select(Gpu.gpu_id)).all():
        if gpu_id not in held_gpu_ids:
            out.append(
                ConflictView(
                    kind="unclaimed", gpu_id=gpu_id, detail="no application holds this GPU"
                )
            )

    # Stale holder: the owning app hasn't reported recently.
    cutoff = utcnow() - timedelta(seconds=settings.heartbeat_stale_seconds)
    rows = session.execute(
        select(Holding, Application).join(Application, Holding.app_id == Application.app_id)
    ).all()
    for holding, app in rows:
        last_seen = app.last_seen
        if last_seen is not None and last_seen.tzinfo is None:
            # Normalise naive timestamps (SQLite) to compare against aware cutoff.

            last_seen = last_seen.replace(tzinfo=UTC)
        if last_seen is not None and last_seen < cutoff:
            out.append(
                ConflictView(
                    kind="stale_holder",
                    gpu_id=holding.gpu_id,
                    detail=f"holder {app.app_id} last reported {app.last_seen.isoformat()}",
                )
            )

    return out
