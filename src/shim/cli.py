"""`shim` CLI — the read-only pool view.

    shim gpus        # GPU, host, model, holder, state, util
    shim holdings    # who holds what
    shim pool        # summary + reconciler findings
    shim discover    # NVML discovery on this host (prints only; writes nothing)
"""

from __future__ import annotations

import typer

from shim.api.views import _gpu_views
from shim.db import SessionLocal
from shim.inventory.nvml import discover_local_gpus
from shim.ledger.reconciler import find_conflicts
from shim.models import Holding

app = typer.Typer(help="GPU Workload Shim — read-only pool view (Phase 0).")


@app.command()
def gpus() -> None:
    """Show every GPU in the pool and who holds it."""
    with SessionLocal() as session:
        rows = _gpu_views(session)
    if not rows:
        typer.echo("(no GPUs in the pool yet)")
        return
    typer.echo(f"{'GPU':<32} {'HOST':<16} {'MODEL':<20} {'HOLDER':<16} {'STATE':<8} UTIL")
    for r in rows:
        typer.echo(
            f"{r.gpu_id:<32} {r.host:<16} {(r.model or '-'):<20} "
            f"{(r.holder or '-'):<16} {r.state:<8} {r.util if r.util is not None else '-'}"
        )


@app.command()
def holdings() -> None:
    """Show current holdings."""
    with SessionLocal() as session:
        rows = session.query(Holding).order_by(Holding.app_id).all()
        data = [(h.app_id, h.gpu_id, h.state, h.work_id or "-") for h in rows]
    if not data:
        typer.echo("(nothing held)")
        return
    typer.echo(f"{'APP':<16} {'GPU':<32} {'STATE':<8} WORK")
    for app_id, gpu_id, state, work in data:
        typer.echo(f"{app_id:<16} {gpu_id:<32} {state:<8} {work}")


@app.command()
def pool() -> None:
    """Summary plus reconciler findings."""
    with SessionLocal() as session:
        conflicts = find_conflicts(session)
    if not conflicts:
        typer.echo("No conflicts.")
        return
    typer.echo("Conflicts:")
    for c in conflicts:
        typer.echo(f"  [{c.kind}] {c.gpu_id}: {c.detail}")


@app.command()
def discover() -> None:
    """Run NVML discovery on this host and print it. Writes nothing."""
    found = discover_local_gpus()
    if not found:
        typer.echo("(no local NVIDIA GPUs discoverable; NVML unavailable or none present)")
        return
    for g in found:
        typer.echo(f"{g.gpu_id}\t{g.host}\t{g.model}\t{g.mem_mb}MB\t{g.health}")


if __name__ == "__main__":
    app()
