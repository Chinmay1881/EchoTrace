"""FastAPI server: endpoints, WS contract, runtime source switching, reset (no mic, fake tagger)."""

import time

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from echotrace import config
from echotrace.api.server import Engine, create_app
from echotrace.schemas import StatusData, validate

pytestmark = pytest.mark.skipif(not config.LABELS_FILE.exists(), reason="label CSV missing")
SR = 48000


class FakeTagger:
    device = "cpu"

    def __init__(self):
        from echotrace.tagging.categories import load_labels
        self.labels = load_labels()
        self.i = self.labels.index("Smash, crash")
        self.last_ms = 0.1

    def tag(self, window):
        p = np.full(len(self.labels), 0.01, dtype=np.float32)
        newest = window[-SR // 2:]
        if 20 * np.log10(np.sqrt(np.mean(newest.astype(np.float64) ** 2)) + 1e-12) > -30:
            p[self.i] = 0.8
        return p


def make_wav(path, n_events=2):
    rng = np.random.default_rng(0)
    x = 0.001 * rng.standard_normal((6 * SR, 2))
    for k in range(n_events):
        a = int((1.5 + 2.5 * k) * SR)
        burst = 0.3 * rng.standard_normal(int(0.2 * SR))
        x[a:a + len(burst), 0] += burst
        x[a + 7:a + 7 + len(burst), 1] += burst          # right channel later -> LEFT (default calibration)
    sf.write(path, x, SR, subtype="PCM_24")
    return path


def recv_until(ws, pred, timeout=8.0):
    """Receive (and contract-validate) messages until pred(msg) is true; returns all received."""
    got, t0 = [], time.monotonic()
    while time.monotonic() - t0 < timeout:
        msg = ws.receive_json()
        validate(msg)
        got.append(msg)
        if pred(msg):
            return got
    raise AssertionError(f"condition not met; got types {[m['type'] for m in got]}")


@pytest.fixture()
def client():
    engine = Engine(tagger_factory=FakeTagger, realtime=True)
    app = create_app(engine, {"source": "SIMULATED", "scenario": "breakin"})
    with TestClient(app) as c:
        t0 = time.monotonic()
        while engine.pipeline is None and time.monotonic() - t0 < 5:
            time.sleep(0.05)
        yield c


def test_status_and_mode(client):
    st = client.get("/api/status").json()
    StatusData.model_validate(st)                                 # contract fields present (+ extras allowed)
    assert st["source"] == "SIMULATED" and st["localization"] == "ON"
    m = client.get("/api/mode").json()
    assert m["source"] == "SIMULATED" and {"t", "wall"} <= set(m)


def test_ws_streams_contract_messages_labelled_simulated(client):
    with client.websocket_connect("/ws") as ws:
        first = ws.receive_json()
        assert first["type"] == "status"                          # snapshot starts with status, like the mock
        msgs = recv_until(ws, lambda m: m["type"] == "frame")
        assert all(m["data"]["source"] == "SIMULATED" for m in [first] + msgs)


def test_invalid_mode_and_errors_use_error_key(client):
    r = client.post("/api/mode", json={"source": "BOGUS"})
    assert r.status_code == 400 and "error" in r.json()
    r = client.post("/api/mode", content=b"not json", headers={"Content-Type": "application/json"})
    assert r.status_code == 400 and r.json() == {"error": "Invalid JSON"}
    r = client.post("/api/mode", json={"source": "RECORDED", "file": "does_not_exist.wav"})
    assert r.status_code == 400 and "not found" in r.json()["error"]
    assert client.get("/api/status").json()["source"] == "SIMULATED"   # still running the old mode
    r = client.get("/api/nope")
    assert r.status_code == 404 and r.json() == {"error": "Not found"}


def test_switch_to_recorded_then_events_and_reset(client, tmp_path):
    wav = make_wav(tmp_path / "clip.wav")
    r = client.post("/api/mode", json={"source": "recorded", "file": str(wav)})
    assert r.status_code == 200, r.text
    assert r.json()["source"] == "RECORDED"
    with client.websocket_connect("/ws") as ws:
        msgs = recv_until(ws, lambda m: m["type"] == "event", timeout=10)
        ev = [m for m in msgs if m["type"] == "event"][0]["data"]
        assert ev["source"] == "RECORDED" and ev["category"] == "IMPACT" and ev["zone"] == "LEFT"
        assert ev["id"].startswith("m2-e")                          # ids unique per mode session
    events = client.get("/api/events").json()
    assert isinstance(events, list) and events and events[0]["source"] == "RECORDED"
    st = client.get("/api/status").json()
    assert st["source"] == "RECORDED" and st["latency_ms"] > 0       # measured capture -> WS send
    r = client.post("/api/reset")
    assert r.status_code == 200 and r.json()["ok"] is True
    t0 = time.monotonic()
    while client.get("/api/events").json() and time.monotonic() - t0 < 3:
        time.sleep(0.05)
    assert client.get("/api/events").json() == []


def test_switch_back_to_simulated_changes_labels(client, tmp_path):
    wav = make_wav(tmp_path / "clip.wav", n_events=1)
    assert client.post("/api/mode", json={"source": "RECORDED", "file": str(wav)}).status_code == 200
    r = client.post("/api/mode", json={"source": "SIMULATED"})
    assert r.status_code == 200 and r.json()["source"] == "SIMULATED"
    with client.websocket_connect("/ws") as ws:
        msgs = recv_until(ws, lambda m: m["type"] == "frame")
        assert all(m["data"]["source"] == "SIMULATED" for m in msgs)


SAMPLE_METRICS = {
    "generated_at": "2026-10-09T15:00:00",
    "clips": 6,
    "sequence_accuracy": 0.83,
    "false_alerts": {"echotrace": 1, "baseline": 9, "reduction_pct": 88.9},
    "lcr_accuracy": 0.78,
    "latency_ms": {"mean": 96.0, "p95": 172.0},
    "per_clip": [{"clip": "demo_1.wav", "expected": "MOVEMENT_IMPACT_DISTRESS", "got": "MOVEMENT_IMPACT_DISTRESS",
                  "ok": True}],
    "extra_key_from_eval": "kept as-is",
}


def test_metrics_served_as_is(client, tmp_path, monkeypatch):
    import json
    from echotrace.schemas import Metrics
    monkeypatch.setattr(config, "DOCS_DIR", tmp_path)              # never touch the real docs/
    assert client.get("/api/metrics").json() == {}                # missing -> {}
    (tmp_path / "metrics.json").write_text(json.dumps(SAMPLE_METRICS), encoding="utf-8")
    got = client.get("/api/metrics").json()
    assert got == SAMPLE_METRICS                                  # exactly as written, extra keys included
    Metrics.model_validate(got)                                   # and it matches the agreed shape


def test_metrics_and_root(client):
    assert isinstance(client.get("/api/metrics").json(), dict)
    r = client.get("/")
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]


def test_cors_preflight(client):
    r = client.options("/api/mode", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"})
    assert r.status_code == 200 and r.headers.get("access-control-allow-origin") in ("*", "http://localhost:5173")
