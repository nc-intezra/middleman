"""FastAPI application factory for the broker."""

from __future__ import annotations

from fastapi import FastAPI

from shim import __version__
from shim.api import contract, views


def create_app() -> FastAPI:
    app = FastAPI(
        title="GPU Workload Shim (broker)",
        version=__version__,
        summary="Phase 0: inventory + ledger, read-only. No code path moves a GPU.",
    )
    app.include_router(contract.router)
    app.include_router(views.router)

    @app.get("/healthz", tags=["ops"])
    def healthz() -> dict[str, str]:
        return {"status": "ok", "version": __version__, "phase": "0"}

    return app


app = create_app()
