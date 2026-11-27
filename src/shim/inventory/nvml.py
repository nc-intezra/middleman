"""Inventory discovery via NVML (DCGM is the richer alternative in prod).

This reads GPU facts only — id, host, model, memory, health. It never changes
anything on the device. When no NVIDIA driver / library is present (CI, a dev
laptop, a host an app owns and reports for itself) it returns an empty list
rather than failing; those GPUs reach the ledger through the apps' Report calls.
"""

from __future__ import annotations

import socket
from dataclasses import dataclass


@dataclass
class DiscoveredGpu:
    gpu_id: str
    host: str
    model: str | None
    mem_mb: int | None
    health: str


def discover_local_gpus() -> list[DiscoveredGpu]:
    """Discover GPUs on the local host via NVML. Empty list if unavailable."""
    try:
        import pynvml  # type: ignore
    except Exception:
        return []

    host = socket.gethostname()
    out: list[DiscoveredGpu] = []
    try:
        pynvml.nvmlInit()
    except Exception:
        return []

    try:
        count = pynvml.nvmlDeviceGetCount()
        for i in range(count):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            uuid = _decode(pynvml.nvmlDeviceGetUUID(handle))
            name = _decode(pynvml.nvmlDeviceGetName(handle))
            mem = pynvml.nvmlDeviceGetMemoryInfo(handle)
            health = _health(pynvml, handle)
            out.append(
                DiscoveredGpu(
                    gpu_id=uuid or f"{host}:{i}",
                    host=host,
                    model=name,
                    mem_mb=int(mem.total / (1024 * 1024)) if mem else None,
                    health=health,
                )
            )
    except Exception:
        return out
    finally:
        try:
            pynvml.nvmlShutdown()
        except Exception:
            pass
    return out


def _decode(v: object) -> str | None:
    if isinstance(v, bytes):
        return v.decode("utf-8", "replace")
    if v is None:
        return None
    return str(v)


def _health(pynvml, handle) -> str:
    try:
        # A conservative health signal: any XID/ECC concern -> "degraded".
        ecc = pynvml.nvmlDeviceGetTotalEccErrors(
            handle,
            pynvml.NVML_MEMORY_ERROR_TYPE_UNCORRECTED,
            pynvml.NVML_VOLATILE_ECC,
        )
        return "degraded" if ecc else "ok"
    except Exception:
        return "ok"
