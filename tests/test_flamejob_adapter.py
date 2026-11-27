from __future__ import annotations

from adapters.flamejob.client import AgentGpu, FlamejobReporter


def test_adapter_register_and_report_through_broker(client):
    # Drive the broker directly with the same payloads the adapter builds, so we
    # assert the wire contract the report-only client depends on.
    rep = FlamejobReporter("http://broker")
    reg_payload = {
        "app": rep.app_id,
        "name": rep.name,
        "endpoint": "http://flamejob:9000",
        "version": rep.version,
        "holds": ["GPU-a"],
    }
    assert client.post("/register", json=reg_payload).status_code == 200

    gpus = [AgentGpu(gpu_id="GPU-a", util=97, work_id="job-1/chunk-3")]
    report_payload = {
        "app": rep.app_id,
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
    assert client.post("/report", json=report_payload).status_code == 200

    holders = {g["gpu_id"]: g["holder"] for g in client.get("/gpus").json()}
    assert holders["GPU-a"] == "flamejob"
    rep.close()
