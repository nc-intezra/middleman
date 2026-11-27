# flamejob adapter (report-only, Phase 0)

flamejob is the reference yielder — a distributed hashcat coordinator for
**authorized** GPU password auditing. In Phase 0 this adapter is **report-only**:
it tells the broker which GPUs flamejob's agents hold and changes nothing about
how flamejob runs.

- Calls only `POST /register` and `POST /report`.
- Never receives or acts on `grant`/`reclaim` — that is Phase 1.
- Intended to run as a sidecar or cron beside `flamejob-server`.

```python
from adapters.flamejob.client import FlamejobReporter, AgentGpu

with FlamejobReporter("http://broker:8080", version="1.4.0") as rep:
    rep.register(holds=["GPU-aaa", "GPU-bbb"], endpoint="http://flamejob:9000")

    # on each heartbeat:
    rep.report([
        AgentGpu(gpu_id="GPU-aaa", util=97, work_id="job-42/chunk-7"),
        AgentGpu(gpu_id="GPU-bbb", util=95, work_id="job-42/chunk-8"),
    ])

    # when flamejob finishes with a GPU:
    rep.report_freed(["GPU-bbb"])
```
