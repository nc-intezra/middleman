from __future__ import annotations


def test_ping_advertises_safe_mode(client):
    r = client.post("/ping")
    assert r.status_code == 200
    body = r.json()
    assert body["can_move_gpus"] is False


def test_no_grant_or_reclaim_endpoints(client):
    # The Phase 0 safety guarantee: these must not exist.
    assert client.post("/grant", json={}).status_code == 404
    assert client.post("/reclaim", json={}).status_code == 404


def test_register_then_report_shows_held(client):
    client.post(
        "/register",
        json={"app": "flamejob", "name": "flamejob", "holds": ["GPU-a", "GPU-b"]},
    )
    r = client.post(
        "/report",
        json={
            "app": "flamejob",
            "gpus": [
                {"gpu_id": "GPU-a", "state": "held", "util": 99, "work_id": "job-1"},
                {"gpu_id": "GPU-b", "state": "held", "util": 50},
            ],
        },
    )
    assert r.status_code == 200
    assert r.json()["count"] == 2

    gpus = {g["gpu_id"]: g for g in client.get("/gpus").json()}
    assert gpus["GPU-a"]["holder"] == "flamejob"
    assert gpus["GPU-a"]["state"] == "held"
    assert gpus["GPU-a"]["util"] == 99


def test_report_free_releases(client):
    client.post("/register", json={"app": "flamejob", "holds": ["GPU-a"]})
    client.post("/report", json={"app": "flamejob", "gpus": [{"gpu_id": "GPU-a", "state": "held"}]})
    client.post("/report", json={"app": "flamejob", "gpus": [{"gpu_id": "GPU-a", "state": "free"}]})

    gpus = {g["gpu_id"]: g for g in client.get("/gpus").json()}
    assert gpus["GPU-a"]["holder"] is None
    assert gpus["GPU-a"]["state"] == "free"


def test_phase0_rejects_non_phase0_state(client):
    # 'granted' belongs to Phase 1; the contract must reject it now.
    r = client.post(
        "/report",
        json={"app": "flamejob", "gpus": [{"gpu_id": "GPU-a", "state": "granted"}]},
    )
    assert r.status_code == 422


def test_events_are_logged(client):
    client.post("/register", json={"app": "flamejob", "holds": ["GPU-a"]})
    kinds = {e["kind"] for e in client.get("/events").json()}
    assert "register" in kinds
