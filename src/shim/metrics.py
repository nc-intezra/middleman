"""Prometheus metrics, computed from the ledger at scrape time."""

from __future__ import annotations

from prometheus_client import CollectorRegistry, Gauge, generate_latest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from shim.ledger.reconciler import find_conflicts
from shim.models import Application, Gpu, Holding


def render_metrics(session: Session) -> bytes:
    registry = CollectorRegistry()

    g_total = Gauge("shim_gpus_total", "GPUs in the pool", registry=registry)
    g_held = Gauge("shim_gpus_held", "GPUs currently held", registry=registry)
    g_free = Gauge("shim_gpus_free", "GPUs with no holder", registry=registry)
    g_apps = Gauge("shim_applications_total", "Registered applications", registry=registry)
    g_conflicts = Gauge(
        "shim_conflicts_total", "Reconciler findings", ["kind"], registry=registry
    )

    total = session.scalar(select(func.count()).select_from(Gpu)) or 0
    held = session.scalar(select(func.count()).select_from(Holding)) or 0
    apps = session.scalar(select(func.count()).select_from(Application)) or 0

    g_total.set(total)
    g_held.set(held)
    g_free.set(max(total - held, 0))
    g_apps.set(apps)

    counts: dict[str, int] = {}
    for c in find_conflicts(session):
        counts[c.kind] = counts.get(c.kind, 0) + 1
    for kind in ("unclaimed", "stale_holder", "double_claim"):
        g_conflicts.labels(kind=kind).set(counts.get(kind, 0))

    return generate_latest(registry)
