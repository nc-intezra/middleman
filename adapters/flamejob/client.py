"""flamejob report-only adapter (Phase 0).

flamejob is the reference yielder: a distributed hashcat coordinator whose agents
hold GPUs for authorized password-auditing work. In Phase 0 the adapter does one
thing only — it tells the broker which GPUs flamejob's agents currently hold, so
those GPUs show as held-by-flamejob in the pool view.

There is NO behaviour change to flamejob. This client only calls /register and
/report. It never receives or acts on grant/reclaim (that is Phase 1).

Typical use: run this as a sidecar/cron next to flamejob-server, feeding it the
GPU ids the coordinator currently has agents on.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx


@dataclass
class AgentGpu:
    """A GPU one of flamejob's agents is using."""

    gpu_id: str
    util: int | None = None
    work_id: str | None = None  # e.g. the flamejob job/keyspace-chunk id
    host: str | None = None
    model: str | None = None
    mem_mb: int | None = None


class FlamejobReporter:
    def __init__(
        self,
        broker_url: str,
        app_id: str = "flamejob",
        name: str = "flamejob (hashcat coordinator)",
        version: str | None = None,
        timeout: float = 5.0,
    ) -> None:
        self.broker_url = broker_url.rstrip("/")
        self.app_id = app_id
        self.name = name
        self.version = version
        self._client = httpx.Client(timeout=timeout)

    def register(self, holds: list[str], endpoint: str | None = None) -> dict:
        """Announce flamejob and the GPUs it holds on startup / on change."""
        payload = {
            "app": self.app_id,
            "name": self.name,
            "endpoint": endpoint,
            "version": self.version,
            "holds": holds,
        }
        resp = self._client.post(f"{self.broker_url}/register", json=payload)
        resp.raise_for_status()
        return resp.json()

    def report(self, gpus: list[AgentGpu]) -> dict:
        """Heartbeat: report the GPUs flamejob's agents currently hold.

        State is always 'held' here — Phase 0 only distinguishes free/held, and a
        GPU flamejob no longer uses is reported 'free' so the broker releases it.
        """
        payload = {
            "app": self.app_id,
            "gpus": [
                {
                    "gpu_id": g.gpu_id,
                    "state": "held",
                    "util": g.util,
                    "work_id": g.work_id,
                    "host": g.host,
                    "model": g.model,
                    "mem_mb": g.mem_mb,
                }
                for g in gpus
            ],
        }
        resp = self._client.post(f"{self.broker_url}/report", json=payload)
        resp.raise_for_status()
        return resp.json()

    def report_freed(self, gpu_ids: list[str]) -> dict:
        """Report GPUs flamejob has stopped using, so the broker marks them free."""
        payload = {
            "app": self.app_id,
            "gpus": [{"gpu_id": g, "state": "free"} for g in gpu_ids],
        }
        resp = self._client.post(f"{self.broker_url}/report", json=payload)
        resp.raise_for_status()
        return resp.json()

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> FlamejobReporter:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
