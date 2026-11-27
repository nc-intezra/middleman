# middleman — GPU Workload Shim (broker)

`middleman` is a **GPU compute broker**. All GPUs form one shared pool, and every GPU
can serve either class of application — hashcat auditing (flamejob) or AI inference and
training (llama-server). The broker owns exactly one thing: **who holds which GPUs**, and
it arbitrates that.

It does **not** run jobs, schedule tasks, or migrate processes. Each application keeps its
own control plane. When an admin decides compute should move, the broker (in later phases)
sends an application one of two messages and lets the application act:

- **Grant** — "these GPUs are now yours."
- **Reclaim** — "save your work and release these GPUs by time T."

The authoritative design is the architecture doc *GPU Workload Shim: Architecture v0.1*.

---

## This repository implements **Phase 0** only

Phase 0 builds the broker's spine with **no live reclaim**: discover the GPUs, hold the
ledger, let apps register and report, and show who holds what. Crucially, **no code path
can move a GPU**, so Phase 0 is safe to run in production alongside the apps.

### In scope (Phase 0)

- **Inventory** — discover every GPU with its host, model, memory, and health.
- **Allocation ledger** — the source-of-truth record of holder and state per GPU.
- **Contract, read side only** — `Register` and `Report` from each app. No `Grant`/`Reclaim`.
- **Read-only observability** — a pool view (CLI + table) plus metrics.
- **flamejob adapter (report-only)** — flamejob tells the broker what GPUs it holds.

### Explicitly out of scope (deferred)

- Sending `Grant`/`Reclaim`, or **any** admin action that moves a GPU (Phase 1).
- Policy: floors, ceilings, priority, force (Phase 1–2).
- The llama-server adapter (Phase 2).

> **Safety invariant:** there is no `/grant` or `/reclaim` endpoint and no code path that
> changes what an application is running. The broker only *records* what apps report.

---

## Stack choice (noted because the repo started empty)

| Concern | Choice | Why |
|---|---|---|
| Language | Python 3.11+ | NVML/DCGM have first-class Python bindings (`pynvml`), matching the inventory collector. |
| API | FastAPI + Pydantic | Typed request/response models map directly onto the JSON wire contract; auto OpenAPI for the read endpoints. |
| Store | PostgreSQL via SQLAlchemy 2.0 | The ledger is the source of truth; append-only `event` table needs a real RDBMS. |
| Migrations | Alembic | Versioned schema; Phase 1 adds states/columns without a rewrite. |
| CLI | Typer | `shim gpus`, `shim holdings`. |
| Metrics | `prometheus_client` | `/metrics` scrape endpoint. |

Models stay DB-agnostic (enum values are plain strings, not a PG `ENUM`) so the test suite
runs on SQLite with no Postgres required.

This is a scaffold: endpoints and the ledger are real and exercised by tests; the NVML
collector falls back gracefully when no GPUs/driver are present.

---

## Layout

```
src/shim/
  config.py          settings (DATABASE_URL, etc.)
  db.py              engine/session
  models.py          gpu / application / holding / event  (state ∈ {free, held})
  schemas.py         wire contract models (register / report / ping)
  main.py            FastAPI app factory
  api/contract.py    POST /register, /report, /ping   (read side of the contract)
  api/views.py       GET /gpus, /holdings, /events, /pool  (read-only)
  ledger/service.py  ledger writes from register/report
  ledger/reconciler.py  flags conflicts (two holders) and unclaimed GPUs
  inventory/nvml.py  NVML/DCGM discovery, graceful fallback
  metrics.py         prometheus metrics + /metrics
  cli.py             `shim` CLI
adapters/flamejob/   report-only client (no behaviour change to flamejob)
migrations/          Alembic
tests/
```

## Running locally

```bash
# 1. start Postgres + the broker
docker compose up --build

# 2. apply the schema
docker compose exec broker alembic upgrade head

# 3. look at the pool
docker compose exec broker shim gpus
docker compose exec broker shim holdings
```

Or without Docker:

```bash
pip install -e ".[dev]"
export DATABASE_URL=postgresql+psycopg://shim:shim@localhost:5432/shim
alembic upgrade head
uvicorn shim.main:app --reload
```

Run the tests (SQLite, no Postgres needed):

```bash
pip install -e ".[dev]"
pytest
```
