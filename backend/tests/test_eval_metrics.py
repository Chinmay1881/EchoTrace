"""Metric maths on hand-made results (no audio, no model)."""

import json

import pytest

from echotrace.eval.metrics import (ClipResult, build_metrics, detection, false_alerts, latency_from_logs, lcr,
                                    sequence_accuracy, totals)
from echotrace.schemas import Metrics

BREAKIN = [{"category": "GLASS", "zone": "LEFT"}, {"category": "IMPACT", "zone": "RIGHT"},
           {"category": "ALARM", "zone": "CENTRE"}]


def ev(cat, zone, conf=0.5):
    return {"category": cat, "zone": zone, "confidence": conf}


def alert(risk, pattern, eid="e1"):
    return {"risk": risk, "pattern": pattern, "event_id": eid}


def results():
    return [
        # perfect break-in: AMBER then RED
        ClipResult("breakin_a", "BREAKIN_ALARM", "RED", BREAKIN,
                   [ev("GLASS", "LEFT"), ev("IMPACT", "RIGHT"), ev("IMPACT", "UNKNOWN"), ev("ALARM", "CENTRE")],
                   [alert("AMBER", "GLASS_IMPACT"), alert("RED", "BREAKIN_ALARM")], baseline_alerts=4),
        # break-in where the alarm was missed: only AMBER -> wrong
        ClipResult("breakin_b", "BREAKIN_ALARM", "RED", BREAKIN,
                   [ev("GLASS", "RIGHT"), ev("IMPACT", "RIGHT")], [alert("AMBER", "GLASS_IMPACT")], baseline_alerts=2),
        # lone thud: 3 events, no EchoTrace alert, baseline alerts 3 times -> ok
        ClipResult("lone_thud", "NONE", "GREEN", [BREAKIN[1]],
                   [ev("IMPACT", "RIGHT"), ev("IMPACT", "RIGHT"), ev("IMPACT", "LEFT")], [], baseline_alerts=3),
        # chatter with a spurious DOOR event and a spurious EchoTrace alert -> not ok
        ClipResult("chatter", "NONE", "GREEN", [], [ev("DOOR", "CENTRE")], [alert("AMBER", "GLASS_IMPACT")],
                   baseline_alerts=1),
    ]


def test_got_and_ok():
    r = results()
    assert r[0].got == ("RED", "BREAKIN_ALARM") and r[0].ok
    assert r[1].got == ("AMBER", "GLASS_IMPACT") and not r[1].ok
    assert r[2].got == ("GREEN", "NONE") and r[2].ok
    assert not r[3].ok
    assert r[0].expected == "BREAKIN_ALARM/RED" and r[2].got_str == "NONE/GREEN"


def test_sequence_accuracy():
    assert sequence_accuracy(results()) == pytest.approx(0.5)
    assert sequence_accuracy([]) is None


def test_false_alerts_only_on_green_clips():
    fa = false_alerts(results())
    assert fa == {"echotrace": 1, "baseline": 4, "reduction_pct": 75.0, "clips": 2}
    assert totals(results()) == {"echotrace_alerts": 4, "baseline_alerts": 10, "events_detected": 10}
    assert false_alerts([results()[0]])["reduction_pct"] is None      # no GREEN clips -> undefined, not 100%


def test_lcr_counts_unknown_as_wrong_and_ignores_unlabelled_categories():
    m = lcr(results())
    # labelled-category events: breakin_a 4 (3 right, 1 UNKNOWN), breakin_b 2 (1 right), lone_thud 3 (2 right)
    # chatter's DOOR is not a labelled category there -> ignored
    assert m == {"accuracy": round(6 / 9, 3), "events": 9, "correct": 6, "unknown": 1}
    assert lcr([]) == {"accuracy": None, "events": 0, "correct": 0, "unknown": 0}


def test_detection_per_category():
    d = detection(results())
    assert d["GLASS"] == {"labelled": 2, "detected": 2}
    assert d["IMPACT"] == {"labelled": 3, "detected": 3}
    assert d["ALARM"] == {"labelled": 2, "detected": 1}
    assert "DOOR" not in d


def test_latency_from_logs(tmp_path):
    p = tmp_path / "run_x_events.jsonl"
    lines = [
        {"type": "status", "data": {"source": "LIVE", "latency_ms": 0.0}},
        {"type": "event", "data": {"source": "LIVE"}}, {"type": "sequence", "data": {}},
        {"type": "status", "data": {"source": "LIVE", "latency_ms": 80.0}},
        {"type": "event", "data": {"source": "LIVE"}},
        {"type": "status", "data": {"source": "LIVE", "latency_ms": 100.0}},
        {"type": "event", "data": {"source": "SIMULATED"}},              # not live: ignored
        {"type": "status", "data": {"source": "SIMULATED", "latency_ms": 1.0}},
    ]
    p.write_text("\n".join(json.dumps(x) for x in lines))
    lat = latency_from_logs([p])
    assert lat["n"] == 2 and lat["mean"] == 90.0 and lat["p95"] == pytest.approx(99.0)
    none = latency_from_logs([])
    assert none["mean"] is None and none["p95"] is None and "not measured" in none["note"]


def test_build_metrics_has_the_agreed_shape():
    m = build_metrics(results(), {"mean": 90.0, "p95": 99.0, "n": 2, "sources": [], "note": ""}, "2026-10-09T15:00:00")
    Metrics.model_validate(m)
    assert list(m)[:8] == ["generated_at", "clips", "sequence_accuracy", "false_alerts", "lcr_accuracy",
                           "latency_ms", "per_clip", "false_alerts_detail"]
    assert m["per_clip"][1] == {"clip": "breakin_b", "expected": "BREAKIN_ALARM/RED", "got": "GLASS_IMPACT/AMBER",
                                "ok": False}
