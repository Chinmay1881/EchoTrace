"""Metric maths for the evaluation (pure functions; no audio, no model - unit-tested on hand-made events).

Definitions (docs/metrics.md repeats them for readers):
- got (per clip): the highest risk any EchoTrace alert reached, and that alert's pattern; no alert = GREEN/NONE.
- ok: got risk == expected risk AND got pattern == expected pattern ("NONE" = no alerting pattern).
- false alerts: on clips whose expected risk is GREEN, EchoTrace alerts (risk step-ups) vs baseline alerts
  (one per concerning event, baseline.py). reduction_pct = (baseline - echotrace) / baseline * 100.
- lcr_accuracy: over detected events whose category is labelled in that clip, the fraction whose zone equals
  the labelled zone. UNKNOWN counts as wrong and is also reported separately.
- detection: per category, labelled events for which the clip has >= 1 detected event of that category.
- latency: only from live runs (recordings/run_*_events.jsonl); never estimated.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np

RISK_ORDER = {"GREEN": 0, "AMBER": 1, "RED": 2}


@dataclass
class ClipResult:
    clip: str
    expected_pattern: str
    expected_risk: str
    labelled: list[dict]                       # [{category, zone}]
    events: list[dict] = field(default_factory=list)          # detected: {id, category, zone, confidence, ...}
    alerts: list[dict] = field(default_factory=list)          # EchoTrace step-ups: {risk, pattern, event_id, ...}
    baseline_alerts: int = 0

    @property
    def got(self) -> tuple[str, str]:
        if not self.alerts:
            return "GREEN", "NONE"
        top = max(RISK_ORDER[a["risk"]] for a in self.alerts)
        first = next(a for a in self.alerts if RISK_ORDER[a["risk"]] == top)
        return first["risk"], first["pattern"]

    @property
    def ok(self) -> bool:
        return self.got == (self.expected_risk, self.expected_pattern)

    @property
    def expected(self) -> str:
        return f"{self.expected_pattern}/{self.expected_risk}"

    @property
    def got_str(self) -> str:
        risk, pattern = self.got
        return f"{pattern}/{risk}"


def sequence_accuracy(results: list[ClipResult]) -> float | None:
    return sum(r.ok for r in results) / len(results) if results else None


def false_alerts(results: list[ClipResult]) -> dict:
    neg = [r for r in results if r.expected_risk == "GREEN"]
    e = sum(len(r.alerts) for r in neg)
    b = sum(r.baseline_alerts for r in neg)
    return {"echotrace": e, "baseline": b,
            "reduction_pct": round((b - e) / b * 100, 1) if b else None,
            "clips": len(neg)}


def totals(results: list[ClipResult]) -> dict:
    return {"echotrace_alerts": sum(len(r.alerts) for r in results),
            "baseline_alerts": sum(r.baseline_alerts for r in results),
            "events_detected": sum(len(r.events) for r in results)}


def lcr(results: list[ClipResult]) -> dict:
    n = correct = unknown = 0
    for r in results:
        want = {lab["category"]: lab["zone"] for lab in r.labelled}
        for ev in r.events:
            if ev["category"] not in want:
                continue
            n += 1
            if ev["zone"] == "UNKNOWN":
                unknown += 1
            elif ev["zone"] == want[ev["category"]]:
                correct += 1
    return {"accuracy": round(correct / n, 3) if n else None, "events": n, "correct": correct, "unknown": unknown}


def detection(results: list[ClipResult]) -> dict:
    out: dict[str, dict] = {}
    for r in results:
        found = {ev["category"] for ev in r.events}
        for lab in r.labelled:
            d = out.setdefault(lab["category"], {"labelled": 0, "detected": 0})
            d["labelled"] += 1
            d["detected"] += lab["category"] in found
    return out


def latency_from_logs(paths: list[Path]) -> dict:
    """End-to-end latency of live events: the status message right after each event carries its latency_ms."""
    values: list[float] = []
    used = []
    for p in paths:
        pending, got_here = False, 0
        for line in p.read_text(encoding="utf-8").splitlines():
            try:
                m = json.loads(line)
            except json.JSONDecodeError:
                continue
            if m.get("type") == "event" and m["data"].get("source") == "LIVE":
                pending = True
            elif m.get("type") == "status" and pending:
                pending = False
                lat = m["data"].get("latency_ms", 0)
                if lat and lat > 0:
                    values.append(float(lat))
                    got_here += 1
        if got_here:
            used.append(p.name)
    if not values:
        return {"mean": None, "p95": None, "n": 0, "sources": [],
                "note": "no live-run logs with events (recordings/run_*_events.jsonl); latency not measured"}
    return {"mean": round(float(np.mean(values)), 1), "p95": round(float(np.percentile(values, 95)), 1),
            "n": len(values), "sources": used,
            "note": "capture of the triggering audio block -> event emitted, measured in live runs"}


def build_metrics(results: list[ClipResult], latency: dict, generated_at: str | None = None) -> dict:
    """docs/metrics.json: the agreed shape first, extras after."""
    fa = false_alerts(results)
    lc = lcr(results)
    return {
        "generated_at": generated_at or datetime.now().isoformat(timespec="seconds"),
        "clips": len(results),
        "sequence_accuracy": round(sequence_accuracy(results), 3) if results else None,
        "false_alerts": {"echotrace": fa["echotrace"], "baseline": fa["baseline"], "reduction_pct": fa["reduction_pct"]},
        "lcr_accuracy": lc["accuracy"],
        "latency_ms": {"mean": latency["mean"], "p95": latency["p95"]},
        "per_clip": [{"clip": r.clip, "expected": r.expected, "got": r.got_str, "ok": r.ok} for r in results],
        # extras (ignored by the dashboard)
        "false_alerts_detail": fa,
        "totals": totals(results),
        "lcr": lc,
        "detection": detection(results),
        "latency_detail": latency,
        "per_clip_detail": [{
            "clip": r.clip, "expected": r.expected, "got": r.got_str, "ok": r.ok,
            "events": [f"{e['category']}@{e['zone']}" for e in r.events],
            "echotrace_alerts": len(r.alerts), "baseline_alerts": r.baseline_alerts,
            "alerts": [{k: a[k] for k in ("risk", "pattern", "event_id")} for a in r.alerts],
        } for r in results],
    }
