"""Regression: the real live run of 2026-10-09 12:33 (glass LEFT -> thud RIGHT -> alarm CENTRE, then glass).

It stayed GREEN live because BREAKIN_ALARM did not exist. Replaying its events through the real
Analyzer must now give: s1 AMBER (GLASS_IMPACT) at e4, RED BREAKIN_ALARM at e9, no re-alerts for the
8 alarms after that, and the later glass-only group s2 GREEN.
"""

import json
from datetime import datetime
from pathlib import Path

import pytest

from echotrace.audio.sources import SourceInfo
from echotrace.events import Event
from echotrace.pipeline import Analyzer
from echotrace.schemas import validate

FIXTURE = Path(__file__).parent / "fixtures" / "live_run_20261009_1233.json"


def replay(upto: str | None = None):
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    info = SourceInfo("LIVE", "Microphone Array 2 ()", "Windows WDM-KS", 48000, 2)
    an = Analyzer(info, model_device="cuda", start_wall=datetime.fromisoformat(data["session_start_wall"]))
    seq_after: dict[str, dict] = {}
    for eid, t0, t1, cat, label, conf, zone, ang in data["events"]:
        for msg, _ in an.add_event(Event(eid, t0, t1, cat, label, conf, zone, float(ang))):
            validate(msg)
            if msg["type"] == "sequence":
                seq_after[eid] = msg["data"]
        if eid == upto:
            break
    return an, seq_after


@pytest.fixture(scope="module")
def run():
    return replay()


def test_s1_amber_at_first_impact_then_red_at_first_alarm(run):
    an, seq = run
    assert [seq[e]["risk"] for e in ("e1", "e2", "e3")] == ["GREEN"] * 3
    assert seq["e4"]["id"] == "s1" and seq["e4"]["risk"] == "AMBER" and seq["e4"]["pattern"] == "GLASS_IMPACT"
    assert all(seq[f"e{i}"]["risk"] == "AMBER" for i in range(5, 9))
    assert seq["e9"]["risk"] == "RED" and seq["e9"]["pattern"] == "BREAKIN_ALARM"
    # every later alarm updates the same sequence id, stays RED, same pattern
    for i in range(10, 18):
        s = seq[f"e{i}"]
        assert (s["id"], s["risk"], s["pattern"]) == ("s1", "RED", "BREAKIN_ALARM")
    assert seq["e17"]["event_ids"] == [f"e{i}" for i in range(1, 18)]


def test_alerts_fire_once_per_escalation(run):
    an, _ = run
    s1 = [(a["risk"], a["pattern"], a["event_id"]) for a in an.alerts if a["sequence_id"] == "s1"]
    assert s1 == [("AMBER", "GLASS_IMPACT", "e4"), ("RED", "BREAKIN_ALARM", "e9")]
    assert len(an.alerts) == 2                                   # nothing for s2
    assert len(an.baseline.alerts) == 21                         # the classifier alerts on every event


def test_why_lines_at_e9(run):
    _, seq = run
    assert seq["e9"]["explanation"] == [
        "Glass x3 (Glass, max 68%) on the LEFT",
        "Impact x5 (Chop, max 79%) on the RIGHT, 7.0 s after the glass",
        "Alarm (Alarm) 55% in the CENTRE, 2.5 s after the impact",
        "Possible correlated acoustic sequence, moving towards CENTRE "
        "(possible acoustic trajectory LEFT -> RIGHT -> CENTRE)",
        "Matches pattern BREAKIN_ALARM (breaking glass -> impact -> alarm (possible break-in/incident with "
        "alarm); each step within 15 s) -> RED, alert raised at e9",
    ]
    assert seq["e9"]["summary"] == (
        "12:33:35 - Breaking glass heard on the LEFT (68%), followed 7.0 s later by an impact on the RIGHT (79%) "
        "and an alarm in the CENTRE (55%). Pattern: breaking glass -> impact -> alarm (possible "
        "break-in/incident with alarm). Status RED: potentially significant sequence - verify.")
    assert seq["e9"]["trajectory"] == ["LEFT", "RIGHT", "CENTRE"]


def test_later_events_are_counted_not_realerted(run):
    _, seq = run
    why = seq["e17"]["explanation"]
    assert "8 later event(s) added to this sequence without a new alert" in why
    assert any("alert raised at e9" in w for w in why)
    # stray readings (e5 LEFT, e15/e16 RIGHT) don't scramble the trajectory: majority zone per group
    assert seq["e17"]["trajectory"] == ["LEFT", "RIGHT", "CENTRE"]


def test_s2_glass_only_stays_green(run):
    _, seq = run
    for e in ("e18", "e19", "e20", "e21"):
        assert seq[e]["id"] == "s2" and seq[e]["risk"] == "GREEN"
    assert seq["e18"]["pattern"] == "ISOLATED_EVENT"
    assert seq["e21"]["pattern"] == "NONE" and seq["e21"]["event_ids"] == ["e18", "e19", "e20", "e21"]


def test_status_risk(run):
    an, _ = run
    assert an.status(63.5)["data"]["risk"] == "RED"
    assert an.status(88.0)["data"]["risk"] == "GREEN"            # s1 decayed (last event 63.5 + 20 s)
